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
import celeryconfig
import broker_url

# A note about naming convention of functions in this module:
# sync_* = celery task
# *_sync = local (normal) function

logger = celery.utils.log.get_task_logger(__name__)
app = celery.Celery( 'psync' )
# Collect config settings from config modules
app.conf.update( **{ k:getattr( celeryconfig,k ) 
    for k in dir( celeryconfig ) if not k.startswith('__') } )
app.conf.update( **{ k:getattr( broker_url,k ) 
    for k in dir( broker_url ) if not k.startswith('__') } )
redisconf_fn = os.environ[ 'PSYNCREDISURLFILE' ]
redisconf_name = os.path.basename( redisconf_fn ).split( '.py' )[0]
redisconf = __import__( redisconf_name )
# TODO Get log queue_name from config file (or cmdline?)
logr = redis_logger.Redis_Logger( url=redisconf.BROKER_URL, queue_name='psync_log' )
#logr.info( 'CELERY_ROUTES: {0}'.format( app.conf.CELERY_ROUTES ) )

psynctmpdir = os.environ[ 'PSYNCTMPDIR' ]
psyncrmdir = os.environ[ 'PSYNCRMDIR' ]

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
    Celery task; read contents of dir, 
    create target dir if needed,
    delete contents from target as needed,
    enqueue subdirs and files as new sync tasks
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
    ( src_dirs, src_files ) = dir_scan( src, psyncopts )
    tgt_dirs, tgt_files = [ {} ] * 2
    if os.path.exists( str( tgt ) ):
        ( tgt_dirs, tgt_files ) = dir_scan( tgt, psyncopts )
    # Create sets of names of each filetype from both src and tgt
    src_dir_set = set( src_dirs.keys() )
    src_file_set = set( src_files.keys() )
    tgt_dir_set = set( tgt_dirs.keys() )
    tgt_file_set = set( tgt_files.keys() )
    logr.info( synctype = 'SYNCDIR',
               msgtype  = 'info',
               src      = str( src ),
               tgt      = str( tgt ),
               num_src_dirs    = len( src_dir_set ), 
               num_src_files   = len( src_file_set ), 
               num_tgt_dirs    = len( tgt_dir_set ), 
               num_tgt_files   = len( tgt_file_set ) )
    # Delete entries in tgt that no longer exist in src
    # To be accurate, these processes must all finish before proceeding
    #   (use case: previous directory was removed and new file exists by the same name
    #    as the old directory)
    tmpbase=os.path.join( tgt.mountpoint, psyncrmdir )
    for d in tgt_dir_set - src_dir_set:
        try:
            rm_dir( tgt_dirs[ d ].absname, tmpbase=tmpbase )
        except ( Exception ) as e:
            logr.error( synctype = 'RMDIR',
                        msgtype = 'error',
                        src = tgt_dirs[ d ].absname,
                        tgt = tmpbase )
    for f in tgt_file_set - src_file_set:
        try:
            rm_file( tgt_files[ f ].absname )
        except ( Exception ) as e:
            logr.error( synctype = 'RMFILE',
                        msgtype = 'error',
                        src = tgt_files[ f ].absname,
                        tgt = tmpbase )
    # iterate over dirs
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
    # sync the (local) dir to set metadata
    sync_dir_meta.apply_async( ( src, tgt, psyncopts, rsyncopts ) )
    logr.info( synctype = 'SYNCDIR',
               msgtype  = 'end',
               src      = str( src ),
               tgt      = str( tgt ) )


