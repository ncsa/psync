# This file serves two purposes:
# First, it contains the redis url when the redis server is running.
# Second, it contains additional redis-related celery settings that will get
# used by celery IF the celery broker is set to redis.

###
# Redis specific settings
# See also:
# http://docs.celeryproject.org/en/latest/getting-started/brokers/redis.html
###

# Broadcast messages will be seen by all virtual hosts by default.
# You have to set a transport option to prefix the messages so that 
# they will only be received by the active virtual host
BROKER_TRANSPORT_OPTIONS = {'fanout_prefix': True}

# Workers will receive all task related events by default.
# To avoid this you must set the fanout_patterns fanout option 
# so that the workers may only subscribe to worker related events
BROKER_TRANSPORT_OPTIONS = {'fanout_patterns': True}

# If a task is not acknowledged within the Visibility Timeout the task 
# will be redelivered to another worker and executed.
# This causes problems with ETA/countdown/retry tasks where the time to 
# execute exceeds the visibility timeout; 
# in fact if that happens it will be executed again, and again in a loop.
# So you have to increase the visibility timeout to match the time of the 
# longest ETA you are planning to use.
BROKER_TRANSPORT_OPTIONS = {'visibility_timeout': 604800}

# redis URL information will be filled in below when the redis server starts
