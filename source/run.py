import csv
from datetime import datetime
from itertools import chain, islice
import json
import logging
import os
from os import listdir
from os.path import abspath, basename, dirname, isfile, join, splitext
import re
import shutil
from StringIO import StringIO
import subprocess
import sys
import time

from flask import make_response, render_template, Flask, url_for, redirect, request
import pandas as pd
import redis
from werkzeug import secure_filename

from forms import *
import defaults

app = Flask(__name__)
app.config.from_object(defaults)
try:
    app.config.from_pyfile('config.py', silent=True)
except IOError:  # If it's not there we're probably running a development server
    pass

cache = redis.StrictRedis(**app.config['REDIS'])
aptv_output_path = join(dirname(__file__), app.config['APTV_OUTPUT_DIR'])
export_output_path = join(dirname(__file__), app.config['EXPORT_OUTPUT_DIR'])
raw_output_path = join(dirname(__file__), app.config['RAW_OUTPUT_DIR'])
visualize_output_path = join(dirname(__file__), app.config['VISUALIZE_UPLOAD_FOLDER'])

onlyfiles = [f for f in listdir(raw_output_path) if isfile(join(raw_output_path, f))]

stream_handler = logging.StreamHandler()
stream_handler.setLevel(logging.WARNING)
app.logger.addHandler(stream_handler)

metadata = ['TVi', 'TVe', 'TVe/TVi', 'Previous-PEEP', 'PEEP', 'Min-Pressure', 'I-time', 'E-time']
ventmode_annos = ['vc', 'pc', 'prvc', 'ps', 'simv', 'pav', 'vs', 'cpap_sbt', 'aprv', 'other']
pva_annos = ['fa', 'dbl', 'bs', 'aNOS', 'co', 'su', 'mt', 'wNOS', 'dtpi', 'dtpa', 'vd']
view_anno_mapping = {
    'pva': {
        'graphical_ordering': pva_annos,
        'output_ordering': ["dbl", "mt", "bs", "dtpi", "dtpa", "fa", "co", "su", "vd", "aNOS", "wNOS"],
        'short_name': 'pva',
    },
    'ventmode': {
        'graphical_ordering': ventmode_annos,
        'output_ordering': ventmode_annos,
        'short_name': 'ventmode',
    },
}


class TVData(object):
    def __init__(self, b, tvi, tve, vent_bn, e_time, i_time, peep_prev='N/A', min_p='N/A', peep='N/A', rel_bs="", abs_bs=""):
        self.b = b
        self.tvi = tvi
        self.tve = tve
        self.vent_bn = vent_bn
        self.e_time = e_time
        self.peep = peep
        self.peep_prev = peep_prev
        self.min_p = min_p
        self.rel_bs = rel_bs
        self.abs_bs = abs_bs
        self.i_time = i_time


@app.template_filter("basename")
def basename(s):
    return os.path.basename(s).replace('"', '')


def sort_files(files):
    only_anno_files = filter(lambda f: len(f.split("_")) > 1, files)
    # a silly quick function but whatever
    key = lambda f: (f.split("_")[-2], int(f.split("_")[-1].replace(".csv", "")))
    return sorted(only_anno_files, key=key)


def create_mapped_diff(diff_annos):
    mapped_annos = dict()
    for anno in diff_annos:
        bn = int(anno.split('-')[0])
        async_type = anno.split('-')[1]
        try:
            mapped_annos[bn].append(async_type)
        except KeyError:
            mapped_annos[bn] = [async_type]
    return mapped_annos


