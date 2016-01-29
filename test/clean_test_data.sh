#!/bin/bash

function parallel_del_dir() {
    deldir=$1
    mmdepth=$2
    find "$deldir" -maxdepth $mmdepth -mindepth $mmdepth -print0 \
    | xargs -0 -n1 -P64 -I{} find {} -delete
    find "$deldir" -delete
}

TODAY=$( date +%s)
srcdirlist=( $( find /projects/test/aloftus -mindepth 1 -maxdepth 1 -type d ) )
tmpdir=/mnt/b/__PSYNCTMPDIR__

# Setup mv target
tgtbase="/projects/test/aloftusold"
tgtdir="${tgtbase}/${TODAY}"
mkdir -p $tgtdir

# Move sources out of the way
for d in "${srcdirlist[@]}" "${tmpdir}"; do
    set -x
    if [[ -d "$d" ]] ; then
        mv "$d" "$tgtdir"/.
    fi
    set +x
done

# Iterate over all date-subdirs in tgtbase
for newbase in $( find "$tgtbase" -mindepth 1 -maxdepth 1 ); do
    # Delete sources
    for s in $( find $newbase -mindepth 1 -maxdepth 1 -type d ); do
        src=$( basename $s )
        deldir="${newbase}/$src"
        if [[ -d "$deldir" ]] ; then
            set -x
            time parallel_del_dir "$deldir" 1
            set +x
        fi
    done

    # Delete PSYNCTMPDIR
    deldir="${newbase}/$( basename $tmpdir )"
    if [[ -d "$deldir" ]] ; then
        set -x
        time parallel_del_dir "$deldir" 1
        set +x
    fi

    # Delete top dir
    time find "$newbase" -delete

echo "Total Elapsed Seconds: $SECONDS"

done
