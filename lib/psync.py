from __future__ import absolute_import
from runcmd import runcmd, Run_Cmd_Error
import celery
import celery.utils.log
import os
import stat
import pprint
import pylut
import redis_logger
import fsitem
import time


# A note about naming convention of functions in this module:
# sync_* = celery task
# *_sync = local (normal) function

logger = celery.utils.log.get_task_logger(__name__)
app = celery.Celery( 'psync' )
app.config_from_object('psync_celery_config')
app.config_from_object('broker_url')
redisconf_fn = os.environ[ 'PSYNCREDISURLFILE' ]
redisconf_name = os.path.basename( redisconf_fn ).split( '.py' )[0]
redisconf = __import__( redisconf_name )
# TODO Get log queue_name from config file (or cmdline?)
logr = redis_logger.Redis_Logger( url=redisconf.BROKER_URL, queue_name='psync_log' )

# TODO - remove rsyncpath after moving symlink_sync to external library
rsyncpath = os.environ[ 'PYLUTRSYNCPATH' ]

localhostname = os.uname()[1]


class Psync_Task( celery.Task ):
    abstract = True
    max_retries = 0
    def on_failure( self, exc, task_id, args, kwargs, einfo ):
        msg = 'Caught exception'
        logr.error( msg,
                    exception_type = str( einfo.type ),
                    exception      = str( exc ),
                    args           = str( args ),
                    kwargs         = str( kwargs ),
                    traceback      = str( einfo.traceback ) )


@app.task( base=Psync_Task )
def sync_dir( src, tgt, psyncopts, rsyncopts ):
    """
    Celery task; read contents of dir, sync small files and symlinks, 
    enqueue large files and dirs
    :param src FSItem: source dir
    :param src FSItem: target dir
    :param psyncopts dict: options for adjusting psync behavior
    :param rsyncopts dict: options passed to pylut.syncdir & pylut.syncfile
    :return: None
    """
    logr.info( synctype = 'SYNCDIR',
               msgtype  = 'start',
               src      = str( src ),
               tgt      = str( tgt ) )
    ( src_dirs, src_files, src_symlinks ) = dir_scan( src, psyncopts )
    tgt_dirs, tgt_files, tgt_symlinks = [ {} ] * 3
    if os.path.exists( str( tgt ) ):
        ( tgt_dirs, tgt_files, tgt_symlinks ) = dir_scan( tgt, psyncopts )
    # Create sets of names of each filetype from both src and tgt
    src_dir_set = set( src_dirs.keys() )
    src_file_set = set( src_files.keys() )
    src_symlink_set = set( src_symlinks.keys() )
    tgt_dir_set = set( tgt_dirs.keys() )
    tgt_file_set = set( tgt_files.keys() )
    tgt_symlink_set = set( tgt_symlinks.keys() )
    logr.info( synctype = 'SYNCDIR',
               msgtype  = 'info',
               src      = str( src ),
               tgt      = str( tgt ),
               num_src_dirs    = len( src_dir_set ), 
               num_src_files   = len( src_file_set ), 
               num_src_symlinks= len( src_symlink_set ), 
               num_tgt_dirs    = len( tgt_dir_set ), 
               num_tgt_files   = len( tgt_file_set ), 
               num_tgt_symlinks= len( tgt_symlink_set ) )
    # Delete entries in tgt that no longer exist in src
    # To be accurate, these processes must all finish before proceeding
    #   (use case: previous directory was removed and new file exists by the same name
    #    as the old directory)
    for d in tgt_dir_set - src_dir_set:
        #TODO - for rmdir, get tmpbase from mountpoint + basemod from config file
        rm_dir( tgt_dirs[ d ].absname, 
                tmpbase=os.path.join( tgt.mountpoint, '__PSYNCRMDIR__' ) )
    for f in tgt_file_set - src_file_set:
        rm_file( tgt_files[ f ].absname )
    for s in tgt_symlink_set - src_symlink_set:
        rm_file( tgt_symlinks[ s ].absname )
    # make subdirs (their metadata will get sync'd by another task)
    for dname in src_dir_set:
        newsrc = src_dirs[ dname ]
        if dname not in tgt_dirs:
            tgt_dirs[ dname ] = _mk_new_fsitem( tgt, dname )
        newtgt = tgt_dirs[ dname ]
        try:
            os.mkdir( str( newtgt ) )
        except ( OSError ) as e:
            # Can ignore ... OSError: [Errno 17] File exists
            if e.errno != 17:
                raise e
        sync_dir.apply_async( ( newsrc, newtgt, psyncopts, rsyncopts ) )
    # iterate over files
    for fname in src_file_set:
        newsrc = src_files[ fname ]
        if fname not in tgt_files:
            tgt_files[ fname ] = _mk_new_fsitem( tgt, fname )
        newtgt = tgt_files[ fname ]
        file_sync( newsrc, newtgt, psyncopts, rsyncopts )
    # iterate over symlinks
    for sname in src_symlink_set:
        newsrc = src_symlinks[ sname ]
        if sname not in tgt_symlinks:
            tgt_symlinks[ sname ] = _mk_new_fsitem( tgt, sname )
        newtgt = tgt_symlinks[ sname ]
        symlink_sync( newsrc, newtgt, rsyncopts )
    # sync the (local) dir to set metadata
    dir_sync( src, tgt, psyncopts, rsyncopts )
    logr.info( synctype = 'SYNCDIR',
               msgtype  = 'end',
               src      = str( src ),
               tgt      = str( tgt ) )
    