def trunc(username, reader_filename, start, end, view_dict):
    base = basename(reader_filename)
    base = splitext(base)[0]
    annos_file = StringIO()

    tvfile = basename(reader_filename)
    tvfile = splitext(tvfile)[0].split('_')[:-1]
    tvfile = '_'.join(tvfile)
    tvfile = tvfile + "_atv.csv"
    tvfile = join(aptv_output_path, tvfile)
    anno_type = view_dict['anno_type']

    with open(tvfile, 'r') as aptv_file:
        aptv_reader = csv.reader(aptv_file, delimiter=',')
        writer = csv.writer(annos_file, delimiter=',')
        anno_keys = view_anno_mapping[anno_type]['output_ordering']
        writer.writerow(["BN", "vent BN", "rel time",
                         "abs time", "TVi", "e-time", "i-time",
                         "TVe", "TVe/TVi ratio",
                         "PEEP-prev", "minP", "PEEP"] + anno_keys)
        app.logger.info("Attempt to get breath range file")

        # Reduce memory imprint of this function by only picking the rows we want
        start_offset, end_offset = 0, 0
        tvd = []

        for idx, row in enumerate(aptv_reader):
            if row[0] == start:
                start_offset = idx
            elif row[0] == end:
                end_offset = idx
            if int(start) <= int(row[0]) <= int(end):
                tvd.append(TVData(*row))

        if not tvd:
            raise NoAnnotationDataError(
                "There is no annotation data to use. Please check the source file "
                "to ensure it is properly formatted."
            )
        saved_annotations = cache.smembers('apl_user_{}_file_{}_view_{}'.format(username, reader_filename, view_dict['viewname']))
        mapped_annotations = create_mapped_diff(saved_annotations)
        for tv_data in tvd:
            # We need to ensure that all empty tv_datas are filled with 0's.
            # Second we need to ensure that things are rounded correctly.
            # tvi/tve need to be rounded up/down to the nearest int. the
            # tvi/tve ratio needs to be 2 decimal places.
            tvi = round(float(tv_data.tvi))
            tve = round(abs(float(tv_data.tve)))
            try:
                ratio = round(abs(float(tve / tvi)), 2)
            except ZeroDivisionError:
                ratio = 'inf'
            anno_vals = [0] * len(anno_keys)
            for i in range(len(anno_keys)):
                if int(tv_data.b) in mapped_annotations and anno_keys[i] in mapped_annotations[int(tv_data.b)]:
                    anno_vals[i] = 1
            app.logger.debug("Iterate BN {}".format(tv_data.b))
            writer.writerow([
                int(tv_data.b), int(tv_data.vent_bn), tv_data.rel_bs,
                tv_data.abs_bs, tvi, float(tv_data.e_time),
                float(tv_data.i_time), tve, ratio,
                tv_data.peep_prev, tv_data.min_p, tv_data.peep,
            ] + anno_vals)
    annos_file.seek(0)
    return annos_file


