#!/bin/sh

srcdirs=( \
    ~aloftus/var/redis_psync \
    ~aloftus/var/psync_service \
    ~aloftus/var/rabbitmq_psync/log \
    )

for d in "${srcdirs[@]}"; do
  find $d -delete
  mkdir -p $d
  set -x
  ls -lF $d
  set +x
done
