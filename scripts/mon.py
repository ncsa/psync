from __future__ import print_function
import psync
import argparse
import time
import datetime
import sqlite3
import os
import logging
import pprint

logging.basicConfig(
    level=logging.WARNING,
    format="%(levelname)s-%(filename)s[%(lineno)d]-%(funcName)s-%(message)s"
)
logr = logging.getLogger( __name__ )

def process_cmdline():
    parser = argparse.ArgumentParser()
    parser.add_argument( '--filename', '-f', 
        help='Sqlite3 filename. Default=%(default)s' )
    parser.add_argument( '--collectnew', '-c', action='store_true',
        help='Collect new worker stats into the database. Default=%(default)s' )
    parser.add_argument( '--noreport', '-r', action='store_false', dest='report',
        help='Do not create a report. Default action is to create a report.' )
    mutexgroup = parser.add_mutually_exclusive_group()
#    mutexgroup.add_argument( '--itercount', '-i', metavar='N',
#        help='Show details for last N data collection iterations.' )
    mutexgroup.add_argument( '--seconds', '-s', metavar='N',
        help='''Show details for all iterations for the past N seconds. 
                Default=%(default)s
             ''' )
    mutexgroup.add_argument( '--days', '-d', type=int, metavar='N',
        help='Show details for all iterations for the past N days.' )
    parser.set_defaults( 
        filename='stats.db',
#        seconds=3600
        seconds=86400
        )
    args = parser.parse_args()
    if args.days:
        args.seconds = args.days * 86400
    return args


def db_connect_or_create( fn ):
    mknew = False
    if not os.path.exists( fn ):
        mknew = True
    # connect will create a new file if it doesn't already exist
    conn = sqlite3.connect( fn, isolation_level=None )
    conn.row_factory = sqlite3.Row
    if mknew:
        logging.debug( 'about to initialize database' )
#                   CREATE INDEX IF NOT EXISTS timestamps ON stats ( timestamp );
#                   CREATE INDEX IF NOT EXISTS workers ON stats ( worker );
        conn.cursor().executescript( '''
                   CREATE TABLE IF NOT EXISTS stats
                   ( timestamp INTEGER, 
                     worker TEXT, 
                     taskname TEXT, 
                     qty INTEGER,
                     change INTEGER,
                     elapsed INTEGER,
                     rate REAL );
                   ''' )
    return conn