def display_graphing(username, filename, anno_file, reviewer_1, reviewer_2, view):
    arr = []
    aptv_arr = []
    if anno_file:
        anno_file = pd.read_csv(anno_file)

    if reviewer_1 and reviewer_2:
        reviewer_1_annos = cache.smembers('apl_user_{}_file_{}_view_{}'.format(reviewer_1, basename(filename), view['viewname']))
        reviewer_2_annos = cache.smembers('apl_user_{}_file_{}_view_{}'.format(reviewer_2, basename(filename), view['viewname']))
        saved_annotations = list(reviewer_1_annos.intersection(reviewer_2_annos))
        diff_reviewer_1 = reviewer_1_annos.difference(reviewer_2_annos)
        diff_reviewer_2 = reviewer_2_annos.difference(reviewer_1_annos)
        map_diff_reviewer_1 = create_mapped_diff(diff_reviewer_1)
        map_diff_reviewer_2 = create_mapped_diff(diff_reviewer_2)
    else:
        reviewer_1 = None
        reviewer_2 = None
        redis_annos_key = 'apl_user_{}_file_{}_view_{}'.format(username, basename(filename), view['viewname'])
        saved_annotations = list(cache.smembers(redis_annos_key))

    final_filename = '"{}"'.format(filename)
    base = basename(filename)
    base = splitext(base)[0].split('_')[:-1]
    base = '_'.join(base)
    aptv = join(dirname(__file__), app.config['APTV_OUTPUT_DIR'], '{}_atv.csv'.format(base))
    file_name = "None"
    form = OutputAnnotationsForm(csrf_enabled=False)
    starttime = form.starttime.data
    endtime = form.endtime.data
    # Whatever, just prevent errors
    timetype = "relative"
    with open(aptv) as aptv_f:
        try:
            x_start = float(csv.reader(open(filename, "r")).next()[0])
        except:
            return "File is empty.", 404
        aptv_reader = csv.reader(aptv_f)
        for aptv_row in aptv_reader:
            # Ensures we zoom on the correct breath starting out.
            if aptv_row[-1]:
                timetype = "absolute"
                syntax = "%Y-%m-%d %H:%M:%S.%f"
                cur_time = time.mktime(
                    datetime.strptime(aptv_row[-1], syntax).timetuple()
                ) * 1e3 + (
                    datetime.strptime(aptv_row[-1], syntax).microsecond
                ) / 1e3
                # Compensate for .02 seconds plus some wiggle room
                cur_time = float(cur_time) + 60
            else:
                cur_time = aptv_row[-2]
            if float(cur_time) < x_start:
                continue
            bn = aptv_row[0]
            arr.append({
                "attachAtBottom": "true",
                "cssClass": "annotation",
                "height": "12",
                "series": "flow",
                "shortText": bn,
                "width": "35",
                # This HAS to be rounded to 2 decimal places otherwise
                # dygraphs won't perform annotations
                "x": round(float(cur_time), 2),
            })
            try:
                tv_ratio = abs(round(float(aptv_row[2]) / float(aptv_row[1]), 2))
            except ZeroDivisionError:
                tv_ratio = "inf"

            # In this case we are covering the time where we are annotating
            # the file and wish to see bs markers
            if tv_ratio != "inf" and tv_ratio < .9 and not isinstance(anno_file, pd.DataFrame) and not reviewer_1:
                x_mod = {"absolute": 100}.get(timetype, .1)
#                arr.append({
#                    "series": "flow",
#                    "width": 35,
#                    "height": 24,
#                    "cssClass": "norm-ts-anno",
#                    "x": round(round(float(cur_time), 2) + x_mod, 2),
#                    "shortText": "BS?",
#                })

            # This is when we are performing reconciliation
            elif reviewer_1 and reviewer_2:
                x_mod = {"absolute": 100}.get(timetype, .1)
                is_diff = int(bn) in map_diff_reviewer_1 or int(bn) in map_diff_reviewer_2
                if is_diff:
                    try:
                        reviewer_1_diffs = map_diff_reviewer_1[int(bn)]
                    except KeyError:
                        reviewer_1_diffs = dict()
                    try:
                        reviewer_2_diffs = map_diff_reviewer_2[int(bn)]
                    except KeyError:
                        reviewer_2_diffs = dict()

                    text = "{}: {}".format(reviewer_1, ", ".join(reviewer_1_diffs))
                    text += " ~~ {}: {}".format(reviewer_2, ", ".join(reviewer_2_diffs))
                    width = len(text) * 7.8
                    arr.append({
                        "series": "flow",
                        "width": width,
                        "height": 24,
                        "cssClass": 'pva-anno',
                        "x": round(round(float(cur_time), 2) + x_mod, 2),
                        "shortText": text,
                        'tickColor': 'red',
                    })
                else:
                    arr.append({
                        "series": "flow",
                        "width": 24,
                        "height": 24,
                        "cssClass": 'norm-ts-anno',
                        "x": round(round(float(cur_time), 2) + x_mod, 2),
                        "icon": 'static/images/checkmark.png',
                    })

            aptv_arr.append({
                "tvi": aptv_row[1],
                "tve": aptv_row[2],
                "tv_ratio": tv_ratio,
                "e_time": aptv_row[4],
                "i_time": aptv_row[5],
                "peep_prev": aptv_row[6],
                "min_p": aptv_row[7],
                "peep": aptv_row[8],
            })

    timetype = '"{}"'.format(timetype)
    if not arr or not aptv_arr:
        return "File has no data. Check for BEs and BS to see if it is corrupt.", 404

    resp = make_response(render_template(
        'apgraph.html', arr=arr, form=form, filename=final_filename,
        file_name=file_name, timetype=timetype, aptv_arr=aptv_arr,
        saved_annotations=saved_annotations, viewname=view['viewname'],
        annos_to_perform=view['annos'], anno_type=view['anno_type'],
        metadata_to_use=view['metadata'],
    ))
    return resp


