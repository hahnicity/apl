"""
timeappend
~~~~~~~~~~

Makes files that are compatible for consumption by dygraphs.
"""
from __future__ import print_function
import csv
import glob
import sys
import os
import json
import time
import datetime
from datetime import timedelta
from os import listdir
from os.path import isfile, join, basename, splitext
from subprocess import call

import config

# append is for relative files
# append2 is for absolute


def append():
    # have the passed filename from initial.sh be the target file
    print(str(sys.argv[2]))
    file_name = str(sys.argv[2])
    base = basename(file_name)
    base = splitext(base)[0]
    # _wt stands for withtimestamps, it is the file that contains all timestamps
    filename = base + '_wt.csv'
    filename = os.path.join(os.path.dirname(__file__), config.DATA_DIR, filename)
    # create anno file
    fr = open(file_name, "rbU")
    first_line = fr.readline().rstrip()
    fr.seek(0)
    t = 0.02
    dt = .02
    breath = 1
    prevline = []
    try:
        dt = datetime.datetime.strptime(first_line, "%Y-%m-%d-%H-%M-%S.%f")
        t = time.mktime(dt.timetuple()) * 1e3 + dt.microsecond / 1e3
        dt = 20
    except:
        pass
    b = csv.reader(fr)
    with open(filename, 'wb') as f:
        a  = csv.writer(f, delimiter=',')
        for row in b:
            try:
                float(row[0])
                float(row[1])
            except (IndexError, ValueError):  # If for some reason prevline was not set.
                continue
            ts = '%.2f' % round(t, 2)
            # write ts as the artifical timestamp with flow, pressure
            if prevline and prevline[0].strip() == "BS":
                breath += 1
                to_write = breath
            else:
                to_write = 0
            a.writerow([ts, row[0], row[1], to_write])
            t = t + dt
            prevline = row



# append2 is the function that works on files with absolute datetime stamps
# already included
def append2():
    file_name = str(sys.argv[2])
    base = basename(file_name)
    base = splitext(base)[0]
    filename = base +'_wt.csv'
    filename = os.path.join(os.path.dirname(__file__), config.DATA_DIR, filename)
    fr = open(file_name, "rbU")
    b = csv.reader(fr)
    t = ""
    breath = 1
    prevline = []
    with open(filename, 'wb') as f:
        a  = csv.writer(f, delimiter=',')
        for row in b:
            # create milliseconds from epoch of absolute date time, add
            # microseconds to it, then multiply it by 1000 for javascript
            try:
                row[0]
            except IndexError:
                continue
            if len(row[0]) == 29:
                t = row[0][:-3]
            elif len(row[0]) == 23:
                t = row[0] + '001'
            else:
                t = row[0]
            tmp_dt = datetime.datetime.strptime(t, "%Y-%m-%d %H:%M:%S.%f")
            date_time = time.mktime(tmp_dt.timetuple())*1e3 + (tmp_dt.microsecond)/1e3
            ts = '%.2f' % round(date_time, 2)
            if row[1] == ' BS' or row[1] == ' BE':
                pass
            elif prevline and prevline[1] == ' BS' and len(row) == 3:
                a.writerow([ts, str(row[1]), str(row[2]), breath])
                breath += 1
            else:
                if len(row) != 2:
                    a.writerow([ts, str(row[1]), str(row[2]), 0])
            prevline = row


def main():
    start_time = time.time()
    if int(sys.argv[1]) == 1:
        append()
    elif int(sys.argv[1]) == 2:
        append2()
    print("--- dygraph file create in: %s seconds ---" % (time.time() - start_time))
main()