@app.task( base=Psync_Task, queue='directories' )
def sync_dir_meta( src, tgt, psyncopts, rsyncopts ):
    """
    Sync metadata only of a directory
    :param src FSItem: src directory
    :param tgt FSItem: tgt directory
    :param psyncopts dict: options for adjusting psync behavior
    :param rsyncopts dict: options passed to pylut.syncdir
    :return: None
    """
    logr.info( synctype = 'SYNCDIRMETA',
               msgtype  = 'start',
               src      = str( src ),
               tgt      = str( tgt ) )
    dirsyncopts = {}
    for k in ( 'syncowner', 'syncgroup', 'syncperms', 'synctimes' ):
        dirsyncopts[ k ] = rsyncopts[ k ]
    #TODO - add error handling for pylut.syncdir
    ( output, errput ) = pylut.syncdir( src, tgt, **dirsyncopts )
    logr.info( synctype = 'SYNCDIRMETA',
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
    Celery task, sync a file
    :param src FSItem: src file
    :param tgt FSItem: tgt file
    :param rsyncopts dict: options passed to pylut.syncdir & pylut.syncfile
    :return: None
    """
    _sync_a_file( src, tgt, rsyncopts, 'FILE' )


@app.task( base=Psync_Task, queue='hardlinks' )
def sync_hardlink( src, tgt, rsyncopts ):
    """
    Celery task, sync a file with multiple hardlinks
    This is identical to sync_file, but has to be a separate function so tasks
    can be assigned on a special named queue.
    :param src FSItem: src file
    :param tgt FSItem: tgt file
    :param rsyncopts dict: options passed to pylut.syncdir & pylut.syncfile
    :return: None
    """
    _sync_a_file( src, tgt, rsyncopts, 'HARDLINK' )


def _sync_a_file( src, tgt, rsyncopts, ftype ):
    """
    Common code for syncing any file.  This function will be called by one of
    the sync_file or sync_hardlink Celery Task functions.
    :param src FSItem: src file
    :param tgt FSItem: tgt file
    :param rsyncopts dict: options passed to pylut.syncdir & pylut.syncfile
    :param ftype string: file type that is being sync'd (ie: file or hardlink)
    :return: None
    """
    rsyncopts.update( tmpbase = os.path.join( tgt.mountpoint, psynctmpdir ),
                      keeptmp = True,
                    )
    synctype = 'SYNC' + ftype.upper()
    logr.info( synctype = synctype,
               msgtype  = 'start',
               src      = str( src ),
               tgt      = str( tgt ),
               size     = src.size )
    try:
        tmpfn, action_type = pylut.syncfile( src, tgt, **rsyncopts )
    except ( pylut.PylutError ) as e:
        logr.warning( synctype = synctype,
                      msgtype  = 'error',
                      src      = str( src ),
                      tgt      = str( tgt ),
                      error    = str( e ) )
        return
    msg_parts = {}
    if tmpfn.nlink < 3 and rsyncopts[ 'pre_checksums' ]:
        msg_parts.update( src_chksum = src.checksum(),
                          tgt_chksum = tgt.checksum() )
    sync_action = 'None'
    if action_type[ 'data_copy' ]:
        sync_action = 'data_copy'
        if rsyncopts[ 'post_checksums' ] and not rsyncopts[ 'pre_checksums' ]:
            # do post checksums only if pre_checksums haven't done it already
            msg_parts.update( src_chksum = src.checksum(),
                              tgt_chksum = tgt.checksum() )
    elif action_type[ 'meta_update' ]:
        sync_action = 'meta_update'
    msg_parts.update( synctype = synctype,
                      msgtype  = 'end',
                      src = str( src ),
                      tgt = str( tgt ),
                      action = str( sync_action ) )
    logr.info( **msg_parts )


def dir_scan( dirobj, psyncopts ):
    """
    Get directory contents
    :param dirobj FSItem: directory to scan
    :param psyncopts dict: options for adjusting psync behavior
    :return: tuple of dicts ( dirs, files ) where keys=name and values=FSItem object
    """
    dirs = {}
    files = {}
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
            elif entry.is_file():
                if checkage and entry.ctime > maxage:
                    logr.warning( synctype = 'dir_scan',
                                  msgtype  = 'skipentry',
                                  action   = 'InodeTooYoung',
                                  src      = str( entry ) )
                    continue
                files[ name ] = entry
            else:
                logr.warning( synctype = 'dir_scan',
                              msgtype  = 'skipentry',
                              action   = 'unknown file type',
                              src      = str( entry ) )
        except ( OSError ) as e:
            # Any one of is_dir, is_file
            # OSError: [Errno 2] No such file or directory
            # have to ignore these, since no way to tell if FS is live or quiesced
            if e.errno != 2:
                raise e
            logr.warning( 'Caught exception in psync.dir_scan',
                          synctype = 'dir_scan',
                          msgtype  = 'warning',
                          action   = '{0}'.format( e ),
                          src      = str( entry ) )
    return ( dirs, files )


def rm_file( path ):
    """ Remove the specified file
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
        sync_hardlink.apply_async( ( src, tgt, rsyncopts ) )
    else:
        sync_file.apply_async( ( src, tgt, rsyncopts ) )


@app.task( base=Psync_Task )
def schedule_final_dir_sync( secs=300 ):
    """
    If all the regular syncs are done, enable all workers to start working on the
    final sync_dir_meta tasks.
    """
    #TODO-get queue name from app.conf.CELERY_ROUTES
    if dirs_and_files_are_done():
        app.control.add_consumer( 'directories' )
    else:
        schedule_final_dir_sync.apply_async( args=( secs, ), countdown=secs )


def dirs_and_files_are_done():
    """
    Return True if all dir and file sync actions are complete, False otherwise
    """
    rvparts = [ True ]
    # Check queue lengths
    qnames = [ app.conf.CELERY_DEFAULT_QUEUE ]
    #    #TODO - get list of queues from CELERY_ROUTES
    #    for x,y in app.conf.CELERY_ROUTES.iteritems():
    #        q = y['queue']
    #        if q != 'directories':
    #            qnames.append( q )
    qnames.extend( [ 'hardlinks' ] )
    logr.info( 'qnames: {0}'.format( qnames ) )
    total_len = sum( queue_lengths( qnames ) )
    logr.info( 'total_len: {0}'.format( total_len ) )
    if total_len != 0:
        rvparts.append( False )
    # Check for idle workers
    taskcount = 0
    for func in ( active_tasks, reserved_tasks ):
        for name, count in func().iteritems():
            if 'schedule_final_dir_sync' not in name:
                taskcount += count
    rvparts.append( taskcount == 0 )
    return all( rvparts )


def active_tasks():
    """
    Return count of active tasks by task name
    :return dict: keys are task names, values are int (count of active tasks)
    """
    I = app.control.inspect()
    data = {}
    for w, tlist in I.active().iteritems():
        for task in tlist:
            name = task[ 'name' ]
            if name not in data:
                data[ name ] = 0
            data[ name ] += 1
    return data


def reserved_tasks():
    """
    Return count of reserved tasks by task name
    :return dict: keys are task names, values are int (count of active reserved)
    """
    I = app.control.inspect()
    data = {}
    for w, tlist in I.reserved().iteritems():
        for task in tlist:
            name = task[ 'name' ]
            if name not in data:
                data[ name ] = 0
            data[ name ] += 1
    return data


def queue_lengths( qnames ):
    """
    Return lengths for each queue in qnames
    :param qnames list of queue names
    :return list: list of queue lengths, values match positions of queuenames in qnames
    """
    qlens = []
    for q in qnames:
        with app.connection_or_acquire() as conn:
            qlens.append( 
                conn.default_channel.queue_declare(
                    queue=q, passive=True).message_count
            )
    return qlens

if __name__ == '__main__':
  raise UserWarning( "Cmdline invocation not supported" )
