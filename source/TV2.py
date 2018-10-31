"""
TV2
~~~

Creates aptv files which are necessary for annotation purposes.

Essentially just grabs all the metadata in a raw breath file and sticks it
into a separate file that can be consumed by flask at execution.
"""
import argparse
import csv
import sys
import os
import json
from datetime import datetime, timedelta
from os.path import abspath, basename, dirname, splitext
import time

from scipy.integrate import simps
from ventmap.detection import detect_version_v2
from ventmap.SAM import findx0

import config

parser = argparse.ArgumentParser()
parser.add_argument("filename")
args = parser.parse_args()
filename = args.filename

base = basename(filename)
base = splitext(base)[0]
apfile = base + '_atv.csv'
apfile = os.path.join(dirname(__file__), config.APTV_OUTPUT_DIR, apfile)

N             = 2000
br            = 0
flow          = [0]*N
pressure      = [0]*N
t             = [0]*N
i             = 0
dt            = 0.02
lastb         = 0
count         = 0
ip            = 0
skip          = 0
suction       = 0
sskip         = 0
suctionc      = 0
sctime        = 0
scount        = 0
sstart        = 0
copy          = False
vent_bn       = 0
peep_prev     = 'N/A'
rel_time = 0.02
start_time = time.time()

with open (filename, 'rU') as out, open(apfile, 'wt') as ap:
    first_line = out.readline()
    bs_col, n_col, ts_1st_col, ts_1st_row = detect_version_v2(first_line)
    out.seek(0)
    sreader=csv.reader(out, delimiter=',')
    aptv_writer = csv.writer(ap, delimiter=',', quoting=csv.QUOTE_NONE)

    flow_idx = bs_col
    pressure_idx = bs_col + 1

    for row in sreader:
        if not row:
            continue
        rel_time += dt
        # checks if the row starts with BS. flow_idx is the same as bs_idx
        if 'BS' in row[bs_col].strip():
            rel_time -= dt
            vent_bn = int(row[pressure_idx].partition(':')[2].rstrip(','))
            copy = True
            br += 1
            rel_bs_time = round(rel_time, 2)
            if ts_1st_col:
                if len(row[0]) == 29:
                    abs_bs_time = row[0][:-3]
                elif len(row[0]) == 23:
                    abs_bs_time = row[0] + '001'
                else:
                    abs_bs_time = row[0]
            elif ts_1st_row:
                desired_format = "%Y-%m-%d %H:%M:%S.%f"
                as_dt = datetime.strptime(first_line.strip("\r\n"), "%Y-%m-%d-%H-%M-%S.%f")
                with_delta = as_dt + timedelta(seconds=rel_time)
                abs_bs_time = with_delta.strftime(desired_format)
            else:
                abs_bs_time = ""
        # if it's BE, calculate the title volume for that time period
        elif 'BE' in row[bs_col].strip():
            rel_time -= dt
            if not copy:
                continue
            copy = False
            x0 = findx0(t, flow, 0.5)
            if x0!=[]: #if x0 has a value, use the first one to mark end of breath
                i_end  = x0[0]
            else: #if breath doesn't cross 0 (eg. double trigger)
                i_end  = lastb
            IEI = t.index(i_end)
            BEI = t.index(lastb)
            i_flow = flow[0:IEI]
            e_flow = flow[IEI:BEI+1]
            TVi = simps(i_flow, dx=0.02)*1000/60
            i_time = round(len(i_flow) * 0.02, 2)
            e_time = round(len(e_flow) * 0.02, 2)
            if e_flow == []:
                TVe = 0
            else:
                TVe = simps(e_flow, dx=0.02)*1000/60
            # satisfies x01 - 1
            min_p_obs = pressure[5:IEI]
            # last 5 values of pressure
            peep_obs = pressure[BEI - 4:BEI+1]
            if min_p_obs and peep_obs:
                min_p = round(min(min_p_obs), 2)
                peep = round(sum(peep_obs) / 5.0, 2)
            else:
                min_p, peep = "N/A", "N/A"
            # write to file
            aptv_writer.writerow([
                int(br), round(TVi, 1), round(TVe, 1),
                vent_bn, e_time, i_time, peep_prev,
                min_p, peep, rel_bs_time, abs_bs_time,
            ])
            peep_prev = peep
            flow     = [0]*N
            pressure = [0]*N
            t        = [0]*N
            i        = 0
        # grabbing values
        elif copy:
            try:
                flow[i]     = float(row[flow_idx])
                pressure[i] = float(row[pressure_idx])
                t[i]        = float(i)*dt
                lastb = t[i]
                i           += 1
            except:
                continue

print("--- APTV file created in {} seconds ---".format(time.time() - start_time))
