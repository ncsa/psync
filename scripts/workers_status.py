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
parser.add_argument( '--showqueues', '-q', action='store_true',
    help='Show queue listeners' )
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

# get active_queues
activequeuenames = []
if args.showqueues:
    for worker, qlist in I.active_queues().iteritems():
        data[ worker ][ 'ACTIVEQUEUES' ] = qlist
        for q in qlist:
            activequeuenames.append( q[ 'name' ] )
qnames = set( activequeuenames )

# print summary
fmt = '{name:<25} {maxP:>9} {curP:>9} {numActv:>7} {numRsrv:>7}'
if args.showqueues:
    for name in qnames:
        fmt = fmt + ' {{{0}:>{1}}}'.format( name, len( name ) )

hdrs = dict( name   ='Worker', 
             maxP   ='maxPcount', 
             curP   ='curPcount', 
             numActv='NumActv', 
             numRsrv='NumRsrv'
             )
if args.showqueues:
    hdrs.update( { k:k for k in qnames } )
print( fmt.format( **hdrs ) )

totals = { 'name'   : 0,
           'maxP'   : 0,
           'curP'   : 0,
           'numActv': 0,
           'numRsrv': 0,
         }
if args.showqueues:
    totals.update( { k:0 for k in qnames } )

for name in sorted( data.keys() ):
    stats = data[ name ][ 'STATS' ]
    keys_vals = dict(  
        name    = name,
        maxP    = stats[ 'pool' ][ 'max-concurrency' ],
        curP    = len( stats[ 'pool' ][ 'processes' ] ),
        numActv = len( data[ name ][ 'ACTIVELIST' ] ),
        numRsrv = len( data[ name ][ 'RESERVEDLIST' ] )
        )
    if args.ignoreidle and keys_vals[ 'numActv' ] < 1 and keys_vals[ 'numRsrv' ] < 1:
        continue
    if args.showqueues:
        activequeues = [ d['name'] for d in data[ name ][ 'ACTIVEQUEUES' ] ]
        keys_vals.update( { k:'' for k in qnames } )
        keys_vals.update( { k:'*' for k in qnames if k in activequeues } )
    print( fmt.format( **keys_vals ) )
    if args.activedetails:
        print_active_details( data[ name ][ 'ACTIVELIST' ] )
    totals[ 'name' ]    += 1
    totals[ 'maxP' ]    += keys_vals[ 'maxP' ]
    totals[ 'curP' ]    += keys_vals[ 'curP' ]
    totals[ 'numActv' ] += keys_vals[ 'numActv' ]
    totals[ 'numRsrv' ] += keys_vals[ 'numRsrv' ]
    if args.showqueues:
        for qname in activequeues:
            totals[ qname ] += 1
print( '\nTotals:' )
print( fmt.format( **hdrs ) )
print( fmt.format( **totals ) )
