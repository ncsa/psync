import redis_logger
import cbor
import pprint

logr = redis_logger.Redis_Logger( host='10.10.108.18', db=2, queue_name='logr' )

print( 'Starting qlen...' )
print( logr.rq.qlen() )

logr.info( 'testin 1 2 3', src='abc', tgt='xyz' )
logr.debug( 'new debug message', key1='/mnt/a/u/staff/aloftus', key2='qrst', size=12354 )
logr.warning( 'new warning message', src='asdf', tgt='qrst', action='copy' )
logr.error( 'new error message', synctype='SYNCFILE', msgtype='end', src='123', tgt='456'  )

print( 'qlen after adding logs...' )
size = logr.rq.qlen()
print( size )
print( 'q contents...' )
with open( 'logfile.cbor', 'wb' ) as f:
    for m in logr.rq.qpop( size ):
        f.write( m )
        d = cbor.loads( m )
        pprint.pprint( d )

print( 'qlen after pop...' )
print( logr.rq.qlen() )

#logr.exception( 'this should fail' )
print( 'qlen should still be 0...' )
print( logr.rq.qlen() )
