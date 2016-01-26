#!/bin/sh

#outf=~aloftus/var/log/verify_aloftus.out
#tmp=~aloftus/var/log/tmpfile
#set -x
#time \
#rsync -niirv -Altpgo --hard-links \
#    /mnt/a/test/aloftus/copy_of_home/ \
#    /projects/test/aloftus/hometest \
#    > $tmp
#set +x

[[ $# -lt 1 ]] && {
    echo Missing input file
    exit 99
}

awk '
/^$|^sent|^total|^sending/ { print "SKIP ... ",$0 > "/dev/stderr"; next }
{
    if ( ! ($1 in match_counts ) ) { 
        match_counts[$1]=0 
    }
    match_counts[$1]++
    print
}
END {
    print "\n======= SUMMARY =======" > "/dev/stderr"
    for ( i in match_counts ) {
        print i, match_counts[i] > "/dev/stderr"
    }
}
' "$1"
