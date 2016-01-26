#!/bin/sh

configfile="${BASH_SOURCE%/*}/../config/bashrc"
[[ -r $configfile ]] || {
  echo "ERROR Can't find config file '$configfile'. Exiting"
  exit 1
}
source "$configfile"


[[ $# -ne 1 ]] && {
    echo "Error: no input file specified"
    exit 99
}


$PSYNCBASEDIR/test/parse_psync_errlog.py -d -i TimeLimitExceeded $1 \
| awk '
/^args:/ {split($0, parts, /\/mnt\/a/)
line=(parts[2])
split(line, parts, />, </)
print( parts[1] )}' \
| sort
