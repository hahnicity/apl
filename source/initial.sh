#!/bin/bash
set -euo pipefail

# finds the newest file in /uploads/ folder
FILE=$1
mkdir -p tmp_processing
cp $FILE tmp_processing/
TMP_FILE=tmp_processing/`basename $FILE`
# remove all null bytes
sed -i -e 's/\x00//g' $TMP_FILE

# remove all preceding data before the first BS
firstline=$(head -n 1 $TMP_FILE)
if ! python testfordate.py $firstline
then
    sed -i -e '/BS/,$!d' $TMP_FILE
fi
python clear_null_bytes.py $TMP_FILE $TMP_FILE
# remove all data after the last BE XXX this is currently broken
#tmp="/tmp/foo"
#tac $TMP_FILE | sed '/BE/,$!d' | tac > $tmp ; mv $tmp $TMP_FILE

# count how many columns are in the file
v=$(awk -F',' '{print NF; exit}' $TMP_FILE)

echo $v
if [ "$v" -eq 3 ] || [ "$v" -eq 1 ] || [ "$v" -eq 2 ]
then
    python extract_breath_meta.py $TMP_FILE
    python preprocess_vwd.py $TMP_FILE
# if there are four columns, use absolute time
elif [ "$v" -eq 4 ]
then
    python extract_breath_meta.py $TMP_FILE
    python preprocess_vwd.py $TMP_FILE
fi
./filetrunc.sh $v $TMP_FILE
rm $TMP_FILE
rm -r tmp_processing/