def _mk_new_fsitem( parent, name ):
    return fsitem.FSItem( 
        name,
        absname=os.path.join( parent.absname, name ),
        mountpoint=parent.mountpoint )


@app.task( base=Psync_Task )
def sync_file( src, tgt, rsyncopts ):
    """
    Celery task, sync a regular file
    :param src FSItem: src file
    :param tgt FSItem: tgt file
    :param rsyncopts dict: options passed to pylut.syncdir & pylut.syncfile
    :return: None
    """
    #TODO - get basemod from config file (or cmdline?)
    basemod = '__PSYNCTMPDIR__'
    rsyncopts.update( tmpbase = os.path.join( tgt.mountpoint, basemod ),
                      keeptmp = True,
                    )
    logr.info( synctype = 'SYNCFILE',
               msgtype  = 'start',
               src      = str( src ),
               tgt      = str( tgt ),
               size     = src.size )
    try:
        tmpfn, action_type, attrs_affected = pylut.syncfile( src, tgt, **rsyncopts )
    except ( pylut.PylutError ) as e:
        logr.warning( synctype = 'SYNCFILE',
                      msgtype  = 'error',
                      src      = str( src ),
                      tgt      = str( tgt ),
                      error    = str( e ) )
        return
    msg_parts = {}
    if rsyncopts[ 'pre_checksums' ]:
        msg_parts.update( src_chksum = src.checksum(),
                          tgt_chksum = tgt.checksum() )
    sync_action = 'None'
    if action_type[ 'data_copy' ]:
        sync_action = 'data_copy'
        if rsyncopts[ 'post_checksums' ] and not rsyncopts[ 'pre_checksums' ]:
            # If pre_checksums is enabled, then skip adding checksums again here
            msg_parts.update( src_chksum = src.checksum(),
                              tgt_chksum = tgt.checksum() )
    elif action_type[ 'meta_update' ]:
        sync_action = 'meta_update'
        
    msg_parts.update( synctype = 'SYNCFILE',
                      msgtype  = 'end',
                      src = str( src ),
                      tgt = str( tgt ),
                      action = sync_action )
    logr.info( **msg_parts )


def dir_scan( dirobj, psyncopts ):
    """
    Get directory contents
    :param dirobj FSItem: directory to scan
    :param psyncopts dict: options for adjusting psync behavior
    :return: tuple of dicts ( dirs, files, symlinks ) where keys=name and values=FSItem object
    """
    dirs = {}
    files = {}
    symlinks = {}
    checkage = False
    if psyncopts[ 'minsecs' ] > 0:
        maxage = int( time.time() ) - psyncopts[ 'minsecs' ]
        checkage = True
    # Unicode errors with scandir
    # do Unicode errors go away with listdir?
    for name in os.listdir( dirobj.absname ):
        entry = _mk_new_fsitem( dirobj, name )
        try:
            if entry.is_dir():
                dirs[ name ] = entry
            else:
                if checkage and entry.mtime > maxage:
                    logr.warning( synctype = 'dir_scan',
                                  msgtype  = 'skipentry',
                                  action   = 'InodeTooYoung',
                                  src      = str( entry ) )
                    continue
                if entry.is_file():
                    files[ name ] = entry
                elif entry.is_symlink():
                    symlinks[ name ] = entry
        except ( OSError ) as e:
            # Any one of is_dir, is_file, is_symlink can throw
            # OSError: [Errno 2] No such file or directory
            # have to ignore these, since no way to tell if FS is live or quiesced
            if e.errno != 2:
                raise e
            #logr.warning( 'Caught error in psync.dir_scan: {0}'.format( e ) )
    return ( dirs, files, symlinks )


def rm_file( path ):
    """ Remove the file or symlink
    """
    logr.info( synctype = 'RMFILE',
               src      = str( path ) )
    os.unlink( path )


def rm_dir( path, tmpbase ):
    """ Move the directory out of the way to be deleted later
    """
    fid = pylut.path2fid( path )
    tgt = os.path.join( tmpbase, fid )
    logr.info( synctype = 'RMDIR',
               msgtype  = 'start',
               src      = path,
               tgt      = tgt,
               action   = 'rename' )
    os.rename( path, tgt )
    logr.info( synctype = 'RMDIR',
               msgtype  = 'end',
               src      = path,
               tgt      = tgt )