def update_view(username, viewname):
    settings = cache.hgetall('apl_user_{}'.format(username))
    settings['view'] = viewname
    cache.hmset('apl_user_{}'.format(username), settings)


def setup_generic_views():
    if len(cache.smembers('views')) < 2:
        vm_view = {'viewname': 'ventmode', 'anno_type': 'ventmode', 'metadata': metadata, 'annos': ventmode_annos}
        pva_view = {
            'viewname': 'pva',
            'anno_type': 'pva',
            'metadata': metadata,
            'annos': ['fa', 'dbl', 'bs', 'aNOS', 'co', 'su', 'mt', 'wNOS']
        }
        cache.sadd('views', json.dumps(vm_view))
        cache.sadd('views', json.dumps(pva_view))


def get_view(viewname):
    for view in cache.smembers('views'):
        blob = json.loads(view)
        if viewname == blob['viewname']:
            for key in blob:
                if isinstance(blob[key], str):
                    blob[key] = str(blob[key])
                elif isinstance(blob[key], list):
                    blob[key] = [str(i) for i in blob[key]]
            return blob
    else:
        raise Exception('This shouldnt happen')


@app.route('/anno_output/<filename>', methods=["POST"])
def anno_output(filename):
    if "apl_username" not in request.cookies:
        return redirect(url_for('login', _external=True))
    username = request.cookies['apl_username']
    settings = cache.hgetall('apl_user_{}'.format(username))
    form = OutputAnnotationsForm(csrf_enabled=False)
    starttime = form.starttime.data if form.starttime.data else 1
    endtime = form.endtime.data if form.endtime.data else sys.maxsize
    view = get_view(settings['view'])
    try:
        anno_file = trunc(username, filename, starttime, endtime, view)
    except NoAnnotationDataError as err:
        return err.args[0], 400
    res = anno_file.read()
    response = make_response(res)
    response.headers["Content-Disposition"] = "attachment; filename={}-{}-output.csv".format(splitext(filename)[0], view_anno_mapping[view['anno_type']]['short_name'])
    response.headers['Content-Type'] = 'text/csv'
    return response


@app.route('/')
def home():
    if "apl_username" in request.cookies:
        return redirect(url_for('hello', _external=True))
    else:
        return redirect(url_for('login', _external=True))


@app.route('/login')
def login():
    if "apl_username" in request.cookies:
        return redirect(url_for('hello', _external=True))
    else:
        return render_template('login.html')


@app.route('/sign_in', methods=['POST'])
def sign_in():
    error_state = False
    if cache.hgetall('apl_user_{}'.format(request.form['username'])):
        to_hello = redirect(url_for('hello', _external=True))
        resp = make_response(to_hello)
        resp.set_cookie('apl_username', request.form['username'])
        return resp
    else:
        error_state = True
    return render_template('login.html', sign_in_error=error_state)


@app.route('/sign_up', methods=['POST'])
def sign_up():
    username = request.form['username']
    email = request.form['email']
    if len(re.search(r'(\w+)', username).groups()[0]) != len(username):
        return render_template('login.html', sign_up_alphanum_error=True, sign_up_checked=True)

    if cache.hgetall('apl_user_{}'.format(username)):
        return render_template('login.html', sign_up_already_used_error=True, sign_up_checked=True)
    cache.hmset('apl_user_{}'.format(username), {'email': email, 'view': 'pva'})
    to_hello = redirect(url_for('hello', _external=True))
    resp = make_response(to_hello)
    resp.set_cookie('apl_username', request.form['username'])
    return resp


@app.route('/logout', methods=['GET'])
def logout():
    if "apl_username" not in request.cookies:
        return redirect(url_for('login', _external=True))
    to_hello = redirect(url_for('hello', _external=True))
    resp = make_response(to_hello)
    resp.set_cookie('apl_username', '', expires=0)
    return resp


