"""
extract_breath_meta
~~~~~~~~~~~~~~~~~~~~~

Creates aptv files which are necessary for annotation purposes.

Essentially just grabs all the metadata in a raw breath file and sticks it
into a separate file that can be consumed by flask at execution.
"""
import argparse
import csv
from datetime import datetime
from itertools import groupby
import os
from os.path import basename, dirname, splitext
import time

from sklearn.linear_model import LinearRegression
from ventmap.breath_meta import get_experimental_breath_meta, get_production_breath_meta
from ventmap.raw_utils import extract_raw

from DCA import cal_slope_dyna,cal_slope_static,median_flow_dyna,find_flat_num,find_flat_df,repeatingNumbers
import defaults as config


class APTVFile(object):
    columns = [
        "bn",
        "vent_bn",
        "rel_bs",
        "abs_bs",
        "tvi",
        "tve",
        "tv_ratio",
        "e_time",
        "i_time",
        "peep",
        "peep_prev",
        "min_p",
        'pbit',
        'fbit_pbit',
        'slope_dyna',
        'slope_static',
        'flow_median',
    ]
    display_rows = [
        "tvi",
        "tve",
        "tv_ratio",
        "e_time",
        "i_time",
        "peep_prev",
        "min_p",
        "peep",
        "fbit_pbit",
        "slope_dyna",
        "slope_static",
        'flow_median',
        'pbit',
    ]

    def __init__(self, base_filename, base_file_is_processed):
        self.base_filename = base_filename
        base = basename(base_filename)
        base = splitext(base)[0]
        if not base_file_is_processed:
            apfile = base + '_atv.csv'
        else:
            apfile = '_'.join(base.split('_')[:-1]) + '_atv.csv'
        self.apfile = os.path.join(dirname(__file__), config.APTV_OUTPUT_DIR, apfile)

    def get_columns_idxs(self):
        return dict(zip(self.columns, list(range(len(self.columns)))))

    @classmethod
    def get_columns_idxs(self):
        return dict(zip(self.columns, list(range(len(self.columns)))))

    def read_aptv_file(self, start_bn, end_bn):
        with open(self.apfile, 'r') as aptv_file:
            aptv_reader = csv.reader(aptv_file, delimiter=',')
            start_offset, end_offset = 0, 0
            tvd = []

            for idx, row in enumerate(aptv_reader):
                if row[0] == start_bn:
                    start_offset = idx
                elif row[0] == end_bn:
                    end_offset = idx

                if int(start_bn) <= int(row[0]) <= int(end_bn):
                    tvd.append(row)

            if not tvd:
                raise NoAnnotationDataError(
                    "There is no annotation data to use. Please check the source file "
                    "to ensure it is properly formatted."
                )
            return tvd

    def write_base_file_breath_meta(self):
        peep_prev = 'N/A'
        rel_time = 0.02

        with open(self.base_filename, 'rU') as out, open(self.apfile, 'wt') as ap:
            generator = extract_raw(out, False)
            aptv_writer = csv.writer(ap, delimiter=',', quoting=csv.QUOTE_NONE)

            for breath in generator:
                meta = get_production_breath_meta(breath)
                meta_exp = get_experimental_breath_meta(breath)
                # set datetime format
                if len(breath['ts']) != 0:
                    desired_format = "%Y-%m-%d %H:%M:%S.%f"
                    as_dt = datetime.strptime(breath['ts'][0], "%Y-%m-%d %H-%M-%S.%f")
                    abs_bs_time = as_dt.strftime(desired_format)
                else:
                    abs_bs_time = ""

                tvi = round(meta[9], 1)
                tve = round(meta[10], 1)
                try:
                    tv_ratio = round(abs(float(tve / tvi)), 2)
                except ZeroDivisionError:
                    tv_ratio = 'inf'
                itime = round(meta[6], 2)
                etime = round(meta[7], 2)
                min_pressure = round(meta[35], 2)
                peep = round(meta[17], 2)
                fbit = meta[6]
                pbit = meta_exp[-1]
                fbit_pbit = fbit/pbit
                slope_dyna=cal_slope_dyna(breath)
                slope_static=cal_slope_static(breath)
                flow_median = median_flow_dyna(breath)
                vals = [
                    breath['rel_bn'],
                    breath['vent_bn'],
                    rel_time,
                    abs_bs_time,
                    tvi,
                    tve,
                    tv_ratio,
                    etime,
                    itime,
                    peep,
                    peep_prev,
                    min_pressure,
                    round(fbit_pbit, 2),
                    round(slope_dyna, 2),
                    round(slope_static, 2),
                    round(flow_median, 2),
                    round(pbit, 2),
                ]
                if len(vals) != len(self.columns):
                    raise Exception('number of columns does not match number of values trying to be written!')
                aptv_writer.writerow(vals)
                peep_prev = peep
                rel_time = round(rel_time + breath['frame_dur'], 2)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("filename")
    args = parser.parse_args()
    filename = args.filename

    start_time = time.time()

    aptv = APTVFile(args.filename, False)
    aptv.write_base_file_breath_meta()

    print("--- APTV file created in {} seconds ---".format(time.time() - start_time))


if __name__ == "__main__":
    main()
