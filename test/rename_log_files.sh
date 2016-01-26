#!/bin/sh

[[ $# -ne 1 ]] && {
  echo 'Missing original file path'
  exit 1
}

fullpath=$1
dn=$( dirname "$fullpath" )
fn=$( basename "$fullpath" ".INFO" )
testfn="$dn/${fn}.INFO"
[[ -f "$testfn" ]] || {
  echo "Cant open file '$dn/${fn}.INFO'"
  echo "Must specify a valid path to a *.INFO file"
  exit 1
}

ts=$( ~aloftus/psync/test/catcbor.py --ini -H 1 $fullpath \
| awk '$1 == "ts" {print $NF}' )
new_f_pfx="${ts}.${fn}"

for ext in INFO WARNING ERROR; do
    old_f="$dn/${fn}.$ext"
    new_f="$dn/${new_f_pfx}.$ext"
    if [[ -f $old_f ]] ; then
        mv "$old_f" "$new_f"
    fi
done
echo
echo "$dn/${new_f_pfx}"
echo
ls -lF "$dn/${new_f_pfx}"*
