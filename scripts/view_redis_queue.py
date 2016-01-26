import psync
import argparse
import os
import cbor


parser = argparse.ArgumentParser( 
    description='View/Count/Delete messages in a redis queue.' )
parser.add_argument( '--verbose', '-v', action='store_true', 
    help="""Verbose, print individual log messages.""" )
parser.add_argument( '--delete', '-d', action='store_true', 
    help="""Delete log messages.""" )
parser.add_argument( '--logbase', '-l',
    help="""Write logs to LOGBASE.<TYPE> where <TYPE> is
    the log type (ie: INFO, WARNING, ERROR, etc).  Implies --delete.""" )
parser.set_defaults( 
    verbose=False,
    delete=False
)
args = parser.parse_args()
if args.logbase:
    args.delete = True

rq = psync.logr.rq
msg_count = 0

# How to get logs
func = rq.qlist
if args.delete:
    func = rq.qpop_all

# Get logs
logmsgs = dict( DEBUG=[], INFO=[], WARNING=[], ERROR=[] )
for m in func():
    msgdict = cbor.loads( m )
    logmsgs[ msgdict[ 'sev' ] ].append( m )
    if args.verbose:
        print( msgdict )

# Process logs
for k, msglist in logmsgs.iteritems():
    size = len( msglist )
    if size > 0 and args.logbase:
        fn = '{0}.{1}'.format( args.logbase, k )
        with open( fn, 'ab' ) as f:
            f.writelines( msglist )
    msg_count += size

# Print summary information
action = 'Retrieved'
if args.logbase:
    action = 'Logged'
elif args.delete:
    action = 'Deleted'
print( '{action} {sz} messages.'.format( action=action, sz=msg_count ) )
