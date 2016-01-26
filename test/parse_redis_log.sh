#!/bin/sh

find ~aloftus/var/redis_psync/ -type f -name redis_psync.log \
| xargs grep -v -E \
-e 'Server started'  \
-e 'server is now ready' \
-e 'Redis [0-9.]+ .* 64 bit$' \
-e 'Running in stand alone mode' \
-e 'Port: [0-9]+$' \
-e 'PID: [0-9]+$' \
-e 'http://redis.io' \
-e 'Increased maximum number of open files' \
-e 'Saving...$' \
-e 'Background saving started by pid ' \
-e 'DB saved on disk' \
-e ' of memory used by copy-on-write' \
-e 'Background saving terminated with success' \
-e 'Background AOF rewrite finished successfully' \
-e 'Starting automatic rewriting of AOF' \
-e 'Background append only file rewriting started' \
-e 'append only file rewrite performed' \
-e 'Background AOF rewrite terminated with success' \
-e 'Calling fsync\(\) on the AOF file' \
-e 'Parent diff successfully flushed' \
-e 'DB loaded from disk: ' \
-e 'User requested shutdown...' \
-e 'Saving the final RDB' \
-e 'Removing the pid file' \
-e 'Redis is now ready to exit, bye bye...' \
| grep -E -e '[a-zA-Z0-9]'
