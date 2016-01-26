#!/bin/env python

import psync
import time
import datetime
import pprint
import argparse
import os
import fsitem

epoch = datetime.datetime( year=1970, month=1, day=1 )


def process_cmdline():
    help_txt = """Note: TGT must already exist.
    After psync is done, the inside of TGT will look identical to the inside of SRC.
    This is equivalent to 'rsync ... src/ tgt/' (note the trailing
    slashes).
    """
    parser = argparse.ArgumentParser( epilog=help_txt )
    parser.add_argument( 'src_dir', metavar='SRC' )
    parser.add_argument( 'tgt_dir', metavar='TGT' )
    parser.add_argument( '--logbasename', '-l', metavar='BASENAME',
        help="""Basename for logfiles (default: %(default)s).
            Actual filenames created will be suffixed with current date/time
            and type of log message (ie: INFO, ERROR, WARNING, ...).
            Logfiles will be created in the directory specified by $PSYNCLOGDIR
            (environment variable) except when BASENAME is an absolute path, in which
            case $PSYNCLOGDIR will be ignored.
        """
        )
    pgroup = parser.add_argument_group( title='Psync options',
        description='Options to adjust psync behavior.')
    pgroup.add_argument( '--minsecs', '-m', type=int,
        help="""Skip inodes younger than MINSECS. Useful for avoiding race 
        conditions when syncing a live filesystem. (default: %(default)s)"""
        )
    pgroup.add_argument( '--no_checksums', action='store_false', dest='post_checksums',
        help='When a file is copied, the checksums for both source and target are '
             'compared to verify the copy was accurate.  Specifying no_checksums '
             'will disable that check.'
        )
    pgroup.add_argument( '--use_checksums', action='store_true', dest='pre_checksums',
        help='Use checksums to determine if source and target files differ. '
             'Normally, only size and mtime are used to determine if the source '
             'file has changed.'
        )
    rgroup = parser.add_argument_group( title='Rsync options' )
    rgroup.add_argument( '--syncowner', '-o', action='store_true',
        help='Sync file owner (default: %(default)s).'
        )
    rgroup.add_argument( '--syncgroup', '-g', action='store_true',
        help='Sync file group (default: %(default)s).'
        )
    rgroup.add_argument( '--syncperms', '-p', action='store_true',
        help='Sync file permissions (default: %(default)s).'
        )
    rgroup.add_argument( '--synctimes', '-t', action='store_true',
        help='Sync file mtime (default: %(default)s).'
        )
    default_options = {
        'logbasename': 'psync',
        'syncowner': False,
        'syncgroup': False,
        'syncperms': False,
        'synctimes': False,
        'pre_checksums': False,
        'post_checksums': True,
        'minsecs': 0,
    }
    parser.set_defaults( **default_options )
    args = parser.parse_args()
    # check for logdir
    logdir = os.environ.get( 'PSYNCLOGDIR' )
    logbase = ''
    if args.logbasename.startswith( os.sep ):
        logbase = args.logbasename
    elif logdir is None:
        raise UserWarning( """Don't know where to write logs.  
            Must either set PSYNCLOGDIR environment variable or 
            set fully qualified path using -l cmdline argument.""" )
    else:
        logbase = os.path.join( logdir, args.logbasename )
    # append date/time stamp to logbasename
    now = int( ( datetime.datetime.now() - epoch ).total_seconds() )
    args.logbasename = '{0}.{1}'.format( logbase, now )
    # attempt to write logfile; easier to fail here than after starting
    testlogfile = '{0}.{1}'.format( args.logbasename, 'test' )
    with open( testlogfile, 'a' ) as f:
        f.write( 'a' )
    os.unlink( testlogfile )
    return args


def run():
    args = process_cmdline()

    # Create FSItem's for the cmdline args
    src = fsitem.FSItem( args.src_dir )
    tgt = fsitem.FSItem( args.tgt_dir )
    psyncopts = {}
    for k in ( 'minsecs', 'pre_checksums' ):
        psyncopts[ k ] = getattr( args, k )
    rsyncopts = {}
    for k in ( 'syncowner', 'syncgroup', 'syncperms', 'synctimes', 
               'pre_checksums', 'post_checksums' ):
        rsyncopts[ k ] = getattr( args, k )
    # Seed the process
    psync.sync_dir.delay( src, tgt, psyncopts, rsyncopts )

if __name__ == '__main__':
    run()
