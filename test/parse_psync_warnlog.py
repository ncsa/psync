#!/bin/env python

from __future__ import print_function

import pprint
import io
import csv
import os
import re
import cbor
import logging
import argparse
import pickle
import collections

logr = logging.getLogger( __name__ )

class PsyncWarning( object ):
    re_errtypes = re.compile( 'LustreStripeInfoError'
                          '|' 'Checksum mismatch'
                          '|' 'No such file or directory'
                          '|' 'Setstripe failed'
                          '|' 'file has vanished'
                          '|' 'get_xattr_data'
                          '|' 'Cannot send after transport endpoint shutdown'
                          '|' 'No such device'
                          '|' 'Input/output error'
                          )
    detail_keys = ( 'synctype', 'msgtype', 'action', 'error', 'src', )

    def __init__( self, dict_record ):
        self.keys = []
        for k in self.detail_keys:
            setattr( self, k, None )
        for k in dict_record:
            setattr( self, k, dict_record[ k ] )
            self.keys.append( k )
        errtype = self.parse_errtype( dict_record )
        if not errtype:
            print( "NO ERRTYPE FOUND FOR ..." )
            pprint.pprint( dict_record )
            raise SystemExit()
        self.errtype = errtype

    def parse_errtype( self, dict_record ):
        errtype = None
        if 'error' in dict_record:
            try:
                m = self.re_errtypes.search( dict_record[ 'error' ] )
            except ( TypeError ) as e:
                print( "caught TypeError" )
                pprint.pprint( dict_record )
                raise SystemExit()
            if m:
                errtype = m.group()
        elif 'action' in dict_record:
            errtype = self.msgtype + ' ' + self.action
        return errtype

    def __str__( self ):
        return '<{cl} ({mt}) ({st}) ({et}) ({e})>'.format( 
            cl=self.__class__.__name__,
            mt=self.msgtype,
            st=self.synctype,
            et=self.errtype,
            e=self.error )

    __repr__ = __str__

    @classmethod
    def csv_headers( cls ):
        output = io.BytesIO()
        writer = csv.writer( output )
        writer.writerow( [ 'timestamp',
                           'host',
                           'synctype',
                           'errtype',
                           'src-fullpath',
                           'src-filename',
                           'tgt-fullpath',
                           'tgt-filename',
                           'error' ] )
        return output.getvalue()

    def as_csv( self ):
        src_bn = os.path.basename( self.src )
        tgt_bn = os.path.basename( self.tgt )
        output = io.BytesIO()
        writer = csv.writer( output )
        writer.writerow( [ self.ts, 
                           self.host,
                           self.synctype,
                           self.errtype, 
                           self.src,
                           src_bn,
                           self.tgt,
                           tgt_bn,
                           self.error ] )
        return output.getvalue()

    def message( self ):
        return pprint.pformat( dict( src=self.src ) )

    def details( self ):
        return pprint.pformat( { k: getattr( self, k ) for k in self.detail_keys } )
#        d = {}
#        for k in [ 'synctype', 'msgtype', 'action', 'error', 'src' ]:
#            d[ k ] = getattr( self, k )
#        return pprint.pformat( d )

    def raw( self ):
        return pprint.pformat( { k: getattr( self, k ) for k in self.keys } )


def process_cmdline():
    parser = argparse.ArgumentParser()
    parser.add_argument( 'infile' )
    picklegroup = parser.add_argument_group( title='Pickling options',
        description="""Specifying -n and -p at the same time will cause the source
            file to be re-parsed and a new pickle file created.""")
    picklegroup.add_argument( '--nopicklein', '-n', action='store_false', dest='picklein',
        help="Don't read from pickled data file" )
    picklegroup.add_argument( '--pickle', '-p', action='store_true', dest='pickleout',
        help='Save pickled data in INFILE.pickle, clobbering an existing file' )
    outputgroup = parser.add_argument_group( title='Output Details' )
    outputgroup.add_argument( '--message', '-m', action='store_true',
        help="Show one-line message for each instance of error type" )
    outputgroup.add_argument( '--details', '-d', action='store_true',
        help="Show details for each instance of error type" )
    outputgroup.add_argument( '--raw', '-r', action='store_true',
        help="""Show raw exception for each error type.
            Note: Raw exception is stored only once, from the first instance of
            type, for space and time saving reasons.""" )
    parser.add_argument( '--anydetails', action='store_true', 
        help=argparse.SUPPRESS )
    limitgroup = parser.add_mutually_exclusive_group()
    limitgroup.add_argument( '--show', '-s', type=int, metavar='N',
        help="Show details for error number N (in list of errors) and exit" )
    limitgroup.add_argument( '--include', '-i', action='append', metavar='INC',
        help="""Show only errors with type matching INC. 
            Can be specified multiple times.""" )
    limitgroup.add_argument( '--exclude', '-e', action='append', metavar='EXC',
        help="""Show errors where type does NOT match EXC. 
            Can be specified multiple times.""" )
    default_options = {
        "picklein": True,
        "pickleout": False,
        "message": False,
        "details": False,
        "raw": False,
#        "anydetails": False,
    }
    parser.set_defaults( **default_options )
    args = parser.parse_args()