@app.route('/settings', methods=['GET', 'POST'])
def settings():
    if "apl_username" not in request.cookies:
        return redirect(url_for('login', _external=True))
    username = request.cookies['apl_username']
    form = SelectViewForm()
    all_views = cache.smembers('views')
    existing_views = [json.loads(i)['viewname'] for i in all_views]
    form.options.choices = [(v, v) for v in existing_views]
    view = {'viewname': None, 'anno_type': None, 'metadata': [], 'annos': []}
    if form.options.data != 'None':
        cache_idx = existing_views.index(form.options.data)
        view = json.loads(list(all_views)[cache_idx])
        update_view(username, form.options.data)
    elif 'viewname' in request.args:
        viewname = "{}-{}".format(username, request.args['viewname'])
        if viewname in existing_views:
            # XXX figure out how to provide error feedback
            raise Exception('XXX Need error feedback')
        view['viewname'] = viewname
        for item in request.args:
            if item in metadata:
                view['metadata'].append(item)
            elif item in pva_annos and not view['anno_type']:
                view['annos'].append(item)
                view['anno_type'] = 'pva'
            elif item in ventmode_annos and not view['anno_type']:
                view['annos'].append(item)
                view['anno_type'] = 'ventmode'
            elif (item in ventmode_annos and view['anno_type'] == 'ventmode') or (item in pva_annos and view['anno_type'] == 'pva'):
                view['annos'].append(item)
            elif (item in ventmode_annos and view['anno_type'] == 'pva') or (item in pva_annos and view['anno_type'] == 'ventmode'):
                return "Something went wrong; Click on Settings again and retry", 500

        cache.sadd('views', json.dumps(view))
        update_view(username, viewname)

    return render_template('settings.html', form=form, existing_view=view)


@app.route('/upload', methods=('GET', 'POST'))
def upload():
    if "apl_username" not in request.cookies:
        return redirect(url_for('login', _external=True))
    form = UploadForm(csrf_enabled=False)
    app.logger.debug(form.validate_on_submit())
    app.logger.debug(form.errors)
    if form.validate_on_submit():
        if form.ufile.data:
            filename = secure_filename(form.ufile.data.filename)
            file_path = join(
                dirname(__file__), app.config['RAW_UPLOAD_FOLDER'], filename
            )
            form.ufile.data.save(file_path)
    return render_template('upload.html', form=form)


@app.route('/delete', methods=('GET', 'POST'))
def delete():
    if "apl_username" not in request.cookies:
        return redirect(url_for('login', _external=True))
    onlyfiles = [
        f for f in listdir(raw_output_path)
        if isfile(join(raw_output_path, f))
    ]
    onlyfiles = sort_files(onlyfiles)
    form = DeleteMultiForm(csrf_enabled=False)
    form.options.choices = [(f, f) for f in onlyfiles]
    a = form.options.data
    if a:
        for i in range(0, len(a)):
            a[i] = join(
                abspath(raw_output_path), a[i])
            os.remove(a[i])
    return render_template('delete.html', form=form, a=a)


@app.route('/hello', methods=('GET', 'POST'))
def hello():
    setup_generic_views()
    if "apl_username" not in request.cookies:
        return redirect(url_for('login', _external=True))
    username = request.cookies['apl_username']
    settings = cache.hgetall('apl_user_{}'.format(username))
    view = get_view(settings['view'])
    onlyfiles = [
        f for f in listdir(raw_output_path) if isfile(
        join(raw_output_path, f))
    ]
    onlyfiles = sort_files(onlyfiles)
    form = SelectAnnoForm(csrf_enabled=False)
    form.options.choices = [(f, f) for f in onlyfiles]
    settings = cache.hgetall('apl_user_{}'.format(username))
    if form.validate_on_submit():
        filename = join(app.config['RAW_OUTPUT_DIR'], form.options.data)
        return display_graphing(username, filename, None, None, None, view)
    else:
        filename = None
    return render_template('viewing.html', form=form, filename=filename)


