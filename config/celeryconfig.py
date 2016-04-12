# Note: broker_url is loaded from a separate file that broker updates when it starts.

CELERY_ACCEPT_CONTENT = ['pickle']

#CELERY_SEND_EVENTS = True

#CELERYD_PREFETCH_MULTIPLIER = 4
CELERYD_PREFETCH_MULTIPLIER = 1

CELERYD_LOG_LEVEL = 'INFO'

# Queues & Routes
# Note: default queue is "celery"
# Note: anything not explicitly defined below will go to the the default queue
#CELERY_IMPORTS = ('psync', )
#CELERY_CREATE_MISSING_QUEUES = True
CELERY_ROUTES = {
    'psync.sync_hardlink':   {'queue': 'hardlinks'},
}
##    'psync.resync_dir_meta': {'queue': 'dirmeta'},
