#!/bin/bash
set -euo pipefail

BASE_DIR=$(dirname "$0")
FILE=$2
UPLOAD=$2
if [[ -z $FILE ]]; then
    echo "Failure! File to truncate not given!"
    exit 1
fi

filename=$(basename $FILE)
filename="${filename%.*}"

newest="$filename"_wt.csv
FILE="$BASE_DIR/static/data/$newest"

a=$filename
b='type'
filetype=$a$b

# set the output folder
OUTPUT="$BASE_DIR/static/data/output/$filename"
# line count
LC=$(wc -l < $FILE)
if [[ -z $LC ]]; then
    echo "$FILE is empty!"
    exit 1
fi
# ceiling of line count
LCC=$(python -c "from math import ceil; print int(ceil($LC/600000))")
# line count ceiling += 1
LCC=$(($LCC+1))
# start of first line
C=1
# the code is a truncation script that takes in line numbers that are multiples of 300000, finds the closest BE to that multiple, and
# splits them into files accordingly
#
# begin for
for (( i=1; i<=$LCC; i++ ))
do
    # MULTiple of 300000
    MULT=$((300000*$i))
    # BE that is the closest multiple of 300000
    QUERY=$(awk -F ',' -v mult="$MULT" '($4 > 0) && NR > mult {print NR-1; exit;}' $FILE)

    # basically saying that if the ceiling of line count is equal to the
    # counter, then execute the second sed
    if [ "$i" -ne "$LCC" ]
    then
        # copy file lines from c to QUERY
        sed -n "$C,$QUERY p" $FILE > ${OUTPUT}_${i}.csv
    else
        # if there is no more multiple of 300000, print until end of file
        sed -n "${C},$ p" $FILE > ${OUTPUT}_${i}.csv
    fi
    # set c as QUERY + 1
    C=$(($QUERY+1))
done
rm $FILE
# end for
