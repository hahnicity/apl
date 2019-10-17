"""
preprocess_vwd
~~~~~~~~~~~~~~

Makes files that are compatible for consumption by dygraphs.
"""
from __future__ import print_function
import argparse
import csv
import os
import time
import datetime
from os.path import basename, splitext

from ventmap.raw_utils import extract_raw

import defaults as config


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('input_file')
    args = parser.parse_args()

    generator = extract_raw(open(args.input_file, "rbU"), False)

    base = basename(args.input_file)
    base = splitext(base)[0]
    filename = base +'_wt.csv'
    filename = os.path.join(os.path.dirname(__file__), config.DATA_DIR, filename)
    with open(filename, 'wb') as f:
        a = csv.writer(f, delimiter=',')

        bs_time = 0.02
        for breath in generator:
            if len(breath['ts']) != 0:
                bs_time = datetime.datetime.strptime(breath['ts'][0], "%Y-%m-%d %H-%M-%S.%f")
                t = time.mktime(bs_time.timetuple()) * 1e3 + bs_time.microsecond / 1e3
                dt = 20
                for i, obs in enumerate(breath['flow']):
                    # 20 corresponds with 20 milliseconds or .02 seconds
                    a.writerow(["{:0.2f}".format(round(t + (20*(i-1)), 2)), "{:0.2f}".format(obs), " {:0.2f}".format(breath['pressure'][i]), 0])
            else:  # we can only use rel time in this case
                for i, obs in enumerate(breath['flow']):
                    a.writerow(["{:0.2f}".format(round(bs_time + (.02*i), 2)), "{:0.2f}".format(obs), " {:0.2f}".format(breath['pressure'][i]), 0])
                bs_time = bs_time + breath['frame_dur']


if __name__ == '__main__':
    main()
