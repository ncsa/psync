import psync
import argparse
import pprint

def process_cmdline():
    default_queue_name = 'celery'
    parser = argparse.ArgumentParser(
        description='Tell all workers to stop consuming from the specified queue.' )
    parser.add_argument( '--discard_reserved', '-r', action='store_true',
        help='Also discard reserved tasks (default=%(default)s)' )
    parser.add_argument( '--discard_waiting', '-w', action='store_true',
        help='Also discard waiting tasks from queue (default=%(default)s)' )
    parser.add_argument( '--kill_active', '-k', action='store_true',
        help='Also active tasks that are currently running (default=%(default)s)' )
    parser.add_argument( '--unpause', '-u', action='store_true',
        help='Unpause tasks. (default=%(default)s)' )
    parser.add_argument( '--verbose', '-v', action='store_true' )
    parser.add_argument( 'queuenames', nargs=argparse.REMAINDER,
        help='Queue name(s) to stop consuming from. (default={0})'.format( 
            default_queue_name ) )
#    parser.set_defaults(
#        discard_reserved=False,
#        discard_waiting=False,
#        verbose=False,
#        unpause=False,
#        )
    args = parser.parse_args()
    if len( args.queuenames ) < 1:
        args.queuenames = [ default_queue_name ]
    return args


def process_results( results ):
    data = {}
    for item in results:
        for worker, status in item.iteritems():
            data[ worker ] = status
    return data
    

def do_unpause( args ):
    outfmt = '{name:25} {rv}'
    for q in args.queuenames:
        results = psync.app.control.add_consumer( q, reply=True )
        result_data_by_worker = process_results( results )
        for k in sorted( result_data_by_worker ):
            print( outfmt.format( name=k, rv=str( result_data_by_worker[ k ] ) ) )


def do_pause( args ):
    outfmt = '{name:25} {rv}'
    for q in args.queuenames:
        results = psync.app.control.cancel_consumer( q, reply=True )
        result_data_by_worker = process_results( results )
        for k in sorted( result_data_by_worker ):
            print( outfmt.format( name=k, rv=str( result_data_by_worker[ k ] ) ) )


def discard_reserved( args ):
    total_num_reserved = 0
    inspect = psync.app.control.inspect()
    reserved = inspect.reserved()
    for worker, reserved_list in reserved.iteritems():
        num_reserved = 0
        for task in reserved_list:
            if not task[ 'acknowledged' ]:
                result = psync.app.control.revoke( task[ 'id' ],
                                                   destination=( worker, ),
                                                   reply=True )
                if args.verbose:
                    print( result )
                num_reserved += 1
                total_num_reserved += 1
        print( '{0} Revoked {1} reserved tasks'.format( worker, num_reserved ) )
    print( '\nRevoked {0} reserved tasks in total\n'.format( total_num_reserved ) )


def kill_active( args ):
    total_num_active = 0
    inspect = psync.app.control.inspect()
    active = inspect.active()
    for worker, active_list in active.iteritems():
        print( "WORKER: {0}".format( worker ) )
        num_active = 0
        for task in active_list:
            result = psync.app.control.revoke( task[ 'id' ],
                                               destination=( worker, ),
                                               reply=True,
                                               terminate=True )
            if args.verbose:
                print( result )
            num_active += 1
            total_num_active += 1
        print( '{0} Killed {1} active tasks'.format( worker, num_active ) )
    print( '\nKilled {0} active tasks in total\n'.format( total_num_active ) )
            

def discard_waiting( args ):
    num_waiting = psync.app.control.discard_all()
    print( 'Discarded {0} waiting tasks'.format( num_waiting ) )


if __name__ == '__main__':
    args = process_cmdline()
    if args.unpause:
        do_unpause( args )
    else:
        do_pause( args )
        if args.discard_reserved:
            do_discard_reserved( args )
        if args.kill_active:
            do_kill_active( args )



# RETURN VALUE FROM app.control.revoke(... )
#[{u'psync_worker1@nid00013': {u'ok': u'tasks 2ec4591b-67c6-4175-bb95-e921c01019d6 flagged as revoked'}}]
#[{u'psync_worker1@nid00013': {u'ok': u'tasks f142fa55-06d1-4d56-a52c-bb5b51f0aaa2 flagged as revoked'}}]




# RETURN VALUE FROM app.control.inspect().reserved()
#{u'psync_worker1@nid00013': [{u'acknowledged': False,                                                    [164/4563]
#                              u'args': u"(<FSItem None /u/staff/aloftus/.cpan/sources>, <FSItem None /projects/test
#/psynctest/.cpan/sources>, {'minsecs': 3600}, {'synctimes': True, 'syncowner': False, 'syncgroup': False, 'syncperm
#s': True})",
#                              u'delivery_info': {u'exchange': u'celery',
#                                                 u'priority': 0,
#                                                 u'redelivered': None,
#                                                 u'routing_key': u'celery'},
#                              u'hostname': u'psync_worker1@nid00013',
#                              u'id': u'dc8367d4-a088-4203-b8d8-33b70efcdbd3',
#                              u'kwargs': u'{}',
#                              u'name': u'psync.sync_dir',
#                              u'time_start': None,
#                              u'worker_pid': None},
#                             {u'acknowledged': False,
#                              u'args': u"(<FSItem None /u/staff/aloftus/src/rpyc-3.2.2>, <FSItem None /projects/tes
#t/psynctest/src/rpyc-3.2.2>, {'minsecs': 3600}, {'synctimes': True, 'syncowner': False, 'syncgroup': False, 'syncpe
#rms': True})",
#                              u'delivery_info': {u'exchange': u'celery',
#                                                 u'priority': 0,
#                                                 u'redelivered': None,
#                                                 u'routing_key': u'celery'},
#                              u'hostname': u'psync_worker1@nid00013',
#                              u'id': u'b05bfe36-4a00-48da-a583-8d6b5062bedd',
#                              u'kwargs': u'{}',
#                              u'name': u'psync.sync_dir',
#                              u'time_start': None,
#                              u'worker_pid': None},
#                             ...
#                             ]
#}



# ACTIVE TASK
#{u'acknowledged': True,
# u'args': u"(<FSItem None /u/staff/csteffen/sf3dg_run/res_xspec_75580.sdb>, <FSItem None /projects/test/psynctest/csteffen/sf3dg_run/res_xspec_75580.sdb>, {'minsecs': 3600}, {'synctimes': True, 'syncowner': False, 'syncgroup': False, 'syncperms': True})",
# u'delivery_info': {u'exchange': u'celery',
#                    u'priority': 0,
#                    u'redelivered': None,
#                    u'routing_key': u'celery'},
# u'hostname': u'psync_worker1@nid00015',
# u'id': u'9d9cc9ec-135a-4fab-a2e9-e1487d36799a',
# u'kwargs': u'{}',
# u'name': u'psync.sync_dir',
# u'time_start': 3044048.406816009,
# u'worker_pid': 20040}
