#!/bin/env python

import argparse
import collections
import pprint
import pickle
import os
import re
import cbor
import logging


logr = logging.getLogger( __name__ )


# Exception type is part of the error signature
err_type_re_signature = { 
    "<type 'exceptions.OSError'>": re.compile( '([^:]+):?' ),
    "<type 'exceptions.IOError'>": re.compile( '([^:]+):?' ),
    "<class 'runcmd.Run_Cmd_Error'>": 
        re.compile( '<Run_Cmd_Error \((code=.+msg=[^:/]+).*:(.+)\n' ),
    "<class 'billiard.exceptions.SoftTimeLimitExceeded'>": re.compile( '(.*)' ),
}


# Traceback lines to skip in error signature
re_traceback_ignore = re.compile( 
  '/(subprocess|os|genericpath|posixpath).py", ' +
  '|' + 'logging/__init__.py", ' +
  '|' + 'billiard/pool.py", ' +
  '|' + 'celery/app/(task|trace).py", ' )


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
        help="Show raw exception for each error type." )
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
        "message": False,
        "details": False,
        "raw": False,
        "anydetails": False,
    }
    parser.set_defaults( **default_options )
    args = parser.parse_args()
    if args.message or args.details:
        args.anydetails = True
    return args


def get_error_signature( rec ):
    etype = rec[ 'exception_type' ]
    exception = rec[ 'exception' ]
    try:
        re_pattern = err_type_re_signature[ etype ]
    except ( KeyError ) as e:
        logr.error( 'ERROR while parsing record:\n{0}\n'.format( pprint.pformat( rec ) ) )
        raise e
    msg = ('____ Looking for signature match in exception:\n'
           '{e}\n'
           '____ for exception type:\n'
           '{etype}').format( e = exception, etype = etype )
    logr.debug( msg )
    match = re_pattern.match( exception )
    if not match:
        raise UserWarning( 'No match found...\n{msg}'.format( msg = msg ) )
    relevant_parts = [ etype, ' ' ]
    logr.debug( 'Matches: {m}'.format( m = pprint.pformat( match.groups() ) ) )
    relevant_parts.append( ''.join( match.groups() ) + '\n' )
    for L in rec[ 'traceback' ].splitlines():
        if L.startswith( '  File ' ) \
        and not re_traceback_ignore.search( L ):
           relevant_parts.append( L + '\n' )
    return ''.join( relevant_parts )


def process_error_record( errdict, rec ):
    e_sig = get_error_signature( rec )
    e_msg = rec[ 'exception' ]
#    e_details = rec
    if e_sig not in errdict:
        errdict[ e_sig ] = { 'instances': [] }
    errdict[ e_sig ][ 'instances' ].append( rec )


def process_file( infile ):
    errors = collections.OrderedDict()
    with open( infile, 'rb' ) as f:
        try:
            while True:
                rec = cbor.load( f )
                process_error_record( errors, rec )
        except ( EOFError ):
            pass
    return errors


def print_single_error( num, sig, data, args ):
    qty = len( data[ 'instances' ] )
    print( '' )
    print( 'Error # {0:02d}  Qty:{1}'.format( num, qty ) )
    print( '='*22 )
    print( sig )
    if args.raw:
        print( '-'*50 )
        rec = data[ 'instances' ][ 0 ]
        for k in [ 'exception_type', 'exception', 'args', 'traceback' ]:
            print( '{k}: {v}'.format( k=k, v=rec[ k ] ) )
    if args.anydetails:
        for i in data[ 'instances' ]:
            print( '-'*50 )
            if args.message:
                print( i[ 'exception' ] )
            if args.details:
                for k in [ 'args' ]:
                    print( '{k}: {v}'.format( k=k, v=i[ k ] ) )

def print_errors( errdict, args ):
    err_indices = { i: e for i, e in enumerate( errdict, start=1) }
    if args.show:
        # Show only the requested error
        e = err_indices[ args.show ]
        print_single_error( args.show, e, errdict[e], args )
    else:
        total_error_count = 0
        for i, e_sig in err_indices.iteritems():
            # Print errors by default
            print_ok = True
            if args.include:
                # limit errors by inclusion
                print_ok = False
                if any( x in e_sig for x in args.include ):
                    print_ok = True
            if args.exclude:
                # limit errors by exclusion
                print_ok = True
                if any( x in e_sig for x in args.exclude ):
                    print_ok = False
            if print_ok:
                qty = len( errdict[ e_sig ][ 'instances' ] )
                total_error_count += qty
                print_single_error( i, e_sig, errdict[ e_sig ], args )
        print( "" )
        fmt = "Total Error Count: {0}"
        sz = len( fmt ) - 3 + len( str( total_error_count ) )
        print( '='*sz )
        print( fmt.format( total_error_count ) )
        print( '='*sz )


if __name__ == "__main__":
    loglvl = logging.WARNING
    logging.basicConfig( level=loglvl )
    args = process_cmdline()
    head, tail = os.path.split( args.infile )
    pickle_fn = os.path.join( head, '{0}.pickle'.format( tail ) )
    if args.picklein and os.path.exists( pickle_fn ):
        with open( pickle_fn, 'rb' ) as f:
            errors = pickle.load( f )
    else:
        errors = process_file( args.infile )
    print_errors( errors, args )
    if args.pickleout:
        with open( pickle_fn, 'wb' ) as f:
            pickle.dump( errors, f )
