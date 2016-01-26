#!/bin/sh

max_iterations=1
pause=300

#
# Usage
#
function print_usage
{
  echo "" >&2
  echo "Usage: $PRG [-h -u <username> -p <password>] <logfile_prefix>" >&2
  echo "    OPTIONS: -h   This help message" >&2
  echo "             -i <N> number of iterations to run" >&2
  echo "             -p <N> number of seconds to pause between iterations" >&2
  echo "" >&2
}

#
# Process command line options
#
while getopts ":hi:[iterations]p:[pause]" val; do
  case $val in
    h) print_usage
       exit 0
       ;;
    i) max_iterations=$OPTARG
       ;;
    p) pause=$OPTARG
       ;;
   \?) echo "Invalid option: -$OPTARG" >&2
       print_usage
       exit 1
       ;;
    :) echo "Option -$OPTARG requires an argument." >&2
       print_usage
       exit 1
       ;;
  esac
done
shift $((OPTIND-1))

if [[ $# -ne 1 ]]; then
  echo
  echo ERROR Missing logfile_prefix >&2
  exit 1
fi
logfile_pfx="$1"


for i in $(seq $max_iterations); do
  date
  start=$( date +%s )
  ~aloftus/psync/bin/view_redis_queue -l $logfile_pfx
  end=$( date +%s )
  let "elapsed = $end - $start"
  echo Elapsed secs $elapsed
  [[ $i -lt $max_iterations ]] && sleep $pause
done