@app.route('/_clear', methods=['GET'])
def clear():
    if "apl_username" not in request.cookies:
        return redirect(url_for('login', _external=True))
    subprocess.Popen(['sh', 'clear.sh'])
    return 'files have been cleared'


@app.route('/visualize', methods=['GET', 'POST'])
def visualize():
    setup_generic_views()
    if "apl_username" not in request.cookies:
        return redirect(url_for('login', _external=True))
    username = request.cookies['apl_username']
    settings = cache.hgetall('apl_user_{}'.format(username))
    view = get_view(settings['view'])
    form = VisualizeForm(csrf_enabled=False)
    onlyfiles = [(f, f) for f in sort_files(listdir(raw_output_path))]
    form.raw_data_files.choices = onlyfiles
    onlyfiles = [(f, f) for f in sorted(listdir(app.config['VISUALIZE_UPLOAD_FOLDER']))]
    form.annotations.choices = onlyfiles

    raw_file = form.raw_data_files.data
    anno_file = form.annotations.data
    if form.validate_on_submit():
        raw_file = join(app.config['RAW_OUTPUT_DIR'], raw_file)
        anno_file = join(visualize_output_path, anno_file)
        return display_graphing(request.cookies['apl_username'], raw_file, anno_file, None, None, view)

    return render_template('visualize.html', form=form)


@app.route('/reconcile', methods=['GET', 'POST'])
def reconcile():
    setup_generic_views()
    if "apl_username" not in request.cookies:
        return redirect(url_for('login', _external=True))
    username = request.cookies['apl_username']
    settings = cache.hgetall('apl_user_{}'.format(username))
    view = get_view(settings['view'])
    form = ReconcileForm(csrf_enabled=False)
    # The right way to do this would be to select the file, and then select out
    # of a list of users that annotated the file, but for now just do this
    usernames = [
        (key.replace('apl_user_', ''), key.replace('apl_user_', ''))
        for key in cache.keys() if re.search(r'apl_user_\w+$', key)
    ]
    onlyfiles = [(f, f) for f in sort_files(listdir(raw_output_path))]
    form.raw_data_files.choices = onlyfiles
    form.reviewer_1.choices = usernames
    form.reviewer_2.choices = usernames

    if form.validate_on_submit():
        raw_file = form.raw_data_files.data
        reviewer_1 = form.reviewer_1.data
        reviewer_2 = form.reviewer_2.data
        raw_file = join(app.config['RAW_OUTPUT_DIR'], raw_file)
        return display_graphing(request.cookies['apl_username'], raw_file, None, reviewer_1, reviewer_2, view)

    return render_template('reconcile.html', form=form)


@app.route('/update_anno/<filename>/<bn>/<anno>/<switch>', methods=['POST'])
def update_anno(filename, bn, anno, switch):
    username = request.cookies['apl_username']
    view = cache.hgetall('apl_user_{}'.format(username))['view']
    redis_key = 'apl_user_{}_file_{}_view_{}'.format(username, basename(filename), view)
    redis_field = '{}-{}'.format(bn, anno)
    if switch == 'false':
        cache.srem(redis_key, redis_field)
    else:
        cache.sadd(redis_key, redis_field)
    return ""


@app.route('/update_annos/<filename>', methods=['POST'])
def update_annos(filename):
    username = request.cookies['apl_username']
    view = cache.hgetall('apl_user_{}'.format(username))['view']
    redis_annos_key = 'apl_user_{}_file_{}_view_{}'.format(username, basename(filename), view)
    saved_annos = set(cache.smembers(redis_annos_key))
    request_data = request.get_json()
    for anno in request_data:
        for bn in request_data[anno]:
            redis_field = '{}-{}'.format(bn, anno)
            if redis_field not in saved_annos:
                cache.sadd(redis_annos_key, redis_field)
    for saved in saved_annos:
        bn, anno_type = saved.split('-')
        bn = int(bn)
        if bn not in request_data[anno_type]:
            cache.srem(redis_annos_key, saved)
    return ""
