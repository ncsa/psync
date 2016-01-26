#!/bin/env python

import psync
import re
import pprint


class ActiveTask( object ):
    re_repr = re.compile( '<FSItem [^ ]+ ([^>]+)>' )
    def __init__( self, t_id, t_name, t_args, t_kwargs ):
        self.id = t_id
        self.name = t_name
        self.args = self.re_repr.findall( t_args )
        self.kwargs = t_kwargs

    def __repr__( self ):
        return "<{cl} ({tn} {a0})>".format(
            cl=self.__class__.__name__, tn=self.name, a0=self.args[0])


def inspect_workers():
    workers = {}
    i = psync.app.control.inspect()
    a = i.active()
    if a:
        for k, activelist in a.iteritems():
            if len( activelist ) > 0:
                workers[ k ] = []
                for t in activelist:
                    workers[ k ].append( ActiveTask( t['id'], t['name'],
                        t['args'], t['kwargs'] ) )
    return workers


def print_data( workers ):
    pprint.pprint( workers, indent=2 )


def run():
    data = inspect_workers()
    if len( data ) > 0:
        print_data( data )
    else:
        print( 'No workers found.' )


if __name__ == '__main__':
    run()
