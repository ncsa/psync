import psync
import argparse
import pprint
import sys
import math
import logging
import time

def process_cmdline():
    help_txt = """
        For dry-run, set max-iterations to 0 (zero).
    """
    parser = argparse.ArgumentParser( epilog=help_txt )
    parser.add_argument( '--max-iterations', '-x', type=int, metavar='N',
        help="Never try more than X times to adjust pool size. (default is largest adjustment size to make)" )
    parser.add_argument( '--pause-amount', '-p', type=int, metavar='P',
        help="Pause for P secs between iterations. (default=%(default)s)." )
    group = parser.add_mutually_exclusive_group( required=True )
    group.add_argument( '--setsize', '-s', type=int, metavar='N',
        help='Exactly N processes are running.' )
    group.add_argument( '--multiple', '-m', type=float, metavar='N',
        help='Current process count * N.' )
    group.add_argument( '--increment', '-i', type=int, metavar='N',
        help='Increment current process count by N. Use a negative number for decrement.' )
    default_options = {
        'max_iterations': None,
        'pause_amount': 2
    }
    parser.set_defaults( **default_options )
    args = parser.parse_args()
    return args


def get_cur_worker_stats():
    workers = {}
    worker_stats = psync.app.control.inspect().stats()
    if worker_stats is not None:
        for workername, stats in worker_stats.iteritems():
            workers[ workername ] = {
                'maxPcount': stats[ 'pool' ][ 'max-concurrency' ],
                'curPcount': len( stats[ 'pool' ][ 'processes' ] ),
                }
    return workers
    

def calc_adjustment_size( worker_stats, args ):
    for worker, stats in worker_stats.iteritems():
        max = stats[ 'maxPcount' ]
        cur = stats[ 'curPcount' ]
        adjustment = 0
        if args.setsize:
            adjustment = args.setsize - cur
        elif args.increment:
            adjustment = args.increment
        elif args.multiple:
            adjustment = int( math.floor( args.multiple * cur ) )
        result_size = cur + adjustment
        if result_size > max:
            adjustment = max - cur
        elif result_size < 1:
            adjustment = 1 - cur
        stats[ 'adjustment' ] = adjustment
        stats[ 'tgtPcount' ] = cur + adjustment


def try_adjustments( worker_stats ):
    # Create list of workers for each adjustment value
    adjustments = {}
    for worker, stats in worker_stats.iteritems():
        adj_size = stats[ 'adjustment' ]
        if adj_size not in adjustments:
            adjustments[ adj_size ] = []
        adjustments[ stats[ 'adjustment' ] ].append( worker )
    for adj, workerlist in adjustments.iteritems():
        action = 'pool_grow'
        if adj < 0:
            action = 'pool_shrink'
        if adj == 0:
            continue
        response = psync.app.control.broadcast(
            action,
            n=adj,
            destination=workerlist,
            reply=True,
            timeout=60
        )
# INFO:[{u'worker1@ie09': {u'ok': u'pool will shrink'}}]
        for resp in response:
            for worker, data in resp.iteritems():
                for status, reason in data.iteritems():
                    msg = "{0}: {1} {2}".format( worker, status, reason )
                    logging.info( msg )
                    if status != 'ok':
                        raise UserWarning( msg )


def show_summary( old, new ):
    fmt = '{0:25} {1:>9} {2:>7} {3:>9} {4:>9} {5:>9}'
    hdrs = [ 'Worker', 'oldPCount', 'AdjSize', 'newPcount', 'tgtPcount', 'maxPcount' ]
    print( fmt.format( *hdrs ) )
    for worker, oldstats in old.iteritems():
        if worker not in new:
            logging.warning( '{0} not found in new stats list'.format( worker ) )
        print( fmt.format( 
            worker,
            oldstats[ 'curPcount' ],
            oldstats[ 'adjustment' ],
            new[ worker ][ 'curPcount' ],
            oldstats[ 'tgtPcount' ],
            oldstats[ 'maxPcount' ]
            )
        )


def run():
    args = process_cmdline()
    orig_stats = get_cur_worker_stats()
    if len( orig_stats ) < 1:
        sys.exit( 'No workers found' )
    calc_adjustment_size( orig_stats, args )
    if args.max_iterations is None:
        max_iter = max( [ abs( orig_stats[k]['adjustment'] ) for k,v in orig_stats.iteritems() ] )
        args.max_iterations = max_iter
    new_stats = orig_stats
    keep_going = True
    itercount = 0
    while keep_going:
        if itercount >= args.max_iterations:
            logging.warning( "Max iterations reached." )
            keep_going = False
            break
        old_stats = new_stats
        calc_adjustment_size( old_stats, args )
        try_adjustments( old_stats )
        time.sleep( args.pause_amount )
        new_stats = get_cur_worker_stats()
#        show_summary( old_stats, new_stats )
        # check if tgt has been met
        for worker, stats in old_stats.iteritems():
            if worker not in new_stats:
                del new_stats[ worker ]
            if new_stats[ worker ][ 'curPcount' ] == orig_stats[ worker ][ 'tgtPcount' ]:
                del new_stats[ worker ]
        new_size = len( new_stats )
        if new_size > 0:
            logging.debug( "{0} workers still out of bounds.".format( new_size ) )
        else:
            keep_going = False
            logging.info( "Success! All workers are at expected size." )
        itercount = itercount + 1
    new_stats = get_cur_worker_stats()
    show_summary( orig_stats, new_stats )


if __name__ == '__main__':
    logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.INFO)
    run()
