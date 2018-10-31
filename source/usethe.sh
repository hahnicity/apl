#!/bin/bash

DIR="$HOME/apl/uploads/"
while FILE=$(inotifywait --format '%f' -e close_write $DIR)
do
    FILE=$DIR$FILE
    echo "`date` $FILE" >> uploaded-read-files.out
    echo "`date` Run on file $FILE `/home/ubuntu/apl/initial.sh $FILE`" &>> initial.log
    rm $DIR$FILE
done
