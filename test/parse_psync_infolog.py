#!/bin/env python
from __future__ import print_function
import cbor
import argparse
import datetime
import time
import pprint
import collections
import logging

logr = logging.getLogger( __name__ )


def process_cmdline():
    parser = argparse.ArgumentParser()
    parser.add_argument( 'infile' )
    parser.add_argument( '--inodes', '-i', type=int, metavar='N',
        help='Source file system has N inodes total. '
             'Used to estimate completion progress.' )
    default_options = {
        'inodes': 124674897,
    }
    parser.set_defaults( **default_options )
    args = parser.parse_args()
    return args


def process_start_end_times( rec, time_data ):
    newts = rec[ 'ts' ]
    if newts < time_data[ 'start_ts' ]:
        time_data[ 'start_ts' ] = newts
    elif newts > time_data[ 'end_ts' ]:
        time_data[ 'end_ts' ] = newts



def count_sync_types( rec, sync_types ):
    stype = rec[ 'synctype' ]
    mtype = 'None'
    try:
        mtype = rec[ 'msgtype' ]
    except ( KeyError ) as e:
        pass
    if stype not in sync_types:
        sync_types[ stype ] = {}
    sdata = sync_types[ stype ]
    if mtype not in sdata:
        sdata[ mtype ] = 0
    sdata[ mtype ] += 1


def process_syncdir_stats( rec, syncdir_data ):
    dir_data = syncdir_data[ 'dir_data' ]
    dups = syncdir_data[ 'dups' ]
    working = syncdir_data[ 'working' ]
    if rec[ 'synctype' ] != 'SYNCDIR':
        return
    ts = rec[ 'ts' ]
    msgtype = rec[ 'msgtype' ]
    src = rec[ 'src' ]
    if src in dups:
        return
    if msgtype == 'start':
        if src in dir_data or src in working or src in dups:
            dups[ src ] = parts
            return
        working[ src ] = { 'start': ts,
                           'num_src_dirs': 0,
                           'num_src_files': 0,
                           'num_src_symlinks': 0,
                           'num_tgt_dirs': 0,
                           'num_tgt_files': 0,
                           'num_tgt_symlinks': 0,
                           'srctot': 0,
                           'end': 0,
                           'elapsed': 999999,
                           }
        dir_data[ src ] = working[ src ]
    elif msgtype == 'info':
        working[ src ] [ 'srctot' ] = 0
        for k in [ 'num_src_dirs', 'num_src_files', 'num_src_symlinks' ]:
            working[ src ][ k ] = rec[ k ]
            working[ src ] [ 'srctot' ] += rec[ k ]
        for k in [ 'num_tgt_dirs', 'num_tgt_files', 'num_tgt_symlinks' ]:
            working[ src ][ k ] = rec[ k ]
    elif msgtype == 'end':
        working[ src ][ 'end' ] = ts
        working[ src ][ 'elapsed' ] = ts - working[ src ][ 'start' ]
        del working[ src ]
    else:
        raise UserWarning( "Unknown msgtype '{0}' for record '{1}'".format(
            msgtype, rec ) )


def print_psync_summary( args, time_data, sync_types, total_rec_count ):
    start_time = datetime.datetime.fromtimestamp( time_data[ 'start_ts' ] )
    end_time = datetime.datetime.fromtimestamp( time_data[ 'end_ts' ] )
    elapsed = end_time - start_time
    inodes_completed = 0
    for k,v in sync_types.iteritems():
        if 'end' in v:
            inodes_completed += v[ 'end' ]
    pct_complete_by_inodes = inodes_completed * 100.0 / args.inodes
    pct_rate = pct_complete_by_inodes / elapsed.total_seconds() * 3600
    eta_complete = ( 100.0 - pct_complete_by_inodes ) / pct_rate
    psync_summary_outfile = args.infile + '.summary'
    with open( psync_summary_outfile, 'w' ) as f:
        print( 
            'Record counts: {rc}\n'
            'Total log record count: {tlrc}\n'
            'Start time: {st_ts} ({st})\n'
            'End time: {et_ts} ({et})\n'
            'Elapsed Time: {el}\n'
            'Inodes completed : {icnt}\n'
            'Total inodes: {itotal}\n'
            'Percent Complete: {pct_c:4.2f}\n'
            'Percent rate (per Hour): {pct_ph:4.2f}\n'
            'Estimated time remaining (hours): {eta:4.2f}\n'.format( 
            rc     = pprint.pformat( sync_types ),
            tlrc   = total_rec_count,
            st_ts  = time_data[ 'start_ts' ],
            st     = str( start_time ),
            et_ts  = time_data[ 'end_ts' ],
            et     = str( end_time ),
            el     = str( elapsed ),
            icnt   = inodes_completed,
            itotal = args.inodes,
            pct_c  = pct_complete_by_inodes,
            pct_ph = pct_rate,
            eta    = eta_complete ), file=f )


