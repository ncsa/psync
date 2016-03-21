#!/bin/sh

configfile="${BASH_SOURCE%/*}/../config/bashrc"
[[ -r $configfile ]] || {
  echo "ERROR Can't find config file '$configfile'. Exiting"
  exit 1
}
source "$configfile"

PYTHON=/mnt/a/settools/bin/python
tmp=$( mktemp )
tmp2=$( mktemp )
tmp3=$( mktemp )

function dumptmp {
    if [[ -s $tmp ]]; then
        cat $tmp
    else
        echo "  n/a"
    fi
}

function is_file_open {
    lsof "$1" 2>/dev/null
}

pfx=$( ls -t $PSYNCLOGDIR/*.INFO | head -1 | sed -e 's/.INFO$//' )

LOGFILE=${pfx}.INFO
ERRFILE=${pfx}.ERROR
WARNINGFILE=${pfx}.WARNING

echo
echo PSYNC ERRORS
if [[ -f $ERRFILE ]] ; then
    $PYTHON $PSYNCBASEDIR/test/parse_psync_errlog.py -n $ERRFILE
else
    echo "  n/a"
fi

echo
echo PSYNC WORKER ERRORS
find $PSYNCVARDIR/psync_service/ -name '*.log' \
| xargs $PYTHON $PSYNCBASEDIR/test/parse_worker_errlog.py \
>$tmp2
head -n -4 $tmp2 > $tmp
dumptmp

echo
echo REDIS ERRORS
$PSYNCBASEDIR/test/parse_redis_log.sh >$tmp
dumptmp

echo
echo LOG FILE SIZES
ls -1sh ${pfx}*

echo
echo WARNINGS
if [[ -f $WARNINGFILE ]] ; then
    $PSYNCBASEDIR/test/parse_psync_warnlog.py $WARNINGFILE
else
    echo "  n/a"
fi

# Parse infolog
# tmp = progress info
# tmp2 = duplicate dirs
# The $@ allows to pass "-i <num_inodes>" to parse_infolog
$PSYNCBASEDIR/test/parse_psync_infolog.py $@ $LOGFILE > $tmp 2>$tmp2

echo
echo "5 LONGEST RUNNING TASKS"
dupfile=${LOGFILE}.syncdir_data
sort -n $dupfile | fgrep -v ' 999999 ' > $tmp2
sed -ne '2 p' $dupfile
tail -5 $tmp2

echo
echo PROGRESS INFO
cat ${LOGFILE}.summary

echo
echo REPORT TIME : $SECONDS secs

rm -f $tmp $tmp2 $tmp3
