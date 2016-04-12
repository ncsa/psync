from __future__ import print_function
import psync
import sys
import argparse
import pprint


def print_active_details( dlist ):
    for e in dlist:
        print( '  Name: {0}\n  Args: {1}'.format( 
            pprint.pformat( e['name'] ),
            pprint.pformat( e['args'] ) ) )


data = {}

parser = argparse.ArgumentParser()
parser.add_argument( '--ignoreidle', '-i', action='store_true',
    help='Show only workers with active tasks' )
parser.add_argument( '--activedetails', '-d', action='store_true',
    help='Show details of active tasks' )
#parser.set_defaults( ignoreidle=False )
args = parser.parse_args()

I = psync.app.control.inspect()

# get per worker stats
worker_stats = I.stats()
if worker_stats is None:
    sys.exit( 'No active workers found.' )
for worker, stats in worker_stats.iteritems():
    data[ worker ] = dict( STATS=stats )

# get per worker active tasks
for worker, activelist in I.active().iteritems():
    data[ worker ][ 'ACTIVELIST' ] = activelist

# get per worker reserved tasks
for worker, reservedlist in I.reserved().iteritems():
    data[ worker][ 'RESERVEDLIST' ] = reservedlist

# print summary
fmt = '{name:<25} {maxP:>9} {curP:>9} {inQa:>8} {inQt:>8} {numActv:>7} {numRsrv:>7}'
#fmt = '{name:<25} {maxP:>9} {curP:>9} {numActv:>7} {numRsrv:>7}'

hdrs = dict( name='Worker', 
             maxP='maxPcount', 
             curP='curPcount', 
             inQa='InQ-actv',
             inQt='InQ-tot', 
             numActv='NumActv', 
             numRsrv='NumRsrv'
             )
print( fmt.format( **hdrs ) )

totals = { 'name'   : 0,
           'maxP'   : 0,
           'curP'   : 0,
           'inQa'   : 0,
           'inQt'   : 0,
           'numActv': 0,
           'numRsrv': 0,
         }

for name in sorted( data.keys() ):
    stats = data[ name ][ 'STATS' ]
    max_procs = stats[ 'pool' ][ 'max-concurrency' ]
    cur_procs = len( stats[ 'pool' ][ 'processes' ] )
    inq_active = stats[ 'pool' ][ 'writes' ][ 'inqueues' ][ 'active' ]
    inq_total = stats[ 'pool' ][ 'writes' ][ 'inqueues' ][ 'total' ]
    numActive = len( data[ name ][ 'ACTIVELIST' ] )
    numReserved = len( data[ name ][ 'RESERVEDLIST' ] )
    if args.ignoreidle and numActive < 1 and numReserved < 1:
        continue
    print( fmt.format( 
        name=name,
        maxP=max_procs,
        curP=cur_procs,
        inQa=inq_active,
        inQt=inq_total,
        numActv=numActive,
        numRsrv=numReserved
        )
    )
    if args.activedetails:
        print_active_details( data[ name ][ 'ACTIVELIST' ] )
    totals[ 'name' ] += 1
    totals[ 'maxP' ] += max_procs
    totals[ 'curP' ] += cur_procs
    totals[ 'inQa' ] += inq_active
    totals[ 'inQt' ] += inq_total
    totals[ 'numActv' ] += numActive
    totals[ 'numRsrv' ] += numReserved
print( '\nTotals:' )
print( fmt.format( **hdrs ) )
print( fmt.format( **totals ) )