def print_syncdir_summary( args, syncdir_data ):
    # Duplicates (if there are any)
    dup_outfile = args.infile + '.duplicate_dirs'
    with open( dup_outfile, 'w' ) as f:
        for d in syncdir_data[ 'dups' ]:
            f.write( d )
    # Dirs without end records
    working_outfile = args.infile + '.unfinished_dirs'
    with open( working_outfile, 'w' ) as f:
        for k in syncdir_data[ 'working' ]:
            print( k, file=f )
    # Dir Data
    syncdir_outfile = args.infile + '.syncdir_data'
    outfmt = '{elapsed:>7} {nsd:>7} {nsf:>7} {nsl:>7} {srctot:>7} {src}'
    outkeys = (
             'elapsed', 'nsd', 'nsf', 'nsl', 'ntd', 'ntf', 'ntl', 'srctot', 'src' )
    hdrs1 = ('Elap',    'SRC', 'SRC', 'SRC', 'TGT', 'TGT', 'TGT', 'Total',  'Key' )
    hdrs2 = ('Secs',    'Dir', 'Reg', 'Lnk', 'Dir', 'Reg', 'Lnk', 'Total',  'SrcDir' )
    with open( syncdir_outfile, 'w' ) as f:
        print( outfmt.format( **( dict( zip( outkeys, hdrs1 ) ) ) ), file=f )
        print( outfmt.format( **( dict( zip( outkeys, hdrs2 ) ) ) ), file=f )
        for k, d in syncdir_data[ 'dir_data' ].iteritems():
           print( outfmt.format( elapsed = d[ 'elapsed' ],
                          nsd = d[ 'num_src_dirs' ],
                          nsf = d[ 'num_src_files' ],
                          nsl = d[ 'num_src_symlinks' ],
                          ntd = d[ 'num_tgt_dirs' ],
                          ntf = d[ 'num_tgt_files' ],
                          ntl = d[ 'num_tgt_symlinks' ],
                          src = k,
                          srctot = d[ 'srctot' ] ), file=f )


def run( args ):
    time_data = dict( 
        start_ts = int( time.time() ),
        end_ts = 0
        )
    sync_types = {}
    syncdir_data = dict( 
        dir_data = collections.OrderedDict(),
        dups = collections.OrderedDict(),
        working = {}
        )
    starttime = int( time.time() )
    total_records = 0
    with open( args.infile, 'rb' ) as f:
        try:
            while (1):
                rec = cbor.load( f )
                process_start_end_times( rec, time_data )
                count_sync_types( rec, sync_types )
                process_syncdir_stats( rec, syncdir_data )
                total_records += 1
                if total_records % 1000000 == 0:
                    elapsed_secs = int( time.time() ) - starttime
                    logr.info( 'Processed {0} records in {1} secs'.format(
                        total_records, elapsed_secs ) )
        except ( EOFError ) as e:
            pass
    print_syncdir_summary( args, syncdir_data )
    print_psync_summary( args, time_data, sync_types, total_records )


if __name__ == '__main__':
    loglvl = logging.DEBUG
    logging.basicConfig( 
        level=loglvl,
        format="%(levelname)s-%(filename)s[%(lineno)d]-%(funcName)s-%(message)s"
        )
    args = process_cmdline()
    run( args )