#    if args.message or args.details:
#        args.anydetails = True
    return args


def process_warning( rec, warnings ):
    if not 'msgtype' in rec:
        pprint.pprint( rec )
        raise UserWarning( "KeyError: 'msgtype' not found in record" )
#    if rec[ 'msgtype' ] == 'skipentry':
#        return
    #pprint.pprint( rec )
    #print( PsyncWarning( rec ) )
    #raise SystemExit( 'Forced Exit' )
    new_w = PsyncWarning( rec )
    wtype = new_w.errtype
    if wtype not in warnings:
        warnings[ wtype ] = []
    warnings[ wtype ].append( new_w )


def process_file( infile ):
    warnings = collections.OrderedDict()
    with open( infile, 'rb' ) as f:
        try:
            while True:
                rec = cbor.load( f )
                process_warning( rec, warnings )
        except ( EOFError ):
            pass
    return warnings


def print_single_warning( num, sig, data, args ):
    qty = len( data )
    print( '' )
    print( 'Warning # {0:02d}  Qty:{1}'.format( num, qty ) )
    print( '='*22 )
    print( sig )
    if args.message:
        print( '-'*50 )
        for w in data:
            print( w.message() )
    if args.details:
        print( '-'*50 )
        for w in data:
            print( w.details() )
    elif args.raw:
        print( '-'*50 )
        for w in data:
            print( w.raw() )


def print_all( all_warnings, args ):
    w_indices = { i: w for i, w in enumerate( all_warnings, start=1 ) }
    if args.show:
        # Show only the requested warning number
        k = w_indices[ args.show ]
        print_single_warning( args.show, k, all_warnings[ k ], args )
    else:
        total_error_count = 0
        for i, w_sig in w_indices.iteritems():
            # Print warnings by default
            print_ok = True
            if args.include:
                # limit by inclusion
                print_ok = False
                if any( x in w_sig for x in args.include ):
                    print_ok = True
            if args.exclude:
                # limit by exclusion
                print_ok = True
                if any( x in w_sig for x in args.exclude ):
                    print_ok = False
            if print_ok:
                qty = len( all_warnings[ w_sig ] )
                total_error_count += qty
                print_single_warning( i, w_sig, all_warnings[w_sig], args )
        print( '' )
        fmt = "Total Warning Count: {0}"
        sz = len( fmt ) - 3 + len( str( total_error_count ) )
        print( '='*sz )
        print( fmt.format( total_error_count ) )
        print( '='*sz )

#    print( PsyncWarning.csv_headers(), end='' )
#    for k, v in all_warnings.iteritems():
#        print( 'ERRTYPE: {0}  COUNT: {1} '.format( k, len( v ) ) )
#    for x in all_warnings:
#        print( x.as_csv(), end='' )
##        if x.errtype == 'Setstripe failed':
##            print( x.src )
#        print( x.errtype )


if __name__ == "__main__":
    loglvl = logging.WARNING
    logging.basicConfig( level=loglvl )
    args = process_cmdline()
    head, tail = os.path.split( args.infile )
    pickle_fn = os.path.join( head, '{0}.pickle'.format( tail ) )
    if args.picklein and os.path.exists( pickle_fn ):
        with open( pickle_fn, 'rb' ) as f:
            warnings = pickle.load( f )
    else:
        warnings = process_file( args.infile )
    if args.pickleout:
        with open( pickle_fn, 'wb' ) as f:
            pickle.dump( warnings, f )

    print_all( warnings, args )
