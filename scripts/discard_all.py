import psync

# These might work IF the CELERY_ROUTES config setting were set properly
#print( psync.app.control.discard_all() )
#print( psync.app.control.purge() )

# Otherwise, name the queues here
import celery.bin.amqp
amqp = celery.bin.amqp.amqp( app = psync.app )
queuenames = [ 'celery', 'hardlinks', 'directories' ]
for q in queuenames:
    print( 'Queue: ' + q )
    print( amqp.run( 'queue.purge', q ) )
