import os
import pprint
import fsitem
import psync
import time
import cbor
import parse_worker_errlog
from runcmd import runcmd, Run_Cmd_Error

rsyncopts = dict( syncowner = True,
                  syncgroup = True,
                  syncperms = True,
                  synctimes = True,
                  pre_checksums = False,
                  post_checksums = True
                )

psyncopts = dict( minsecs = 0,
                  pre_checksums = False
                )

def _truncate( fn ):
    with open( str( fn ), 'wb' ) as fh:
        pass

def wait_for( func, max_seconds=10, pause=1 ):
    """ def wait_for
        Wait for up to max_seconds for func to return True
        If func returns True within time alloted, return True
        Otherwise, return False
        func must return a boolean value (others might work, but behavior is undefined)
    """
    rv = False
    start = time.time()
    diff = 0
    while rv != True and diff < max_seconds:
        rv = func()
        if rv is not True and rv is not False:
            raise UserWarning( "func '{0}' did not return a boolean value".format( func ) )
        time.sleep( pause )
        diff = time.time() - start
    return rv


def psync_is_complete():
    """ def psync_is_complete():
        Return True if psync is complete, False otherwise
    """
    return workers_are_idle()


def workers_are_idle():
    """ def workers_are_idle():
        Return True if workers are idle, False otherwise
    """
    rv = False
    # get per worker active tasks
    num_active_tasks = 0
    for worker, activelist in psync.app.control.inspect().active().iteritems():
        num_active_tasks += len( activelist )
    # get per worker reserved tasks
    num_reserved_tasks = 0
    for worker, reservedlist in psync.app.control.inspect().reserved().iteritems():
        num_reserved_tasks += len( reservedlist )
    if num_active_tasks == 0 and num_reserved_tasks == 0:
        rv = True
    return rv


def get_redis_logs():
    """ def get_redis_logs():
        Return lists of logs separated by severity as
        dict( DEBUG=[], INFO=[], WARNING=[], ERROR=[] )
    """
    logmsgs = dict( DEBUG=[], INFO=[], WARNING=[], ERROR=[] )
    rq = psync.logr.rq
    for m in rq.qpop_all():
        msgdict = cbor.loads( m )
        logmsgs[ msgdict[ 'sev' ] ].append( m )
#    for k in [ 'WARNING', 'ERROR' ]:
#        pprint.pprint( logmsgs[ k ] )
    return logmsgs


def get_task_errors():
    """
    Return list of warnings and errors from psync tasks
    """
    logmsgs = get_redis_logs()
    errors = []
    for k in [ 'WARNING', 'ERROR' ]:
        if len( logmsgs[ k ] ) > 0:
#            pprint.pprint( logmsgs[ k ] )
            errors.append( pprint.pformat( logmsgs[ k ] ) )
    return errors


def get_worker_errors():
    """
    Return list of errors, if any, from celery workers
    """
    logfiles = []
    worker_log_dir = os.path.join( os.environ[ 'PSYNCVARDIR' ], 'psync_service' )
    for root, dirs, files in os.walk( worker_log_dir ):
        logfiles.extend( [ os.path.join( root, f ) for f in files if f.endswith( '.log' ) ] )
    errors = parse_worker_errlog.parse_files( logfiles )
    for f in logfiles:
        _truncate( f )
    return errors


def error_free_sync():
    """
    Return True if no errors or warnings produced, False otherwise
    """
    rv=True
    worker_errs = get_worker_errors()
    if len( worker_errs ) > 0:
        rv = False
        print( 'Worker Errors:' )
        args = parse_worker_errlog.process_cmdline()
        print( parse_worker_errlog.format_output( worker_errs, args ) )
    task_errs = get_task_errors()
    if len( task_errs ) > 0:
        rv = False
        print( 'Task Errors:' )
        pprint.pprint( task_errs )
    return rv
    

def in_sync( src, tgt ):
    """
    Return True if rsync finds no differences, False otherwise
    """
    rv = False
    cmd = [ os.environ[ 'PYLUTRSYNCPATH' ] ]
    opts = { '--timeout': 60 }
    args = [ '-nirlHAtpog', '--specials' ]
    args.append( '{0}/'.format( src ) )
    args.append( '{0}/'.format( tgt ) )
    ( output, errput ) = runcmd( cmd, opts, args )
    #TODO-remove this filter once dir mtimes are fixed (issue #2)
    # filter out known dir mtime mismatches
    leftovers = []
    for line in output.splitlines():
        if not line.startswith( '.d..t...... '):
            leftovers.append( line )
    output = leftovers
    # any output from rsync indicates incorrect sync behavior
    if len( errput ) < 1 and len( output ) < 1:
        rv = True
    else:
        pprint.pprint( output )
        pprint.pprint( errput )
    return rv


def test_sync_no_hardlinks( testdir ):
    # don't create hardlinks
    testdir.config.HARDLINK_WEIGHT=0
    testdir.reset()
    # run psync from testdir.source to testdir.target
    src = fsitem.FSItem( testdir.config.SOURCE_DIR )
    tgt = fsitem.FSItem( testdir.config.DEST_DIR )
    psync.sync_dir.delay( src, tgt, psyncopts, rsyncopts )
    assert wait_for( psync_is_complete, max_seconds=6000 )
    assert error_free_sync()

    # TODO ?? check RMQ for errors ??

    # clear any cached meta data
    src.update()
    tgt.update()
    # verify source matches target
    assert in_sync( src, tgt )


#def test_full_sync( testdir ):
#    # ensure psconfig defaults
#    testdir.reset_config()
#    testdir.reset()
#    # run psync from testdir.source to testdir.target
#    src = fsitem.FSItem( testdir.config.SOURCE_DIR )
#    tgt = fsitem.FSItem( testdir.config.DEST_DIR )
#    psync.sync_dir.delay( src, tgt, psyncopts, rsyncopts )
#    assert wait_for( psync_is_complete, max_seconds=6000 )
#    assert error_free_sync()
#
#    # TODO ?? check RMQ for errors ??
#
#    # clear any cached meta data
#    src.update()
#    tgt.update()
#    # verify source matches target
#    assert in_sync( src, tgt )

