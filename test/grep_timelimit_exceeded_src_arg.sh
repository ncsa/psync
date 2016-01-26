#!/bin/sh

[[ $# -ne 1 ]] && {
    echo "Error: no input file specified"
    exit 99
}

~aloftus/psync/test/parse_psync_errlog.py -d -i TimeLimitExceeded $1 \
| awk '
/^args:/ {split($0, parts, /\/mnt\/a/)
line=(parts[2])
split(line, parts, />, </)
print( parts[1] )}' \
| sort