def update_worker_stats( db ):
    timestamp = int( time.time() )
    worker_stats = psync.app.control.inspect().stats()
    if worker_stats is None:
        raise SystemExit( 'No workers found.' )
    # get previous update for each worker
    prev_ts, prev = get_prev_update( db )
    values = []
    # process new worker stats
    for worker, stats in worker_stats.iteritems():
        for task, qty in stats[ 'total' ].iteritems():
            # calculate change and rate from previous DB update
            change = 0
            rate = 0
            elapsed = 0
            if prev_ts:
                change = qty - prev[ worker ][ task ]
                elapsed = timestamp - prev_ts
                rate = change * 1.0 / elapsed
            values.append( ( timestamp, worker, task, qty, change, elapsed, rate ) )
    db.executemany( """
                    INSERT INTO stats
                    ( timestamp, worker, taskname, qty, change, elapsed, rate ) 
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, values )


def select_as_list( db, stmt ):
    cur = db.cursor()
    cur.execute( stmt )
    return [ x[0] for x in cur ]
    

def get_prev_update( db ):
    data = {}
    ts_max = select_as_list( db, "SELECT max(timestamp) FROM stats" )[0]
    if ts_max:
        cur = db.cursor()
        cur.execute( 
            'SELECT worker, taskname, qty FROM stats WHERE timestamp=?', 
            ( ts_max, ) )
        for row in cur:
            w = row[0]
            t = row[1]
            q = row[2]
            if w not in data:
                data[ w ] = {}
            data[w][t] = q
    return ( ts_max, data )


def get_iter_data( db, args ):
    """
    Process data from the database into combined statistics.
    Return tuple: ( rows, summary ), where each row in rows is a 
    list of rates by taskname and summary is a single row in the same format
    Each row or rows can be passed to print_report.
    """
#    if args.itercount:
#        # get list of distinct timestamps, in descending order, limit itercount
#        # use last (earliest) timestamp to calc new value for args.seconds and 
#        # proceed as normal using args.seconds
    report_rows = []
    task_names = [ 'sync_dir', 'sync_file', 'sync_hardlink' ]
    rates_by_taskname = { k:0 for k in task_names }
    # first and last, save qty's for calculating summary at the end
    first = { k:0 for k in task_names }
    first[ 'ts' ] = 0
    last = { k:0 for k in task_names }
    last[ 'ts' ] = 0
    prev_ts = 0
    mintime = int( time.time() ) - args.seconds
    stmt = 'SELECT * FROM stats WHERE timestamp>=? ORDER BY timestamp ASC'
    for row in db.execute( stmt, ( mintime, ) ):
        cur_ts = row[ 'timestamp' ]
        #save off previous data
        if cur_ts != prev_ts:
            if prev_ts > 0:
                rates_by_taskname[ 'ts' ] = prev_ts
                report_rows.append( rates_by_taskname )
                rates_by_taskname = { k:0 for k in task_names }
            else:
                first[ 'ts' ] = cur_ts
            prev_ts = cur_ts
            last = { k:0 for k in task_names }
            last[ 'ts' ] = cur_ts
        t = row[ 'taskname' ][6:]
        # combine rates from all workers by taskname
        if t in task_names:
            rates_by_taskname[ t ] += row[ 'rate' ]
            last[ t ] += row[ 'qty' ]
            if cur_ts == first[ 'ts' ]:
                first[ t ] += row[ 'qty' ]
    #save last row of data
    if prev_ts > 0:
        rates_by_taskname[ 'ts' ] = prev_ts
        report_rows.append( rates_by_taskname )
    # Calculate summaries
    if last[ 'ts' ] > 0:
        elapsed = last[ 'ts' ] - first[ 'ts' ]
        for t in task_names:
            q1 = first[ t ]
            q2 = last[ t ]
            last[ t ] = ( q2 - q1 ) * 1.0 / elapsed
    return ( report_rows, last )


def get_totals( db ):
    stmt = 'select min(timestamp), max(timestamp) from stats'
    min_ts = None
    max_ts = None
    for row in db.execute( stmt ):
        min_ts = row[0]
        max_ts = row[1]
    stmt = 'SELECT * FROM stats WHERE timestamp IN (?,?) ORDER BY timestamp ASC'
    task_names = [ 'sync_dir', 'sync_file', 'sync_hardlink' ]
    raw_data = { min_ts: { k:0 for k in task_names },
                 max_ts: { k:0 for k in task_names } }
    for row in db.execute( stmt, ( min_ts, max_ts ) ):
        ts = row[ 'timestamp' ]
        t = row[ 'taskname' ][6:]
        if t in task_names:
            raw_data[ ts ][ t ] += row[ 'qty' ]
    rate_data = { k:0 for k in task_names }
    elapsed = max_ts - min_ts
    for t in task_names:
        start = raw_data[ min_ts ][ t ]
        end   = raw_data[ max_ts ][ t ]
        rate_data[ t ] = ( end - start ) * 1.0 / elapsed
    rate_data[ 'ts' ] = max_ts
    return( rate_data )


def print_report( rows, title=None ):
    fmtstr = '{ts:19s}   {sync_dir:<10.1f}   {sync_file:<10.1f}   {sync_total:<10.1f}'
    fmthdr =('{ts:19s}   {sync_dir:<10}' '   {sync_file:<10}' '   {sync_total:<10}' )
    hdrs = { 'ts'        :'Timestamp', 
             'sync_dir'  :'DirRate', 
             'sync_file' :'FileRate', 
             'sync_total':'TotalRate' }
    if title:
        print( title )
    print( fmthdr.format( **hdrs ) )
    for d in rows:
        #combine sync_file and sync_hardlink counts
        d[ 'sync_file' ] += d[ 'sync_hardlink' ]
        #create total count
        d[ 'sync_total' ] = d[ 'sync_file' ] + d[ 'sync_dir' ]
        #convert timestamp to datetime
        d[ 'ts' ] = str( datetime.datetime.fromtimestamp( d[ 'ts' ] ) )
        print( fmtstr.format( **d ) )
    

def run():
    args = process_cmdline()
    db = db_connect_or_create( args.filename )
    if args.collectnew:
        try:
            new_stats = update_worker_stats( db )
        except ( SystemExit ) as e:
            db.close()
            raise e
    if args.report:
        rows, summary = get_iter_data( db, args )
        print_report( rows, title='Per Iteration' )
        print()
        print_report( [ summary ], title='Summary' )
        print()
        totals = get_totals( db )
        print_report( [ totals ], title='Totals since last restart' )

    db.close()


if __name__ == "__main__":
    logr.setLevel( logging.DEBUG )
    run()