def dir_sync( src, tgt, psyncopts, rsyncopts ):
    """
    Wrap details of directory sync.
    Create tgt dir.
    Put src dir on queue.
    :param src FSItem: src directory
    :param tgt FSItem: tgt directory
    :param psyncopts dict: options for adjusting psync behavior
    :param rsyncopts dict: options passed to pylut.syncdir
    :return: None
    """
    #TODO - add error handling for pylut.syncdir
    dirsyncopts = {}
    for k in ( 'syncowner', 'syncgroup', 'syncperms', 'synctimes' ):
        dirsyncopts[ k ] = rsyncopts[ k ]
    ( output, errput ) = pylut.syncdir( src, tgt, **dirsyncopts )


def file_sync( src, tgt, psyncopts, rsyncopts ):
    """
    Wrap details of file sync.
    Make tgt_path look identical to src_path.
    :param src FSItem: src file
    :param tgt FSItem: tgt file
    :param psyncopts dict: options for adjusting psync behavior
    :param rsyncopts dict: options passed to pylut.syncfile
    :return: None
    """
    if src.nlink > 1:
        # TODO - all src files having numlinks > 1 
        #        should be enqueue'd to HARDLINK QUEUE
        # TODO - can we call sync_file directly (without an apply or apply_async)?
        sync_file.apply( ( src, tgt, rsyncopts ) )
    else:
        sync_file.apply_async( ( src, tgt, rsyncopts ) )


def symlink_sync( src, tgt, rsyncopts ):
    """
    Wrap details of symlink sync.
    :param src FSItem: src symlink
    :param tgt FSItem: tgt symlink
    :return: None
    Note: The target of the symlink is copied as is, no changes are made to it.
    """
    # TODO - move symlink sync to a function in the pylut module.
    #        This will allow future enhancements to use a module other than 
    #        pylut without breaking psync.

    #resolve symlink
    sym_tgt_orig = os.readlink( src.absname )
    sym_tgt_new = sym_tgt_orig
    symtype = 'ignored'
    symaction = 'create'
    do_symlink = True
#    # attempt to replace mountpoint for an absolute symlink
#    if sym_tgt_orig.startswith( src.mountpoint ):
#        sym_tgt_new = sym_tgt_orig.replace( src.mountpoint, tgt.mountpoint, 1 )
#        symtype = 'absolute'
    logr.info( synctype     = 'SYMLINK',
               msgtype      = 'start',
               src_src      = str( src ),
               src_tgt      = sym_tgt_orig,
               tgt_src      = str( tgt ),
               tgt_tgt      = sym_tgt_new,
               symlink_type = symtype )
    if tgt.exists():
        if tgt.is_symlink():
            # check existing symtgt against what we think it should be
            tgt_sym_tgt = os.readlink( str( tgt ) )
            if tgt_sym_tgt == sym_tgt_new:
                symaction = 'None'
                do_symlink = False
            else:
                os.unlink( str( tgt ) )
        else:
            # tgt exists but is not a symlink, remove it so we can make a symlink
            os.unlink( str( tgt ) )
    if do_symlink:
        cmd = [ rsyncpath ]
        opts = None
        args = [ '-X', '-A', '--super', '-l' ]
        if 'synctimes' in rsyncopts:
            args.append( '-t' )
        if 'syncperms' in rsyncopts:
            args.append( '-p' )
        if 'syncowner' in rsyncopts:
            args.append( '-o' )
        if 'syncgroup' in rsyncopts:
            args.append( '-g' )
        args.extend( [ src, tgt ] )
        try:
            ( output, errput ) = runcmd( cmd, opts, args )
        except ( Run_Cmd_Error ) as e:
            logr.error( 'caught RunCmdError in sync_symlink',
                          exception_type = type( e ),
                          exception = e,
                          args = args,
                          kwargs = opts )
            return
#                          traceback = traceback.format_tb( sys.exc_info()[2] ) )
#        finally:
#            sys.exc_clear()
        
#        try:
#            os.symlink( sym_tgt_new, tgt.absname )
#            # TODO - utime changes the target file instead of the symlink itself
#            os.utime( sym_tgt_new, ( src.atime, src.mtime ) )
#        except ( OSError ) as e:
#            # TODO - log exception as an error, not a warning
#            logr.warning( synctype     = 'SYMLINK',
#                       msgtype      = 'error',
#                       src_src      = str( src ),
#                       src_tgt      = sym_tgt_orig,
#                       tgt_src      = str( tgt ),
#                       tgt_tgt      = sym_tgt_new,
#                       error        = str( e ) )
#            return
    logr.info( synctype     = 'SYMLINK',
               msgtype      = 'end',
               src_src      = str( src ),
               src_tgt      = sym_tgt_orig,
               tgt_src      = str( tgt ),
               tgt_tgt      = sym_tgt_new,
               action       = symaction )


if __name__ == '__main__':
  raise UserWarning( "Cmdline invocation not supported" )
