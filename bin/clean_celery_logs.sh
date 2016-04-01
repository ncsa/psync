#!/bin/sh

configfile="${BASH_SOURCE%/*}/../config/bashrc"
[[ -r $configfile ]] || {
  echo "ERROR Can't find config file '$configfile'. Exiting"
  exit 1
}
source "$configfile"


srcdirs=( \
    $PSYNCVARDIR/redis_psync \
    $PSYNCVARDIR/psync_service \
    $PSYNCVARDIR/rabbitmq_psync/log \
    )

for d in "${srcdirs[@]}"; do
  find $d -delete
  mkdir -p $d
  set -x
  ls -lF $d
  set +x
done
