#!/bin/bash
set -euo pipefail

# finds the newest file in /uploads/ folder
FILE=$1
mkdir -p tmp_processing
cp $FILE tmp_processing/
TMP_FILE=tmp_processing/`basename $FILE`

# count how many columns are in the file
v=$(awk -F',' '{print NF; exit}' $TMP_FILE)

python extract_breath_meta.py $TMP_FILE
python preprocess_vwd.py $TMP_FILE
./filetrunc.sh $v $TMP_FILE
rm $TMP_FILE
rm -r tmp_processing/
