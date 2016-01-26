#!/bin/env python

import psync
import argparse
import pprint


def inspect_workers():
    workers = {}
    i = psync.app.control.inspect()
    a = i.active()
    if a:
        for k, activelist in a.iteritems():
            if k not in workers:
                workers[ k ] = { 'num_active': 0, 'num_reserved': 0 }
            workers[ k ][ 'num_active' ] = len( activelist )

    v = i.reserved()
#    pprint.pprint( v )
    if v:
        for k, reservedlist in a.iteritems():
            if k not in workers:
                workers[ k ] = { 'num_active': 0, 'num_reserved': 0 }
            workers[ k ][ 'num_reserved' ] = len( reservedlist )
    return workers

def print_data( workers ):
    total_active = 0
    total_reserved = 0
    fmt = '{W:25} {A:6} {V:8}'
    print( fmt.format( W='Worker', A='Active', V='Reserved' ) )
    for k in sorted( workers ):
        d = workers[k]
        total_active += d[ 'num_active' ]
        total_reserved += d[ 'num_reserved' ]
        print( fmt.format( W=k, A=d[ 'num_active' ], V=d[ 'num_reserved' ] ) )
    print( '' )
    print( fmt.format( W='Totals:', A=total_active, V=total_reserved ) )


def run():
    data = inspect_workers()
    if len( data ) > 0:
        print_data( data )
    else:
        print( 'No workers found.' )

if __name__ == '__main__':
    run()
