import datetime
import argparse
import os
import logging
import collections


def process_cmdline():
    parser = argparse.ArgumentParser()
    parser.add_argument( 'logfile' )
    args = parser.parse_args()
    return args


def process_logfile( infile, files, dirs, symlinks, timestamps, current_files ):
    active_file_count = 0
    loglinecount = 0
    with open( infile, 'r' ) as f:
        for line in f:
            loglinecount += 1
            if loglinecount % 100000 == 0:
                logging.info( '{0} Processed {1} lines'.format( datetime.datetime.now().time(), loglinecount ) )
            #logging.debug( 'Processing log line:\n{0}'.format( line ) )
            parts = line.strip().split()
            ts = datetime.datetime.strptime( parts[1], '%Y%m%dT%H%M%S' )
            if ts not in timestamps:
                timestamps[ ts ] = { 'files': current_files[:],
                                     'new_files':  0,
                                     'completed_files': 0,
                                     'dir_inodes': 0,
                                     'sym_inodes': 0, }
            typ = parts[2]
            #Parse dir sync
            if typ == 'SYNCDIR':
                action = parts[3]
                # allow for filenames with spaces
                fnlength = int ( ( len( parts ) - 4 ) / 2 )
                src_start = 4
                src_end = src_start + fnlength
                src = ' '.join( parts[ src_start : src_end ] )
                tgt = ' '.join( parts[ src_end : ] )
                if action == 'start':
                    dirs[ src ] = { 'start': ts,
                                    'tgt': tgt }
                    timestamps[ ts ][ 'dir_inodes' ] += 1
                else:
                    # is length of dirsync interesting at all?
                    diff = ts - dirs[ src ][ 'start' ]
                    elapsed = int( diff.total_seconds() )
                    dirs[ src ].update( { 'end': ts,
                                          'elapsed_secs': elapsed } )
            #Parse file sync
            elif typ == 'SYNCFILE':
                action = parts[3]
                src_start = line.index( ' src=' )
                tgt_start = line.index( ' tgt=' )
                src = line[ src_start + 5 : tgt_start ]
                if action == 'start':
                    size_start=line.find( ' size=' )
                    tgt = line[ tgt_start + 5 : size_start ]
                    size = int( line[ size_start + 6 :] )
                    data = { 'start': ts,
                             'size' : size }
                    files[ src ] = data
                    current_files.append( data )
                    active_file_count += 1
                    if active_file_count != len( current_files ):
                        raise UserWarning( 'active file count mismatch at log line\n{0}'.format( line ) )
                    timestamps[ ts ][ 'new_files' ] += 1
                    timestamps[ ts ][ 'files' ].append( data )
                else:
                    data = files[ src ]
                    diff = ts - data[ 'start' ]
                    elapsed = max( int( diff.total_seconds() ), 1 )
                    rate = data[ 'size' ] / elapsed
                    data.update( { 'end': ts,
                                   'rate': rate } )
                    current_files.remove( data )
                    active_file_count -= 1
                    if active_file_count != len( current_files ):
                        raise UserWarning( 'active file count mismatch at log line\n{0}'.format( line ) )
                    timestamps[ ts ][ 'completed_files' ] += 1
            #Parse symlink sync
            elif typ.startswith( 'SYMLINK' ):
                link_type = typ[8:]
                tgt_src_start=33
                tgt_tgt_start = line.index( ' -> ' )
                src_src_start = line.index( ' (original:' )
                src_tgt_start = line.index( ' -> ', src_src_start )
                tgt_src = line[ tgt_src_start : tgt_tgt_start ]
                symlinks[ tgt_src ] = {
                    'tgt_tgt': line[ tgt_tgt_start + 4 : src_src_start ],
                    'src_src': line[ src_src_start + 11 : src_tgt_start ],
                    'src_tgt': line[ src_tgt_start + 4 : -2 ],
                    }
                timestamps[ ts ][ 'sym_inodes' ] += 1
            else:
                logging.warning( 'Unknown sync type: {0} for line {1}'.format( 
                    typ, line ) )


def print_hourly_summary( ts, rates ):
    print( "{timestamp} AvgRate={avg:.2f} GiB/s".format(
        timestamp = ts.strftime( "%Y-%m-%d %H hrs" ),
        avg = sum( rates ) / len( rates )
        ) )


def calc_rates( timestamps ):
    hourly_avg_rates = []
    prev_ts = timestamps.keys()[0]
    for ts, ts_data in timestamps.iteritems():
        if ts.hour != prev_ts.hour:
            print_hourly_summary( prev_ts, hourly_avg_rates )
            prev_ts = ts
            hourly_avg_rates = []
        rate = 0
        for d in ts_data[ 'files' ]:
            if 'rate' in d:
                rate += d[ 'rate' ]
        ts_data[ 'rate' ] = rate
        rate_mbs = rate / 1048576.0
        rate_gbs = rate / 1073741824.0
        logging.debug( '\n{T} rate={M:.2f} MiB/s ({G:.2f} GiB/s) doneF={D} newF={N}, otherinodes={O}'.format( 
            T = ts, 
            M = rate_mbs, 
            G = rate_gbs, 
            D = ts_data[ 'completed_files' ], 
            N = ts_data[ 'new_files' ], 
            O = ts_data[ 'dir_inodes' ] + ts_data[ 'sym_inodes' ]
            ) )
        hourly_avg_rates.append( rate_gbs )
    print_hourly_summary( prev_ts, hourly_avg_rates )



def run():
    files = {}      # key=src,      subkeys: start, end, size, elapsed_secs, rate
    dirs = {}       # key=src,      subkeys: start, end
    symlinks = {}   # key=tgt_src,  subkeys: ts, link_type, tgt_tgt, src_src, src_tgt
    # Timestamps     key=timestamp, subkeys: files, dir_inodes, sym_inodes, new_files
    timestamps = collections.OrderedDict()
    current_files = []
    args = None
    args = process_cmdline()
    process_logfile( args.logfile, files, dirs, symlinks, timestamps, current_files )
    calc_rates( timestamps )
    

if __name__ == '__main__':

    logging.basicConfig( 
        level=logging.DEBUG,
        format="%(levelname)s-%(filename)s[%(lineno)d]-%(funcName)s-%(message)s"
        )
    run()
