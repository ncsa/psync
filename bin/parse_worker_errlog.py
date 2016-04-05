#!/bin/env python

from __future__ import print_function
import argparse
import collections
import pprint
import pickle
import os
import re
import fileinput

log_msg_start = re.compile( '\[[\d-]{10} [\d:,]{13} ([A-Z]+)/([a-zA-Z]+)\] ')

# Messages that are part of startup/shutdown
# or that are already reported in psync_service logs (and can be ignored here)
#    'clocks are out of sync'
#    '^$'
#    '|' 'Got shutdown from remote'
ignore_msgs = re.compile( 
    'CDeprecationWarning'
    '|' '@(nid|ie)\d+ ready.$'
    '|' "OSError\(17, 'File exists'\)"
    '|' "Got shutdown from remote"
    '|' "Can't shrink pool"
    '|' " (INFO|DEBUG)/MainProcess\]"
    '|' "clocks are out of sync"
    )

# known exceptions
known_exceptions = re.compile( 
    "exited with 'signal 9 \(SIGKILL\)'"
    '|' "OSError\(12, 'Cannot allocate memory'\)"
    '|' 'time limit \(\d+.0s\) exceeded'
    '|' 'clocks are out of sync'
    '|' 'raised unexpected: .+$'
    '|' 'UnicodeDecodeError'
    '|' 'Cannot connect to amqp'
    )

def process_cmdline():
    parser = argparse.ArgumentParser()
    parser.add_argument( '--show', '-s', type=int, metavar='N',
        help="Show details for error number N (in list of errors) and exit" )
    parser.add_argument( '--limit', '-l', type=int, metavar='N',
        help="Limit output to show only N number of errors" )
    parser.add_argument( '--picklefile', '-p', 
        help="""If PICKLEFILE exists, read data from it.
            Otherwise, operate as normal and save data to PICKLEFILE.""" )
    parser.add_argument( '--showall', '-a', action='store_true',
        help="Show raw error data for each error type" )
    parser.add_argument('files', metavar='FILE', nargs='*', 
        help='files to read, if empty, stdin is used')
    default_options = {
        "show": 0,
        "limit": 0,
        "picklefile": None,
        "showall": False,
    }
    parser.set_defaults( **default_options )
    args = parser.parse_args()
    return args


def get_error_signature( lines ):
    relevant_lines = []
    first_line = lines[ 0 ]
    match = log_msg_start.match( first_line )
    err_type = match.group( 1 )
    err_module = match.group( 2 )
    relevant_lines.extend( [ err_type, ' ', err_module, ' ' ] )
    match = known_exceptions.search( first_line )
    if match:
        #type is exception caught
        relevant_lines.append( match.group( 0 ) )
        for L in lines:
            if L.startswith( '  File ' ) \
            and 'trace_task' not in L \
            and '__protected_call__' not in L:
               relevant_lines.append( L )
    else:
        raise UserWarning( "Unknown log message type: {0}".format( ''.join( lines ) ) )
    return ''.join( relevant_lines )


def ignore_msg( lines ):
#    return bool( ignore_msgs.search( ''.join( lines ) ) )
    return bool( ignore_msgs.search( lines[0] ) )


def process_error_msg( error_dict, lines ):
    if not ignore_msg( lines ):
        es = get_error_signature( lines )
        if es not in error_dict:
            error_dict[ es ] = { 'data': lines, 'count': 0 }
        error_dict[ es][ 'count' ] += 1


def parse_files( filelist ):
    errors = collections.OrderedDict()
    lines = []
    for l in fileinput.input( 
        files=filelist if len( filelist ) > 0 else ( '-', ) 
        ) :
        match = log_msg_start.match( l )
        if match and len( lines ) > 0:
            process_error_msg( errors, lines )
            lines = []
        lines.append( l )
    if len( lines ) > 0:
        process_error_msg( errors, lines )
    return errors


def format_output( errors, args ):
    output = []
    total_error_count = 0
    err_indices = { i: e for i, e in enumerate( errors, start=1) }
    if args.show > 0:
        e = err_indices[ args.show ]
        qty = errors[e][ 'count' ]
        lines = errors[e][ 'data' ]
        output.append( 'Error # {0:02d}  Qty:{1}'.format( args.show, qty ) )
        output.append( '='*50 )
        output.append( e )
        output.append( '-'*50 )
        output.append( ''.join( lines ) )
        output.append( '' )
    else:
        for i, e in err_indices.iteritems():
            qty = errors[e][ 'count' ]
            total_error_count += qty
            output.append( 'Error # {0:02d}  Qty:{1}'.format( i, qty ) )
            output.append( '='*20 )
            output.append( e )
            if args.showall:
                lines = errors[e][ 'data' ]
                output.append( '-'*50 )
                output.append( ''.join( lines ) )
            output.append( "" )
        output.append( "" )
        output.append( '='*20 )
        output.append( "Total Error Count: {0}".format( total_error_count ) )
        output.append( '='*20 )
    return '\n'.join( output )


if __name__ == "__main__":
    args = process_cmdline()
    if args.picklefile and os.path.exists( args.picklefile ):
        with open( args.picklefile, 'rb' ) as f:
            errors = pickle.load( f )
    else:
        errors = parse_files( args.files )
    print( format_ooutput( errors, args ) )
#    if args.show > 0:
#        e = err_indices[ args.show ]
#        qty = errors[e][ 'count' ]
#        lines = errors[e][ 'data' ]
#        print( 'Error # {0:02d}  Qty:{1}'.format( args.show, qty ) )
#        print( '='*50 )
#        print( e )
#        print( '-'*50 )
#        print( ''.join( lines ) )
#        print( '' )
#    else:
#        for i, e in err_indices.iteritems():
#            qty = errors[e][ 'count' ]
#            total_error_count += qty
#            print( 'Error # {0:02d}  Qty:{1}'.format( i, qty ) )
#            print( '='*20 )
#            print( e )
#            if args.showall:
#                lines = errors[e][ 'data' ]
#                print( '-'*50 )
#                print( ''.join( lines ) )
#            print( "" )
#        print( "" )
#        print( '='*20 )
#        print( "Total Error Count: {0}".format( total_error_count ) )
#        print( '='*20 )
    if args.picklefile and not os.path.exists( args.picklefile ):
        with open( args.picklefile, 'wb' ) as f:
            pickle.dump( errors, f )
