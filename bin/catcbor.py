#!/bin/env python

from __future__ import print_function
import cbor
import pprint
import sys
import argparse
import collections
import ConfigParser
import logging


def process_cmdline():
    parser = argparse.ArgumentParser()
    parser.add_argument( 'infile' )
    parser.add_argument( '--head', '-H', type=int, metavar='N',
        help='only print N records from the beginning of the file' )
    parser.add_argument( '--tail', '-T', type=int, metavar='N',
        help='only print N records from the end of the file' )
    parser.add_argument( '--ini', action='store_true',
        help='format output in INI style' )
    parser.add_argument( '--raw', '-r', action='store_true',
        help='output raw cbor data '
             '(requires --outfile) '
             '(combine with -H to obtain a small sample of a cbor file)' )
    parser.add_argument( '--outfile', '-o',
        help='write output to OUTFILE ' )
    default_options = {
        'tail': 0,
        'head': 0,
        'outfile': None,
    }
    parser.set_defaults( **default_options )
    args = parser.parse_args()
    if args.raw and not args.outfile:
        raise UserWarning( "'raw' option requires an 'outfile'" )
    return args


def do_print( items, args ):
    if args.raw:
        print_raw( items, args )
    elif args.ini:
        print_ini( items, args )
    else:
        print_std( items, args )


def print_std( items, args ):
    for item in items:
        pprint.pprint( item )


def print_raw( items, args ):
    with open( args.outfile, 'wb' ) as f:
        for item in items:
            cbor.dump( item, f )


def print_ini( items, args ):
    cfg = ConfigParser.RawConfigParser()
    for i in range( 1, len( items ) + 1 ):
        s = str( i )
        cfg.add_section( s )
        for k,v in items.popleft().iteritems():
            cfg.set( s, str( k ), str( v ) )
    cfg.write( sys.stdout )

def run( args ):
    count = 0
    maxlen = 0
    items = collections.deque()
    if args.head > 0:
        items = collections.deque( maxlen=args.head )
        maxlen = args.head
    elif args.tail > 0:
        items = collections.deque( maxlen=args.tail )
    with open( args.infile, 'rb' ) as f:
        try:
            while (1):
                rec = cbor.load( f )
                items.append( rec )
                count += 1
                if count == maxlen:
                    break
        except ( EOFError ) as e:
            pass
        except ( ValueError ) as e:
            logging.warning( 'Error reading from file, input file may be corrupt. '
                          'Using only valid data that was read up to this point.' )
    do_print( items, args )

if __name__ == '__main__':
    args = process_cmdline()
    run( args )
