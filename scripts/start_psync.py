#!/bin/env python

import psync
import time
import datetime
import pprint
import argparse
import os
import stat
import fsitem

def process_cmdline():
    help_txt = """Note: TGT must already exist.
    After psync is done, the inside of TGT will look identical to the inside of SRC.
    This is equivalent to 'rsync ... src/ tgt/' (note the trailing
    slashes).
    """
    parser = argparse.ArgumentParser( epilog=help_txt )
    parser.add_argument( 'src_dir', metavar='SRC' )
    parser.add_argument( 'tgt_dir', metavar='TGT' )
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
    return args


def dir_is_writeable( dn ):
    rv = True
    if not os.path.isdir( dn ):
        os.mkdir( dn )
    if not os.path.isdir( dn ):
        rv = False
    if not os.access( dn, os.W_OK | os.X_OK ):
        rv = False
    return rv

def run():
    args = process_cmdline()

    # Create FSItem's for the cmdline args
    src = fsitem.FSItem( args.src_dir )
    tgt = fsitem.FSItem( args.tgt_dir )

    # Check (or create) tmpdir and rmdir
    for var in [ 'PSYNCTMPDIR', 'PSYNCRMDIR' ]:
        leaf = os.environ[ var ]
        dn = os.path.join( tgt.mountpoint, leaf )
        if not dir_is_writeable( dn ):
            raise UserWarning( "Dir missing or not writeable: {0} = '{1}'".format( 
                var, dn ) )

    psyncopts = {}
    for k in ( 'minsecs', 'pre_checksums' ):
        psyncopts[ k ] = getattr( args, k )
    rsyncopts = {}
    for k in ( 'syncowner', 'syncgroup', 'syncperms', 'synctimes', 
               'pre_checksums', 'post_checksums' ):
        rsyncopts[ k ] = getattr( args, k )
    # Seed the process
    psync.sync_dir.apply_async( ( src, tgt, psyncopts, rsyncopts ) )
    psync.schedule_final_dir_sync.apply_async( args=( 300, ), countdown=300 )

if __name__ == '__main__':
    run()
