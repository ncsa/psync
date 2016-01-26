#!/bin/sh

function parallel_del_dir() {
    deldir=$1
    mmdepth=$2
#    find "$deldir" -maxdepth $mmdepth -mindepth $mmdepth -print \
#    | wc -l
    find "$deldir" -maxdepth $mmdepth -mindepth $mmdepth -print0 \
    | xargs -0 -n1 -P64 -I{} find {} -delete
    find "$deldir" -delete
}

TODAY=$( date +%s)

srcdir=/projects/test/aloftus/hometest
tmpdir=/mnt/b/__PSYNCTMPDIR__

# Setup mv target
tgtbase="/projects/test/aloftusold"
tgtdir="${tgtbase}/${TODAY}"
mkdir -p $tgtdir

# Move sources out of the way
for d in "$srcdir" "$tmpdir"; do
#    set -x
    if [[ -d "$d" ]] ; then
        mv "$d" "$tgtdir"/.
        mkdir -p "$d"
#        ls -lF "$d"
    fi
#    set +x
done

# Iterate over all date-subdirs in tgtbase
for newbase in $( find "$tgtbase" -mindepth 1 -maxdepth 1 ); do
    # Delete PSYNCTMPDIR's
    deldir="${newbase}/$( basename $tmpdir )"
    set -x
    time parallel_del_dir "$deldir" 1
    set +x
    # Delete home's
    src=$( basename $srcdir )
    case $src in
        hometest) deldir="${newbase}/$src"
                  set -x
                  time parallel_del_dir "$deldir" 1
                  set +x
                  ;;
               *) echo "Error: unknown src '$src' from srcdir '$srcdir'" 1>&2
                  exit 99
                  ;;
    esac
    time find "$newbase" -delete

echo "Total Elapsed Seconds: $SECONDS"

done
