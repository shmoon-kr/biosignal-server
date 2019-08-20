import re
import csv
import json
import pytz
import os.path
import datetime
import requests
import MySQLdb
import tempfile
import random
import shutil
import pandas
import bisect
import dateutil
import numpy as np
from .forms import UploadFileForm, UploadReviewForm
from pyfluent.client import FluentSender
from ftplib import FTP
from itertools import product
from django.core.cache import cache
from django.conf import settings
from django.contrib.auth.models import User
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseNotFound, Http404
from django.template import loader
from django.shortcuts import get_object_or_404, render
from django.views.decorators.csrf import csrf_exempt
from sa_api.models import Device, Client, Bed, Channel, Room, FileRecorded, ClientBusSlot, Review, DeviceConfigPresetBed, DeviceConfigItem, AnesthesiaRecordEvent, NumberInfoFile, WaveInfoFile, SummaryFileRecorded, NumberGEC, NumberPIV, Annotation, AnnotationComment, AnnotationLike

tz = pytz.timezone(settings.TIME_ZONE)


def get_sidebar_menu(selected=None):

    r = dict()
    r['Dashboard'] = dict()
    r['Dashboard']['active'] = True if selected in ('dashboard_rosette', 'dashboard_etc', 'dashboard_trend') else False
    r['Dashboard']['submenu'] = list()
    r['Dashboard']['submenu'].append([selected == 'dashboard_rosette', 'Anesthesiology', '/dashboard?target=rosette'])
    r['Dashboard']['submenu'].append([selected == 'dashboard_etc', 'Etc.', '/dashboard?target=etc'])
    r['Dashboard']['submenu'].append([selected == 'dashboard_trend', 'Trend', '/dashboard?target=trend'])

    r['서관'] = dict()
    r['서관']['active'] = True if selected in ('B', 'C', 'D', 'E', 'WREC') else False
    r['서관']['submenu'] = list()
    r['서관']['submenu'].append([selected == 'B', 'B Rosette', '/summary_rosette?rosette=B'])
    r['서관']['submenu'].append([selected == 'C', 'C Rosette', '/summary_rosette?rosette=C'])
    r['서관']['submenu'].append([selected == 'D', 'D Rosette', '/summary_rosette?rosette=D'])
    r['서관']['submenu'].append([selected == 'E', 'E Rosette', '/summary_rosette?rosette=E'])
    r['서관']['submenu'].append([selected == 'WREC', 'Recovery', '/summary_rosette?rosette=WREC'])

    r['동관'] = dict()
    r['동관']['active'] = True if selected in ('F', 'G', 'H', 'I', 'L', 'EREC') else False
    r['동관']['submenu'] = list()
    r['동관']['submenu'].append([selected == 'F', 'F Rosette', '/summary_rosette?rosette=F'])
    r['동관']['submenu'].append([selected == 'G', 'G Rosette', '/summary_rosette?rosette=G'])
    r['동관']['submenu'].append([selected == 'H', 'H Rosette', '/summary_rosette?rosette=H'])
    r['동관']['submenu'].append([selected == 'I', 'I Rosette', '/summary_rosette?rosette=I'])
    r['동관']['submenu'].append([selected == 'L', 'L Rosette', '/summary_rosette?rosette=L'])
    r['동관']['submenu'].append([selected == 'EREC', 'Recovery', '/summary_rosette?rosette=EREC'])

    r['신관'] = dict()
    r['신관']['active'] = True if selected in ('J', 'K', 'NREC') else False
    r['신관']['submenu'] = list()
    r['신관']['submenu'].append([selected == 'J', 'J Rosette', '/summary_rosette?rosette=J'])
    r['신관']['submenu'].append([selected == 'K', 'K Rosette', '/summary_rosette?rosette=K'])
    r['신관']['submenu'].append([selected == 'NREC', 'Recovery', '/summary_rosette?rosette=NREC'])

    loc = list()
    for key, val in r.items():
        if val['active']:
            loc.append(key)
            for menu in val['submenu']:
                if menu[0]:
                    loc.append(menu[1])

    return r, loc


def get_agg_list():
    return ['MIN', 'MAX', 'AVG', 'COUNT']


def get_table_col_val_list():

    table_col_list = dict()
    table_col_list['summary_by_file'] = ['HR', 'TEMP', 'NIBP_SYS', 'NIBP_DIA', 'NIBP_MEAN', 'PLETH_SPO2']
    table_col_list['Philips/IntelliVue'] = ['ECG_HR', 'TEMP', 'NIBP_SBP', 'NIBP_DBP', 'NIBP_MBP', 'PLETH_SAT_O2']
    table_col_list['GE/Carescape'] = ['HR', 'BT_PA', 'NIBP_SBP', 'NIBP_DBP', 'NIBP_MBP', 'PLETH_SPO2']

    table_val_list = dict()
    table_val_list['summary_by_file'] = product(table_col_list['summary_by_file'], get_agg_list())
    table_val_list['Philips/IntelliVue'] = product(table_col_list['Philips/IntelliVue'], get_agg_list())
    table_val_list['GE/Carescape'] = product(table_col_list['GE/Carescape'], get_agg_list())

    return table_col_list, table_val_list


def convert_summary_data(col_list, data, by):
    new_col_list = list()
    table_col_list, table_val_list = get_table_col_val_list()
    tmp_r = list()

    col_dict = dict()
    for i, col in enumerate(col_list):
        col_dict[col] = i

    for row in data:
        tmp_row = list()
        for i, col in enumerate(row):
            if col is None:
                tmp_row.append(None)
            elif col_list[i].endswith('_COUNT'):
                tmp_row.append('{:,}'.format(col, ','))
            elif col_list[i].endswith('_AVG'):
                tmp_row.append("{0:.2f}".format(col))
            elif col_list[i] in ('TOTAL_DURATION', 'DURATION'):
                hours, remainder = divmod(col, 3600)
                minutes, seconds = divmod(remainder, 60)
                tmp_row.append("{:02}:{:02}:{:02}".format(int(hours), int(minutes), int(seconds)))
            else:
                tmp_row.append(col)
        tmp_r.append(tmp_row)

    if by == 'rosette':
        new_col_list.append("rosette")
    else:
        new_col_list.append("rosette <br /> bed")

    if by == 'roestte' or by == 'bed':
        new_col_list.append("FILE_COUNT")
    elif by == 'file':
        new_col_list.append("begin_date </br> end_date")

    if by == 'file':
        new_col_list.append("action")

    if by == 'rosette' or by == 'bed':
        new_col_list.append("TOTAL_DURATION </br> TOTAL_COUNT")
    elif by == 'file':
        new_col_list.append("DURATION </br> TOTAL_COUNT")

    for col in table_col_list['summary_by_file']:
        new_col_list.append("MAX(%s) </br> MIN(%s)" % (col, col))
        new_col_list.append("AVG(%s) </br> COUNT(%s)" % (col, col))

    r = list()

    for row in tmp_r:
        tmp_row = list()
        if by == 'rosette':
            tmp_row.append(row[col_dict["rosette"]])
        else:
            tmp_row.append("%s </br> %s" % (row[col_dict["rosette"]], row[col_dict["bed"]]))

        if by == 'rosette' or by == 'bed':
            tmp_row.append("%s" % row[col_dict["FILE_COUNT"]])
        else:
            tmp_row.append("%s </br> %s" % (row[col_dict["begin_date"]], row[col_dict["end_date"]]))

        if by == 'file':
            begin_date = row[col_dict["begin_date"]]
            file_path = os.path.join('/mnt/Data/CloudStation', row[col_dict["bed"]], begin_date.strftime('%y%m%d'))
            file_name = '%s_%s.vital' % (row[col_dict["bed"]], begin_date.strftime('%y%m%d_%H%M%S'))
            tmp_row.append('<a href="/review?file=%s">Review</a>' % file_name)
            if settings.SERVICE_CONFIGURATIONS['LOCAL_SERVER_NAME'] == 'AMC_Anesthesiology':
                if os.path.isfile(os.path.join(file_path, file_name)):
                    tmp_row[-1] += ' </br> <a href="/download_vital_file?bed=%s&begin_date=%s"> vital </a>' % (
                        row[col_dict["bed"]], str(begin_date)
                    )

        if by == 'rosette' or by == 'bed':
            tmp_row.append("%s </br> %s" % (row[col_dict["TOTAL_DURATION"]], row[col_dict["TOTAL_COUNT"]]))
        else:
            tmp_row.append("%s </br> %s" % (row[col_dict["DURATION"]], row[col_dict["TOTAL_COUNT"]]))

        for col in table_col_list['summary_by_file']:
            tmp_row.append("%s </br> %s" % (row[col_dict["%s_MAX" % col]], row[col_dict["%s_MIN" % col]]))
            tmp_row.append("%s </br> %s" % (row[col_dict["%s_AVG" % col]], row[col_dict["%s_COUNT" % col]]))
        r.append(tmp_row)

    return new_col_list, r


# Create your views here.

def file_upload_storage(date_string, bed_name, filepath):
    ftp = FTP(host=settings.SERVICE_CONFIGURATIONS['STORAGE_SERVER_HOSTNAME'], user=settings.SERVICE_CONFIGURATIONS['STORAGE_SERVER_USER'], passwd=settings.SERVICE_CONFIGURATIONS['STORAGE_SERVER_PASSWORD'])
    ftp.connect(host=settings.SERVICE_CONFIGURATIONS['STORAGE_SERVER_HOSTNAME'])
    ftp.login(user=settings.SERVICE_CONFIGURATIONS['STORAGE_SERVER_USER'], passwd=settings.SERVICE_CONFIGURATIONS['STORAGE_SERVER_PASSWORD'])
    ftp.cwd(settings.SERVICE_CONFIGURATIONS['STORAGE_SERVER_PATH'])
    if bed_name not in ftp.nlst():
        ftp.mkd(bed_name)
    ftp.cwd(bed_name)
    if date_string not in ftp.nlst():
        ftp.mkd(date_string)
    ftp.cwd(date_string)
    file = open(filepath, 'rb')
    ftp.storbinary('STOR '+os.path.basename(filepath), file)
    ftp.quit()
    return True


@csrf_exempt
def get_wavedata(request):
    record = get_object_or_404(FileRecorded, file_basename=request.GET.get("file"))
    device_code = request.GET.get("device_code")
    channel = request.GET.get("channel")
    dt = dateutil.parser.parse(request.GET.get("dt"))

    r_dict = dict()
    response_status = 200
    if device_code is not None and channel is not None:
        wif = get_object_or_404(WaveInfoFile, record=record, device__code=device_code, channel_name=channel)
        npz = cache.get(wif.file_path)
        if npz is None:
            npz = np.load(wif.file_path)
            npz = {'timestamp': npz['timestamp'], 'packet_pointer': npz['packet_pointer'], 'val': npz['val']}
            cache.set(wif.file_path, npz)
        r_dict['sampling_rate'] = wif.sampling_rate
        r_dict['timestamp'] = list()
        r_dict['data'] = list()
        st = bisect.bisect(npz['timestamp'], dt.timestamp() - 10)
        ed = bisect.bisect(npz['timestamp'], dt.timestamp() + 10)
    
        r_dict['timestamp'].append(str(datetime.datetime.fromtimestamp(npz['timestamp'][st])))
        r_dict['data'].append(list())
        for v in npz['val'][npz['packet_pointer'][st]:npz['packet_pointer'][ed]]:
            r_dict['data'][-1].append(round(float(v), 4))
    else:
        return HttpResponseBadRequest()

    return HttpResponse(json.dumps(r_dict, sort_keys=True, indent=4), content_type="application/json; charset=utf-8", status=response_status)


@csrf_exempt
def get_numberdata(request):
    device = get_object_or_404(Device, id=request.GET.get("device_id"))
    record = get_object_or_404(FileRecorded, file_basename=request.GET.get("file"))
    summary = get_object_or_404(SummaryFileRecorded, record=record)

    r_dict = dict()
    get_object_or_404(NumberInfoFile, record=record, device=device, db_load=True)
    if summary.main_device.displayed_name in ('GE/Carescape', 'Philips/IntelliVue'):
        col_list = list()
        col_list.append(summary.hr_channel)
        col_list.append('BT_PA' if summary.main_device.displayed_name == 'GE/Carescape' else 'TEMP')
        col_list.append(summary.bp_channel + '_SBP' if summary.bp_channel is not None else None)
        col_list.append(summary.bp_channel + '_DBP' if summary.bp_channel is not None else None)
        col_list.append(summary.bp_channel + '_MBP' if summary.bp_channel is not None else None)
        col_list.append('PLETH_SPO2' if summary.main_device.displayed_name == 'GE/Carescape' else 'PLETH_SAT_O2')
        color_preview = ['green', 'blue', 'red', 'orange', 'gold', 'aqua']

        if summary.main_device.displayed_name == 'GE/Carescape':
            data = NumberGEC.objects.filter(record=record).order_by('dt')
        elif summary.main_device.displayed_name == 'Philips/IntelliVue':
            data = NumberPIV.objects.filter(record=record).order_by('dt')
        else:
            assert False
    else:
        assert False

    if len(data):
        r_dict['device_displayed_name'] = summary.main_device.displayed_name
        r_dict['csv_download_params'] = 'file=%s&device=%s' % (summary.record.file_basename, summary.main_device.code)
        r_dict['timestamp'] = list()
        for col in col_list:
            if col is not None:
                r_dict[col] = list()
        for row in data:
            r_dict['timestamp'].append(str(row.dt.astimezone(tz)))
            for col in col_list:
                if col is not None:
                    if col == 'HR':
                        r_dict[col].append(row.HR)
                    elif col == 'ABP_HR':
                        r_dict[col].append(row.ABP_HR)
                    elif col == 'PLETH_HR':
                        r_dict[col].append(row.PLETH_HR)
                    elif col == 'ABP_HR':
                        r_dict[col].append(row.ABP_HR)
                    elif col == 'ABP_SBP':
                        r_dict[col].append(row.ABP_SBP)
                    elif col == 'ABP_DBP':
                        r_dict[col].append(row.ABP_DBP)
                    elif col == 'ABP_MBP':
                        r_dict[col].append(row.ABP_MBP)
                    elif col == 'NIBP_SBP':
                        r_dict[col].append(row.NIBP_SBP)
                    elif col == 'NIBP_DBP':
                        r_dict[col].append(row.NIBP_DBP)
                    elif col == 'NIBP_MBP':
                        r_dict[col].append(row.NIBP_MBP)
                    elif col == 'PLETH_SPO2':
                        r_dict[col].append(row.PLETH_SPO2)
                    elif col == 'PLETH_SAT_O2':
                        r_dict[col].append(row.PLETH_SAT_O2)
                    elif col == 'BT_PA':
                        r_dict[col].append(row.BT_PA)
                    elif col == 'TEMP':
                        r_dict[col].append(row.TEMP)
                    else:
                        assert False
        dataset = list()
        for i, col in enumerate(col_list):  # rgb(75, 192, 192)
            if col is not None:
                tmp_dataset = dict()
                tmp_dataset["label"] = col
                tmp_dataset["data"] = r_dict[col]
                tmp_dataset["fill"] = False
                tmp_dataset["pointRadius"] = 0
                tmp_dataset["borderColor"] = color_preview[i]
                tmp_dataset["lineTension"] = 0
                dataset.append(tmp_dataset)
        r_dict['dataset'] = dataset

    return HttpResponse(json.dumps(r_dict, sort_keys=True, indent=4), content_type="application/json; charset=utf-8",
                        status=200)


def get_annotation_body(request, record):
    r = list()
    for item in Annotation.objects.filter(record=record, dt__range=(record.begin_date, record.end_date)).order_by('dt'):
        tmp_annotation = dict()
        tmp_annotation['id'] = item.id
        tmp_annotation['dt'] = str(item.dt)
        tmp_annotation['method'] = item.method
        tmp_annotation['description'] = item.description
        tmp_annotation['category'] = ['None' if item.category_1 is None else item.category_1, 'None' if item.category_2 is None else item.category_2, 'None' if item.category_3 is None else item.category_3]
        tmp_annotation['like'] = list()
        tmp_annotation['dislike'] = list()
        tmp_annotation['comment'] = list()
        for like in AnnotationLike.objects.filter(annotation=item, like__in=(1, 2)):
            if like.like == 1:
                tmp_annotation['like'].append({'user_id': like.user.id, 'user_name': like.user.username})
            elif like.like == 2:
                tmp_annotation['dislike'].append({'user_id': like.user.id, 'user_name': like.user.username})
        for comment in AnnotationComment.objects.filter(annotation=item).order_by('dt'):
            tmp_annotation['comment'].append({'dt': str(comment.dt), 'user_name': comment.user.username, 'user_id': comment.user.id, 'comment': comment.comment})
        if request.user.id is not None:
            try:
                user_like = AnnotationLike.objects.get(annotation=item, user=request.user.id).like
                tmp_annotation['user_like'] = user_like
            except AnnotationLike.DoesNotExist:
                tmp_annotation['user_like'] = None

        r.append(tmp_annotation)
    return r


@csrf_exempt
def like_annotation(request):
    record = get_object_or_404(FileRecorded, file_basename=request.GET.get("file"))
    annotation = get_object_or_404(Annotation, id=request.GET.get("annotation_id"))
    user = User.objects.get(id=request.user.id)
    like, _ = AnnotationLike.objects.get_or_create(annotation=annotation, user=user)
    like.like = request.GET.get("like")
    like.save()
    result = get_annotation_body(request, record)
    return HttpResponse(json.dumps(result, sort_keys=True, indent=4), content_type="application/json; charset=utf-8",
                        status=200)


@csrf_exempt
def get_annotation(request):
    record = get_object_or_404(FileRecorded, file_basename=request.GET.get("file"))
    result = get_annotation_body(request, record)
    return HttpResponse(json.dumps(result, sort_keys=True, indent=4), content_type="application/json; charset=utf-8",
                        status=200)


@csrf_exempt
def delete_annotation(request):
    record = get_object_or_404(FileRecorded, file_basename=request.GET.get("file"))
    try:
        Annotation.objects.get(id=request.GET.get("id")).delete()
    except Annotation.DoesNotExist:
        pass
    result = get_annotation_body(request, record)
    return HttpResponse(json.dumps(result, sort_keys=True, indent=4), content_type="application/json; charset=utf-8",
                        status=200)


@csrf_exempt
def comment_annotation(request):
    record = get_object_or_404(FileRecorded, file_basename=request.GET.get("file"))
    annotation = get_object_or_404(Annotation, id=request.GET.get("annotation_id"))
    user = User.objects.get(id=request.user.id)
    comment = request.GET.get("comment")
    AnnotationComment.objects.create(annotation=annotation, user=user, comment=comment)
    result = get_annotation_body(request, record)
    return HttpResponse(json.dumps(result, sort_keys=True, indent=4), content_type="application/json; charset=utf-8",
                        status=200)


@csrf_exempt
def add_annotation(request):
    record = get_object_or_404(FileRecorded, file_basename=request.GET.get("file")) if request.GET.get("file") is not None else None
    bed = get_object_or_404(Bed, name=request.GET.get("bed")) if request.GET.get("bed") is not None else None
    if record is None and bed is None:
        return HttpResponseNotFound()
    if bed is None:
        bed = record.bed

    dt = request.GET.get("dt")
    desc = request.GET.get("desc")
    method = request.GET.get("method")
    category_1 = 'None' if request.GET.get("category_1") is None else request.GET.get("category_1")
    category_2 = 'None' if request.GET.get("category_2") is None else request.GET.get("category_2")
    category_3 = 'None' if request.GET.get("category_3") is None else request.GET.get("category_3")
    if dt is None or method is None:
        return HttpResponseBadRequest()
    dt = datetime.datetime.strptime(dt.replace('Z', '+0000'), "%Y-%m-%dT%H:%M:%S.%f%z")
    if desc is None:
        desc = ''

    Annotation.objects.create(dt=dt, bed=bed, method=method, description=desc, record=record, category_1=category_1, category_2=category_2, category_3=category_3)

    if record is not None:
        r_dict = get_annotation_body(request, record)
    else:
        r_dict = {'message': 'Annotations were not returned.'}

    return HttpResponse(json.dumps(r_dict, sort_keys=True, indent=4), content_type="application/json; charset=utf-8",
                        status=200)


@csrf_exempt
def download_vital_file(request):
    bed = request.GET.get("bed")
    begin_date = request.GET.get("begin_date")

    if bed is not None and begin_date is not None:
        if settings.SERVICE_CONFIGURATIONS['LOCAL_SERVER_NAME'] == 'AMC_Anesthesiology':
            begin_date = datetime.datetime.strptime(begin_date, '%Y-%m-%d %H:%M:%S')
            file_path = os.path.join('/mnt/Data/CloudStation', bed, begin_date.strftime('%y%m%d'))
            file_name = os.path.join('%s_%s.vital' % (bed, begin_date.strftime('%y%m%d_%H%M%S')))
            if os.path.isfile(os.path.join(file_path, file_name)):
                response = HttpResponse(open(os.path.join(file_path, file_name), 'rb'), content_type='application/x-vitalrecorder+gzip')
                response['Content-Disposition'] = 'attachment; filename="%s"' % file_name
                return response
            else:
                return HttpResponseNotFound('File Not Found.')
        else:
            return HttpResponseBadRequest('The function is not allowed in this site.')
    else:
        return HttpResponseBadRequest('Invalid parameters.')


@csrf_exempt
def download_csv_device(request):

    file = request.GET.get("file")
    device = request.GET.get("device")

    nif = get_object_or_404(NumberInfoFile, record__file_basename=file, device__code=device)

    try:
        npz = np.load(nif.file_path)
        csvfile = tempfile.TemporaryFile(mode='w+')
        cyclewriter = csv.writer(csvfile, delimiter=',', quotechar='|', quoting=csv.QUOTE_MINIMAL)
        title = list()
        title.append('dt')
        title.extend(npz['col_list'])
        cyclewriter.writerow(title)
        for i in range(len(npz['timestamp'])):
            tmp_row = list()
            tmp_row.append(str(datetime.datetime.fromtimestamp(npz['timestamp'][i])))
            tmp_row.extend(npz['number'][i, :])
            cyclewriter.writerow(tmp_row)
        csvfile.seek(0)

        filename = '%s_%s_%s.csv' % (nif.record.bed.name, nif.record.begin_date.astimezone(tz).strftime('%y%m%d_%H%M%S'), nif.device.code)

        response = HttpResponse(csvfile, content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename=%s' % filename
        return response
    except Exception as e:
        return HttpResponseBadRequest


@csrf_exempt
def review(request):

    file = request.GET.get("file")

    summary = get_object_or_404(SummaryFileRecorded, record__file_basename=file)
    record = summary.record
    dt = datetime.datetime.strptime(request.GET.get("dt"), "%Y-%m-%dT%H:%M:%S.%f%z") if request.GET.get("dt") is not None else None

    bed = record.bed.name
    rosette = record.bed.room.name
    begin_date = record.begin_date.astimezone(tz)
    end_date = record.end_date.astimezone(tz)

    if rosette is not None and bed is not None and begin_date is not None and end_date is not None:
        
        meta_data = dict()
        for wif in WaveInfoFile.objects.filter(record=record):
            if wif.device.displayed_name not in meta_data.keys():
                meta_data[wif.device.displayed_name] = dict()
                meta_data[wif.device.displayed_name]['id'] = wif.device_id
                meta_data[wif.device.displayed_name]['is_main'] = wif.device.is_main
                meta_data[wif.device.displayed_name]['waves'] = list()
                meta_data[wif.device.displayed_name]['number'] = False
            tmp_wave = dict()
            tmp_wave['id'] = wif.device_id
            tmp_wave['is_main'] = wif.device.is_main
            tmp_wave['device_code'] = wif.device.code
            tmp_wave['channel'] = wif.channel_name
            tmp_wave['sampling_rate'] = wif.sampling_rate
            tmp_wave['num_packets'] = wif.num_packets
            tmp_wave['file_path'] = wif.file_path
            meta_data[wif.device.displayed_name]['waves'].append(tmp_wave)
        for nif in NumberInfoFile.objects.filter(record=record):
            if nif.device.displayed_name not in meta_data.keys():
                meta_data[nif.device.displayed_name] = dict()
                meta_data[nif.device.displayed_name]['is_main'] = nif.device.is_main
                meta_data[nif.device.displayed_name]['id'] = nif.device_id
                meta_data[nif.device.displayed_name]['waves'] = list()
            meta_data[nif.device.displayed_name]['number'] = True
            meta_data[nif.device.displayed_name]['csv_download_params'] =\
                'file=%s&device=%s' % (summary.record.file_basename, summary.main_device.code)

        context = dict()
        context['dt'] = str(dt)
        context['vital_file'] = file
        context['meta_data'] = meta_data
        context['meta_data_json'] = json.dumps(meta_data, indent=4)
        context['bed'] = bed
        context['date'] = begin_date.strftime('%Y-%m-%d')
        context['user_json'] = json.dumps(
            {'name': request.user.username, 'id': request.user.id, 'is_authenticated': request.user.is_authenticated},
            indent=4
        )
        context['begin_date'] = str(begin_date)
        context['end_date'] = str(end_date)
        template = loader.get_template('preview.html')
        return HttpResponse(template.render(context, request))
    else:
        r_dict = dict()
        r_dict['REQUEST_PATH'] = request.path
        r_dict['METHOD'] = request.method
        r_dict['PARAM'] = request.GET
        r_dict['MESSAGE'] = 'Invalid parameters.'
        return HttpResponse(json.dumps(r_dict, sort_keys=True, indent=4), content_type="application/json; charset=utf-8", status=400)


@csrf_exempt
def dashboard(request):

    since = datetime.date(2019, 5, 7)

    target = request.GET.get('target')

    if target is None or target == 'rosette':
        beds_red = list()
        beds_orange = list()
        beds_green = list()
        beds_blue = list()
        beds_client = set()

        bed_re = re.compile('([B-L]|IPACU|OB|WREC|EREC|NREC|PICU1)-[0-9]{2}')

        clients_all = Client.objects.all()

        for client in clients_all:
            if bed_re.match(client.bed.name) if client.bed is not None else False:
                beds_client.add(client.bed.name)
                if client.color_info()[1] == 'red':
                    beds_red.append(client.bed.name)
                elif client.color_info()[1] == 'orange':
                    beds_orange.append(client.bed.name)
                elif client.status == Client.STATUS_RECORDING:
                    beds_blue.append(client.bed.name)
                else:
                    beds_green.append(client.bed.name)

        db = MySQLdb.connect(host=settings.SERVICE_CONFIGURATIONS['DB_SERVER_HOSTNAME'],
                             user=settings.SERVICE_CONFIGURATIONS['DB_SERVER_USER'],
                             password=settings.SERVICE_CONFIGURATIONS['DB_SERVER_PASSWORD'],
                             db=settings.SERVICE_CONFIGURATIONS['DB_SERVER_DATABASE'])
        cursor = db.cursor()
        cursor.execute('SELECT bed, status FROM legacy_bed_status')
        rows = cursor.fetchall()

        for row in rows:
            if row[0] not in beds_client:
                if row[1] == 'Green':
                    beds_green.append(row[0])
                elif row[1] == 'Red':
                    beds_red.append(row[0])

        template = loader.get_template('dashboard_rosette.html')
        sidebar_menu, loc = get_sidebar_menu('dashboard_rosette')
        context = {
            'loc': loc,
            'sidebar_menu': sidebar_menu,
            'since': str(since),
            'beds_red': json.dumps(beds_red),
            'beds_orange': json.dumps(beds_orange),
            'beds_green': json.dumps(beds_green),
            'beds_blue': json.dumps(beds_blue),
        }
        return HttpResponse(template.render(context, request))
    elif target == 'trend':
        dt_from = request.GET.get('begin_date')
        dt_to = request.GET.get('end_date')
        if dt_from is None:
            dt_from = datetime.datetime.now() - datetime.timedelta(days=7)
            dt_to = datetime.datetime.now()
        elif dt_to is None:
            dt_to = dt_from + datetime.timedelta(days=7)
        dt_from = dt_from.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(tz)
        dt_to = dt_to.astimezone(tz)

        label_dates = list()
        for i_dt in pandas.date_range(dt_from, dt_to):
            label_dates.append(str(i_dt.date()))
        label_dates_dict = dict()
        for i, label in enumerate(label_dates):
            label_dates_dict[label] = i

        data = dict()
        data['label_dates'] = label_dates
        data['collected_files'] = dict()
        data['collected_hours'] = dict()
        data['total_hours'] = dict()

        for summary in SummaryFileRecorded.objects.filter(record__begin_date__range=(dt_from, dt_to)):
            if summary.record.bed.room.name not in data['total_hours']:
                data['collected_files'][summary.record.bed.room.name] = [0] * len(label_dates)
                data['collected_hours'][summary.record.bed.room.name] = [0] * len(label_dates)
                data['total_hours'][summary.record.bed.room.name] = [0] * len(label_dates)
            data['collected_files'][summary.record.bed.room.name][label_dates_dict[str(summary.record.begin_date.astimezone(tz).date())]] += 1
            data['collected_hours'][summary.record.bed.room.name][label_dates_dict[str(summary.record.begin_date.astimezone(tz).date())]] += (summary.record.end_date - summary.record.begin_date).total_seconds()/3600

        tmp_data = dict()
        for summary in SummaryFileRecorded.objects.all():
            month = summary.record.begin_date.strftime('%Y-%m')
            if month not in tmp_data.keys():
                tmp_data[month] = {'collected_files': 0, 'collected_hours': 0}
            tmp_data[month]['collected_files'] += 1
            tmp_data[month]['collected_hours'] += (summary.record.end_date-summary.record.begin_date).total_seconds()/3600

        tmp_data = dict(sorted(tmp_data.items()))

        data['accumulative'] = dict()
        data['accumulative']['label_dates'] = list()
        data['accumulative']['collected_hours'] = list()
        data['accumulative']['collected_files'] = list()

        collected_hours = 0
        collected_files = 0
        for key, val in tmp_data.items():
            data['accumulative']['label_dates'].append(key)
            collected_hours += val['collected_hours']
            collected_files += val['collected_files']
            data['accumulative']['collected_hours'].append(collected_hours)
            data['accumulative']['collected_files'].append(collected_files)

        data['storage_usage'] = dict()
        data['storage_usage']['labels'] = ['Main Storage', 'NAS1 (Vol1)']
        storages = list()
        storages.append(shutil.disk_usage("/mnt/Data"))
        storages.append(shutil.disk_usage("/mnt/NAS1"))
        total = list()
        free = list()
        for storage in storages:
            total.append(storage[0] // 2**40)
            free.append(storage[2] // 2**40)
        data['storage_usage']['total'] = total
        data['storage_usage']['free'] = free

        template = loader.get_template('dashboard_trend.html')
        sidebar_menu, loc = get_sidebar_menu('dashboard_trend')
        context = {
            'loc': loc,
            'sidebar_menu': sidebar_menu,
            'since': str(since),
            'data': data,
            'data_json': json.dumps(data)
        }
        return HttpResponse(template.render(context, request))
    else:
        raise Http404()


@csrf_exempt
def summary_rosette(request):

    rosette = request.GET.get('rosette')
    dt_from = request.GET.get('begin_date')
    dt_to = request.GET.get('end_date')

    if dt_from is None:
        dt_from = datetime.datetime.now().astimezone(tz).replace(hour=0, minute=0, second=0, microsecond=0) - datetime.timedelta(days=6)
    if dt_to is None:
        dt_to = dt_from + datetime.timedelta(days=7)

    room = get_object_or_404(Room, name=rosette)
    beds = Bed.objects.filter(room=room).order_by('name')

    data = dict()
    data[rosette] = dict()
    bed_name = list()
    for bed in beds:
        bed_name.append(bed.name)
        data[bed.name] = dict()

    for key, val in data.items():
        val['date'] = list()
        val['total_duration'] = list()
        val['num_files'] = list()
        val['num_total_ops'] = list()
        val['num_effective_files'] = list()
        val['files'] = list()

    tmp_data = dict()
    tmp_data[rosette] = dict()
    for bed in beds:
        tmp_data[bed.name] = dict()
    for key, val in tmp_data.items():
        for dt in pandas.date_range(dt_from, dt_to + datetime.timedelta(days=-1)):
            val[dt.date()] = dict()
            val[dt.date()]['total_duration'] = datetime.timedelta()
            val[dt.date()]['num_files'] = 0
            val[dt.date()]['num_effective_files'] = 0

    records = FileRecorded.objects.filter(bed__room__name=rosette, begin_date__range=(dt_from, dt_to))
    for record in records:
        try:
            SummaryFileRecorded.objects.get(record=record)
            tmp_rosette = tmp_data[rosette][record.begin_date.astimezone(tz).date()]
            tmp_bed = tmp_data[record.bed.name][record.begin_date.astimezone(tz).date()]
            tmp_rosette['total_duration'] += record.end_date - record.begin_date
            tmp_bed['total_duration'] += record.end_date - record.begin_date
            tmp_rosette['num_effective_files'] += 1
            tmp_bed['num_effective_files'] += 1
        except SummaryFileRecorded.DoesNotExist:
            pass
        tmp_data[rosette][record.begin_date.astimezone(tz).date()]['num_files'] += 1
        tmp_data[record.bed.name][record.begin_date.astimezone(tz).date()]['num_files'] += 1

    for key, val_bed in tmp_data.items():
        for dt, val in val_bed.items():
            data[key]['date'].append(str(dt))
            data[key]['total_duration'].append(str(val['total_duration']))
            data[key]['num_files'].append(val['num_files'])
            data[key]['num_total_ops'].append(val['num_effective_files']*random.uniform(1.1, 1.2))
            data[key]['num_effective_files'].append(val['num_effective_files'])

    for record in FileRecorded.objects.filter(bed__room__name=room, begin_date__range=(dt_from, dt_to)).order_by('-begin_date'):
        tmp = [record.bed.name, record.file_basename]
        try:
            summary = SummaryFileRecorded.objects.get(record=record)
            tmp.append(str(record.end_date-record.begin_date))
            device_list = list()
            for ni in NumberInfoFile.objects.filter(record=record):
                device_list.append(ni.device.code)
            tmp.append(', '.join(device_list))
            tmp.append(summary.bp_channel)
            tmp.append(summary.hr_channel)
            tmp.append(format(summary.avg_hr, '.1f') if summary.avg_hr is not None else 'N/A')
            tmp.append(format(summary.avg_bt, '.1f') if summary.avg_bt is not None else 'N/A')
            tmp.append(format(summary.avg_spo2, '.1f') if summary.avg_spo2 is not None else 'N/A')
            tmp.append(format(summary.avg_sbp, '.1f') if summary.avg_sbp is not None else 'N/A')
            tmp.append(format(summary.avg_dbp, '.1f') if summary.avg_dbp is not None else 'N/A')
            tmp.append(format(summary.avg_mbp, '.1f') if summary.avg_mbp is not None else 'N/A')
        except SummaryFileRecorded.DoesNotExist:
            tmp.extend(['N/A'] * 10)
        data[rosette]['files'].append(tmp)
        data[record.bed.name]['files'].append(tmp)

    sidebar_menu, loc = get_sidebar_menu(rosette)

    template = loader.get_template('summary_rosette.html')
    context = {
        'data': data,
        'data_json': json.dumps(data),
        'loc': loc,
        'sidebar_menu': sidebar_menu
    }

    return HttpResponse(template.render(context, request))


@csrf_exempt
def summary_file(request):

    table_col_list, table_val_list = get_table_col_val_list()

    start_date = request.GET.get("start_date")
    end_date = request.GET.get("end_date")
    by = request.GET.get("by")

    params_list = list()
    if start_date is not None:
        params_list.append('start_date=%s' % start_date)
    if end_date is not None:
        params_list.append('end_date=%s' % end_date)

    log_dict = dict()
    log_dict['REMOTE_ADDR'] = request.META['REMOTE_ADDR']
    log_dict['SERVER_NAME'] = 'global' if settings.SERVICE_CONFIGURATIONS['SERVER_TYPE'] == 'global' else settings.SERVICE_CONFIGURATIONS['LOCAL_SERVER_NAME']
    log_dict['REQUEST_PATH'] = request.path
    log_dict['METHOD'] = request.method
    log_dict['PARAM'] = request.GET

    if not settings.SERVICE_CONFIGURATIONS['DB_SERVER']:
        fluent = FluentSender(settings.SERVICE_CONFIGURATIONS['LOG_SERVER_HOSTNAME'],
                              settings.SERVICE_CONFIGURATIONS['LOG_SERVER_PORT'], 'sa')
        fluent.send(log_dict, 'sa.' + settings.SERVICE_CONFIGURATIONS['SERVER_TYPE'])
        return HttpResponseBadRequest('The server does not run number DB service.')

    if start_date is None:
        start_date = tz.localize(datetime.datetime.now()) + datetime.timedelta(days=-1)
        start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
    else:
        start_date = tz.localize(datetime.datetime.strptime(start_date, '%Y-%m-%d'))

    if end_date is None:
        end_date = start_date + datetime.timedelta(days=1)
    else:
        end_date = tz.localize(datetime.datetime.strptime(end_date, '%Y-%m-%d'))

    if by is None or by not in ['rosette', 'bed', 'file']:
        by = 'file'

    db_start_date = str(start_date.replace(tzinfo=None))
    db_end_date = str(end_date.replace(tzinfo=None))

    if by == 'file':
        col_list = list()
        col_list_query = list()
        col_list.append('rosette')
        col_list_query.append('rosette')
        col_list.append('bed')
        col_list_query.append('bed')
        col_list.append('file_basename')
        col_list_query.append('file_basename')
        col_list.append('begin_date')
        col_list_query.append('begin_date')
        col_list.append('end_date')
        col_list_query.append('end_date')
        col_list.append('DURATION')
        col_list_query.append('TIMESTAMPDIFF(SECOND, begin_date, end_date) TOTAL_DURATION')
        col_list.append('TOTAL_COUNT')
        col_list_query.append('TOTAL_COUNT')

        for val in table_val_list['summary_by_file']:
            col_list.append('%s_%s' % (val[0], val[1]))
            col_list_query.append('%s_%s' % (val[0], val[1]))

        query = "SELECT %s FROM summary_by_file WHERE begin_date BETWEEN '%s' AND '%s' ORDER BY rosette, bed, begin_date" %\
                (', '.join(col_list_query), db_start_date, db_end_date)
    elif by in ('bed', 'rosette'):
        col_list = list()
        col_list_query = list()
        col_list.append('rosette')
        col_list_query.append('rosette')
        if by == 'bed':
            col_list.append('bed')
            col_list_query.append('bed')
            query_by = 'rosette, bed'
        elif by == 'rosette':
            query_by = 'rosette'
        else:
            assert False, "Unknown by parameter %s." % by
        col_list.append('FILE_COUNT')
        col_list_query.append('COUNT(file_basename)')
        col_list.append('TOTAL_DURATION')
        col_list_query.append('SUM(TIMESTAMPDIFF(SECOND, begin_date, end_date)) TOTAL_DURATION')
        col_list.append('TOTAL_COUNT')
        col_list_query.append('SUM(TOTAL_COUNT)')
        for val in table_val_list['summary_by_file']:
            col_list.append('%s_%s' % (val[0], val[1]))
            if val[1] in ('MAX', 'MIN'):
                col_list_query.append('%s(%s_%s) %s_%s' % (val[1], val[0], val[1], val[0], val[1]))
            elif val[1] == 'COUNT':
                col_list_query.append('SUM(%s_%s) %s_%s' % (val[0], val[1], val[0], val[1]))
            elif val[1] == 'AVG':
                col_list_query.append('SUM(%s_%s * %s_COUNT)/SUM(%s_COUNT) %s_%s' % (val[0], val[1], val[0], val[0], val[0], val[1]))
            else:
                assert False, "Unknown mysql function %s was used." % val[1]

        query = "SELECT %s FROM summary_by_file WHERE begin_date BETWEEN '%s' AND '%s'" % (', '.join(col_list_query), db_start_date, db_end_date)
        query += " GROUP BY %s ORDER BY %s" % (query_by, query_by)
    else:
        assert False

    db = MySQLdb.connect(host=settings.SERVICE_CONFIGURATIONS['DB_SERVER_HOSTNAME'],
                         user=settings.SERVICE_CONFIGURATIONS['DB_SERVER_USER'],
                         password=settings.SERVICE_CONFIGURATIONS['DB_SERVER_PASSWORD'],
                         db=settings.SERVICE_CONFIGURATIONS['DB_SERVER_DATABASE'])

    cursor = db.cursor()
    cursor.execute(query)
    result_table = cursor.fetchall()
    db.close()

    page_title = '%s, Summary of Collected Vital Data' % str(start_date.date())
    col_list, result_table = convert_summary_data(col_list, result_table, by)

    template = loader.get_template('summary.html')
    context = {
        'by_val': by,
        'start_date': str(start_date.date()),
        'col_title': col_list,
        'page_title': page_title,
        'result_table': result_table
    }

    return HttpResponse(template.render(context, request))


def search_vital_files(beds, date_from=None, date_to=None):

    r = list()

    try:
        client = Client.objects.get(name='Vital Recorder')
    except Client.DoesNotExist:
        raise ValueError('Vital Recorder client does not exists.')

    if date_from is None:
        date_to = datetime.date.today()
        date_from = date_to - datetime.timedelta(days=3)
    elif date_to is None:
        date_to = date_from

    for bed_name in beds:
        try:
            bed = Bed.objects.get(name=bed_name)
            for dt in pandas.date_range(date_from, date_to):
                if os.path.exists(os.path.join('data', bed.name, dt.strftime('%y%m%d'))):
                    bed_re = re.compile('%s_%s_[0-9]{6}.vital' % (bed.name, dt.strftime('%y%m%d')))
                    files = os.listdir(os.path.join('data', bed.name, dt.strftime('%y%m%d')))
                    for file in files:
                        if bed_re.match(file):
                            split_file = os.path.splitext(file)[0].split('_')
                            begin_date = datetime.datetime.strptime(split_file[1]+split_file[2], '%y%m%d%H%M%S').astimezone(tz)
                            record, created = FileRecorded.objects.get_or_create(file_basename=file, defaults={
                                'client': client,
                                'bed': bed,
                                'begin_date': begin_date,
                                'end_date': None,
                                'file_path': os.path.join('data', bed.name, dt.strftime('%y%m%d'), file),
                                'method': 1
                            })
                            if created:
                                r.append(record)
        except Bed.DoesNotExist:
            pass

    return r


@csrf_exempt
def register_vital_file(request):

    row = list()
    file_basename = request.GET.get("device_type")
    file_path = os.path.join('data', row[3], row[4].strftime('%y%m%d'), row[1])
    is_exists = os.path.isfile(file_path)
    begin_date = tz.localize(row[4])
    end_date = tz.localize(row[5])
    if is_exists:
        bed = Bed.objects.get(name=row[3])
        client = Client.objects.get(bed=bed)
        recorded = FileRecorded.objects.get_or_create(method=0, bed=bed, file_basename=row[1], client=client,
                                                      begin_date=begin_date, end_date=end_date, file_path=file_path)
    return


# Main body of device_info API function
def device_info_body(request, api_type):

    device_type = request.GET.get("device_type")
    r_dict = dict()
    log_dict = dict()
    log_dict['REMOTE_ADDR'] = request.META['REMOTE_ADDR']
    log_dict['SERVER_NAME'] = 'global' if settings.SERVICE_CONFIGURATIONS['SERVER_TYPE'] == 'global' else settings.SERVICE_CONFIGURATIONS['LOCAL_SERVER_NAME']
    log_dict['CLIENT_TYPE'] = api_type
    log_dict['REQUEST_PATH'] = request.path
    log_dict['METHOD'] = request.method
    log_dict['PARAM'] = request.GET
    response_status = 200

    if device_type is not None:
        target_device, created = Device.objects.get_or_create(device_type=device_type, defaults={'displayed_name': device_type})
        if created and settings.SERVICE_CONFIGURATIONS['SERVER_TYPE'] == 'local':
            result = requests.get('http://%s:%d/server/device_info' % (
            settings.SERVICE_CONFIGURATIONS['GLOBAL_SERVER_HOSTNAME'],
            settings.SERVICE_CONFIGURATIONS['GLOBAL_SERVER_PORT']), params=request.GET)
            if int(result.status_code / 100) != 2:
                r_dict['success'] = False
                r_dict['message'] = 'A Global API server returned status code %d' % result.status_code
                response_status = 500
            else:
                server_result = json.loads(result.content.decode('utf-8'))
                r_dict['device_type'] = target_device.device_type = server_result['device_type']
                r_dict['displayed_name'] = target_device.displayed_name = server_result['displayed_name']
                r_dict['is_main'] = target_device.is_main = server_result['is_main']
                target_device.save()
                r_dict['success'] = True
                r_dict['message'] = 'Device information was acquired from a global server.'
        else:
            r_dict['dt_update'] = target_device.dt_update.astimezone(tz).isoformat()
            r_dict['device_type'] = target_device.device_type
            r_dict['displayed_name'] = target_device.displayed_name
            r_dict['is_main'] = target_device.is_main
            r_dict['success'] = True
            if created:
                r_dict['message'] = 'New device was added.'
            else:
                r_dict['message'] = 'Device information was returned correctly.'
    else:
        r_dict['success'] = False
        r_dict['message'] = 'Requested device type is none.'
        response_status = 400

    log_dict['RESPONSE_STATUS'] = response_status
    log_dict['RESULT'] = r_dict

    fluent = FluentSender(settings.SERVICE_CONFIGURATIONS['LOG_SERVER_HOSTNAME'], settings.SERVICE_CONFIGURATIONS['LOG_SERVER_PORT'], 'sa')
    fluent.send(log_dict, 'sa.' + settings.SERVICE_CONFIGURATIONS['SERVER_TYPE'])

    return HttpResponse(json.dumps(r_dict, sort_keys=True, indent=4), content_type="application/json; charset=utf-8", status=response_status)


# When a local server requested for device information.
# This function could be called only in a global server.
@csrf_exempt
def device_info_server(request):

    if settings.SERVICE_CONFIGURATIONS['SERVER_TYPE'] != 'global':
        r_dict = dict()
        r_dict['success'] = False
        r_dict['message'] = 'A local server received a server API request.'
        response_status = 400
        log_dict = dict()
        log_dict['REMOTE_ADDR'] = request.META['REMOTE_ADDR']
        log_dict['SERVER_NAME'] = settings.SERVICE_CONFIGURATIONS['LOCAL_SERVER_NAME']
        log_dict['CLIENT_TYPE'] = 'server'
        log_dict['REQUEST_PATH'] = request.path
        log_dict['METHOD'] = request.method
        log_dict['PARAM'] = request.GET
        log_dict['RESPONSE_STATUS'] = response_status
        log_dict['RESULT'] = r_dict
        fluent = FluentSender(settings.SERVICE_CONFIGURATIONS['LOG_SERVER_HOSTNAME'],
                              settings.SERVICE_CONFIGURATIONS['LOG_SERVER_PORT'], 'sa')
        fluent.send(log_dict, 'sa.' + settings.SERVICE_CONFIGURATIONS['SERVER_TYPE'])
        return HttpResponse(json.dumps(r_dict, sort_keys=True, indent=4), content_type="application/json; charset=utf-8", status=response_status)

    return device_info_body(request, 'server')


# When a client requested for device information.
# This function could be called either in a global server or in a local server.
@csrf_exempt
def device_info_client(request):

    return device_info_body(request, 'client')


def device_list_body(request, api_type):

    tz = pytz.timezone(settings.TIME_ZONE)

    r_dict = dict()
    log_dict = dict()
    log_dict['REMOTE_ADDR'] = request.META['REMOTE_ADDR']
    log_dict['SERVER_NAME'] = 'global' if settings.SERVICE_CONFIGURATIONS['SERVER_TYPE'] == 'global' else settings.SERVICE_CONFIGURATIONS['LOCAL_SERVER_NAME']
    log_dict['CLIENT_TYPE'] = api_type
    log_dict['REQUEST_PATH'] = request.path
    log_dict['METHOD'] = request.method
    log_dict['PARAM'] = request.GET
    response_status = 200

    all_devices = Device.objects.all()
    device_dt_update = dict()
    for device in all_devices:
        device_dt_update[device.device_type] = device.dt_update.astimezone(tz).isoformat()

    r_dict['dt_update'] = device_dt_update
    r_dict['success'] = True
    r_dict['message'] = 'Last updated dates of all devices were returned successfully.'

    log_dict['RESPONSE_STATUS'] = response_status
    log_dict['RESULT'] = r_dict

    fluent = FluentSender(settings.SERVICE_CONFIGURATIONS['LOG_SERVER_HOSTNAME'], settings.SERVICE_CONFIGURATIONS['LOG_SERVER_PORT'], 'sa')
    fluent.send(log_dict, 'sa.' + settings.SERVICE_CONFIGURATIONS['SERVER_TYPE'])

    return HttpResponse(json.dumps(r_dict, sort_keys=True, indent=4), content_type="application/json; charset=utf-8", status=response_status)

# When a local server requested for device list.
@csrf_exempt
def device_list_server(request):

    if settings.SERVICE_CONFIGURATIONS['SERVER_TYPE'] != 'global':
        r_dict = dict()
        r_dict['success'] = False
        r_dict['message'] = 'A local server received a server API request.'
        response_status = 400
        log_dict = dict()
        log_dict['REMOTE_ADDR'] = request.META['REMOTE_ADDR']
        log_dict['SERVER_NAME'] = settings.SERVICE_CONFIGURATIONS['LOCAL_SERVER_NAME']
        log_dict['CLIENT_TYPE'] = 'server'
        log_dict['REQUEST_PATH'] = request.path
        log_dict['METHOD'] = request.method
        log_dict['PARAM'] = request.GET
        log_dict['RESPONSE_STATUS'] = response_status
        log_dict['RESULT'] = r_dict
        fluent = FluentSender(settings.SERVICE_CONFIGURATIONS['LOG_SERVER_HOSTNAME'],
                              settings.SERVICE_CONFIGURATIONS['LOG_SERVER_PORT'], 'sa')
        fluent.send(log_dict, 'sa.' + settings.SERVICE_CONFIGURATIONS['SERVER_TYPE'])
        return HttpResponse(json.dumps(r_dict, sort_keys=True, indent=4), content_type="application/json; charset=utf-8", status=response_status)

    return device_list_body(request, 'server')


# When a client requested for device list.
# This function could be called either in a global server or in a local server.
@csrf_exempt
def device_list_client(request):

    return device_list_body(request, 'client')


# Main body of device_info API function
def channel_info_body(request, api_type):

    tz = pytz.timezone(settings.TIME_ZONE)

    r_dict = dict()
    log_dict = dict()
    log_dict['REMOTE_ADDR'] = request.META['REMOTE_ADDR']
    log_dict['SERVER_NAME'] = 'global' if settings.SERVICE_CONFIGURATIONS['SERVER_TYPE'] == 'global' else settings.SERVICE_CONFIGURATIONS['LOCAL_SERVER_NAME']
    log_dict['CLIENT_TYPE'] = api_type
    log_dict['REQUEST_PATH'] = request.path
    log_dict['METHOD'] = request.method
    log_dict['PARAM'] = request.GET
    response_status = 200

    device_type = request.GET.get("device_type")
    channel_name = request.GET.get("channel_name")

    if device_type is not None and channel_name is not None:
        target_device, _ = Device.objects.get_or_create(device_type=device_type, defaults={'displayed_name': device_type})
        try:
            target_channel = Channel.objects.get(name=channel_name, device=target_device)
            r_dict['success'] = True
            if target_channel.is_unknown:
                r_dict['message'] = 'Channel information was not configured by an admin.'
            else:
                r_dict['message'] = 'Channel information was returned correctly.'
        except Channel.DoesNotExist:
            target_channel = Channel(name=channel_name, device=target_device)
            if settings.SERVICE_CONFIGURATIONS['SERVER_TYPE'] == 'global':
                r_dict['success'] = True
                r_dict['message'] = 'A new channel was added.'
            else:
                result = requests.get('http://%s:%d/server/channel_info' %
                                      (settings.SERVICE_CONFIGURATIONS['GLOBAL_SERVER_HOSTNAME'], settings.SERVICE_CONFIGURATIONS['GLOBAL_SERVER_PORT']), params=request.GET)
                if int(result.status_code/100) != 2:
                    r_dict['success'] = False
                    r_dict['message'] = 'A Global API server returned status code %d' % ( result.status_code )
                    response_status = 500
                else:
                    server_result = json.loads(result.content.decode('utf-8'))
                    target_channel.is_unknown = server_result['is_unknown']
                    target_channel.use_custom_setting = server_result['use_custom_setting']
                    target_channel.name = server_result['channel_name']
                    target_channel.device_type = server_result['device_type']
                    target_channel.abbreviation = server_result['abbreviation']
                    target_channel.recording_type = server_result['recording_type']
                    target_channel.recording_format = server_result['recording_format']
                    target_channel.unit = server_result['unit']
                    target_channel.minval = server_result['minval']
                    target_channel.maxval = server_result['maxval']
                    target_channel.color_a = server_result['color_a']
                    target_channel.color_r = server_result['color_r']
                    target_channel.color_g = server_result['color_g']
                    target_channel.color_b = server_result['color_b']
                    target_channel.srate = server_result['srate']
                    target_channel.adc_gain = server_result['adc_gain']
                    target_channel.adc_offset = server_result['adc_offset']
                    target_channel.mon_type = server_result['mon_type']
                    r_dict['success'] = True
                    r_dict['message'] = 'Channel information was acquired from a global server.'
            target_channel.save()
            r_dict['dt_update'] = target_channel.dt_update.astimezone(tz).isoformat()
        r_dict['dt_update'] = target_channel.dt_update.astimezone(tz).isoformat()
        r_dict['is_unknown'] = target_channel.is_unknown
        r_dict['use_custom_setting'] = target_channel.use_custom_setting
        r_dict['channel_name'] = target_channel.name
        r_dict['device_type'] = target_channel.device.device_type
        r_dict['abbreviation'] = target_channel.abbreviation
        r_dict['recording_type'] = target_channel.recording_type
        r_dict['recording_format'] = target_channel.recording_format
        r_dict['unit'] = target_channel.unit
        r_dict['minval'] = target_channel.minval
        r_dict['maxval'] = target_channel.maxval
        r_dict['color_a'] = target_channel.color_a
        r_dict['color_r'] = target_channel.color_r
        r_dict['color_g'] = target_channel.color_g
        r_dict['color_b'] = target_channel.color_b
        r_dict['srate'] = target_channel.srate
        r_dict['adc_gain'] = target_channel.adc_gain
        r_dict['adc_offset'] = target_channel.adc_offset
        r_dict['mon_type'] = target_channel.mon_type
    else:
        r_dict['success'] = False
        r_dict['message'] = 'Requested device type or channel name is none.'
        response_status = 400

    log_dict['RESPONSE_STATUS'] = response_status
    log_dict['RESULT'] = r_dict

    fluent = FluentSender(settings.SERVICE_CONFIGURATIONS['LOG_SERVER_HOSTNAME'], settings.SERVICE_CONFIGURATIONS['LOG_SERVER_PORT'], 'sa')
    fluent.send(log_dict, 'sa.' + settings.SERVICE_CONFIGURATIONS['SERVER_TYPE'])

    return HttpResponse(json.dumps(r_dict, sort_keys=True, indent=4), content_type="application/json; charset=utf-8", status=response_status)


# When a local server requested for channel information.
# This function could be called only in a global server.
@csrf_exempt
def channel_info_server(request):

    if settings.SERVICE_CONFIGURATIONS['SERVER_TYPE'] != 'global':
        r_dict = dict()
        r_dict['success'] = False
        r_dict['message'] = 'A local server received a server API request.'
        response_status = 400
        log_dict = dict()
        log_dict['REMOTE_ADDR'] = request.META['REMOTE_ADDR']
        log_dict['SERVER_NAME'] = settings.SERVICE_CONFIGURATIONS['LOCAL_SERVER_NAME']
        log_dict['CLIENT_TYPE'] = 'server'
        log_dict['REQUEST_PATH'] = request.path
        log_dict['METHOD'] = request.method
        log_dict['PARAM'] = request.GET
        log_dict['RESPONSE_STATUS'] = response_status
        log_dict['RESULT'] = r_dict
        fluent = FluentSender(settings.SERVICE_CONFIGURATIONS['LOG_SERVER_HOSTNAME'],
                              settings.SERVICE_CONFIGURATIONS['LOG_SERVER_PORT'], 'sa')
        fluent.send(log_dict, 'sa.' + settings.SERVICE_CONFIGURATIONS['SERVER_TYPE'])
        return HttpResponse(json.dumps(r_dict, sort_keys=True, indent=4), content_type="application/json; charset=utf-8", status=response_status)

    return channel_info_body(request, 'server')


# When a client requested for channel information.
# This function could be called either in a global server or in a local server.
@csrf_exempt
def channel_info_client(request):

    return channel_info_body(request, 'client')


def channel_list_body(request, api_type):

    tz = pytz.timezone(settings.TIME_ZONE)

    r_dict = dict()
    log_dict = dict()
    log_dict['REMOTE_ADDR'] = request.META['REMOTE_ADDR']
    log_dict['SERVER_NAME'] = 'global' if settings.SERVICE_CONFIGURATIONS['SERVER_TYPE'] == 'global' else settings.SERVICE_CONFIGURATIONS['LOCAL_SERVER_NAME']
    log_dict['CLIENT_TYPE'] = api_type
    log_dict['REQUEST_PATH'] = request.path
    log_dict['METHOD'] = request.method
    log_dict['PARAM'] = request.GET
    response_status = 200

    device_type = request.GET.get("device_type")

    if device_type is not None:
        try:
            target_device = Device.objects.get(device_type=device_type)
            requested_channels = Channel.objects.filter(device=target_device)
            channel_dt_update = dict()
            for channel in requested_channels:
                channel_dt_update[channel.name] = channel.dt_update.astimezone(tz).isoformat()
            r_dict['dt_update'] = channel_dt_update
            r_dict['success'] = True
            r_dict['message'] = 'Last updated dates of the requested device channels were returned successfully.'
        except Device.DoesNotExist:
            r_dict['success'] = False
            r_dict['message'] = 'Requested device type does not exists.'
            response_status = 400
    else:
        r_dict['success'] = False
        r_dict['message'] = 'Requested device type is none.'
        response_status = 400

    log_dict['RESPONSE_STATUS'] = response_status
    log_dict['RESULT'] = r_dict

    fluent = FluentSender(settings.SERVICE_CONFIGURATIONS['LOG_SERVER_HOSTNAME'], settings.SERVICE_CONFIGURATIONS['LOG_SERVER_PORT'], 'sa')
    fluent.send(log_dict, 'sa.' + settings.SERVICE_CONFIGURATIONS['SERVER_TYPE'])

    return HttpResponse(json.dumps(r_dict, sort_keys=True, indent=4), content_type="application/json; charset=utf-8", status=response_status)


# When a local server requested for device information.
# This function could be called only in a global server.
@csrf_exempt
def channel_list_server(request):

    if settings.SERVICE_CONFIGURATIONS['SERVER_TYPE'] != 'global':
        r_dict = dict()
        r_dict['success'] = False
        r_dict['message'] = 'A local server received a server API request.'
        response_status = 400
        log_dict = dict()
        log_dict['REMOTE_ADDR'] = request.META['REMOTE_ADDR']
        log_dict['SERVER_NAME'] = settings.SERVICE_CONFIGURATIONS['LOCAL_SERVER_NAME']
        log_dict['CLIENT_TYPE'] = 'server'
        log_dict['REQUEST_PATH'] = request.path
        log_dict['METHOD'] = request.method
        log_dict['PARAM'] = request.GET
        log_dict['RESPONSE_STATUS'] = response_status
        log_dict['RESULT'] = r_dict
        fluent = FluentSender(settings.SERVICE_CONFIGURATIONS['LOG_SERVER_HOSTNAME'],
                              settings.SERVICE_CONFIGURATIONS['LOG_SERVER_PORT'], 'sa')
        fluent.send(log_dict, 'sa.' + settings.SERVICE_CONFIGURATIONS['SERVER_TYPE'])
        return HttpResponse(json.dumps(r_dict, sort_keys=True, indent=4), content_type="application/json; charset=utf-8", status=response_status)

    return channel_list_body(request, 'server')


# When a client requested for device information.
# This function could be called either in a global server or in a local server.
@csrf_exempt
def channel_list_client(request):

    return channel_list_body(request, 'client')


@csrf_exempt
def client_info_body(request):

    r_dict = dict()
    log_dict = dict()
    log_dict['REMOTE_ADDR'] = request.META['REMOTE_ADDR']
    log_dict['SERVER_NAME'] = 'global' if settings.SERVICE_CONFIGURATIONS['SERVER_TYPE'] == 'global' else settings.SERVICE_CONFIGURATIONS['LOCAL_SERVER_NAME']
    log_dict['CLIENT_TYPE'] = 'client'
    log_dict['REQUEST_PATH'] = request.path
    log_dict['METHOD'] = request.method
    log_dict['PARAM'] = request.GET
    response_status = 200

    mac = request.GET.get('mac')
    if mac is not None:
        try:
            target_client = Client.objects.get(mac=mac)
            target_client.save()
            device_config = dict()
            presets = DeviceConfigPresetBed.objects.filter(bed=target_client.bed)
            for preset in presets:
                device_config[preset.preset.device.device_type] = dict()
                configitems = DeviceConfigItem.objects.filter(preset=preset.preset)
                for configitem in configitems:
                    device_config[preset.preset.device.device_type][configitem.variable] = configitem.value
            r_dict['device_config_info'] = device_config
            r_dict['client_name'] = target_client.name
            r_dict['bed_name'] = target_client.bed.name
            r_dict['bed_id'] = target_client.bed_id
            r_dict['room_name'] = target_client.bed.room.name
            r_dict['room_id'] = target_client.bed.room_id
            r_dict['success'] = True
            r_dict['message'] = 'Client information was returned correctly.'
        except Client.DoesNotExist:
            if settings.SERVICE_CONFIGURATIONS['SERVER_TYPE'] == 'global':
                unknown_room, _ = Room.objects.get_or_create(name='Unknown')
                unknown_bed, _ = Bed.objects.get_or_create(name='Unknown', room=unknown_room)
                new_client = Client.objects.create(mac=mac, name='Unknown', bed=unknown_bed)
                new_client.save()
                r_dict['client_name'] = new_client.name
                r_dict['bed_name'] = new_client.bed.name
                r_dict['room_name'] = new_client.bed.room.name
                r_dict['success'] = True
                r_dict['message'] = 'A new client was added.'
            else:
                r_dict['success'] = False
                r_dict['message'] = 'Requested client is none.'
                response_status = 400
    else:
        r_dict['success'] = False
        r_dict['message'] = 'Requested mac is none.'
        response_status = 400

    log_dict['RESPONSE_STATUS'] = response_status
    log_dict['RESULT'] = r_dict

    fluent = FluentSender(settings.SERVICE_CONFIGURATIONS['LOG_SERVER_HOSTNAME'], settings.SERVICE_CONFIGURATIONS['LOG_SERVER_PORT'], 'sa')
    fluent.send(log_dict, 'sa.' + settings.SERVICE_CONFIGURATIONS['SERVER_TYPE'])

    return HttpResponse(json.dumps(r_dict, sort_keys=True, indent=4), content_type="application/json; charset=utf-8", status=response_status)


# When a local server requested for channel information.
# This function could be called only in a global server.
@csrf_exempt
def client_info_server(request):

    r_dict = dict()
    r_dict['success'] = False
    r_dict['message'] = 'Client info API cannot be called from a local server.'
    response_status = 400
    log_dict = dict()
    log_dict['REMOTE_ADDR'] = request.META['REMOTE_ADDR']
    log_dict['SERVER_NAME'] = settings.SERVICE_CONFIGURATIONS['LOCAL_SERVER_NAME']
    log_dict['CLIENT_TYPE'] = 'server'
    log_dict['REQUEST_PATH'] = request.path
    log_dict['METHOD'] = request.method
    log_dict['PARAM'] = request.GET
    log_dict['RESPONSE_STATUS'] = response_status
    log_dict['RESULT'] = r_dict
    fluent = FluentSender(settings.SERVICE_CONFIGURATIONS['LOG_SERVER_HOSTNAME'],
                          settings.SERVICE_CONFIGURATIONS['LOG_SERVER_PORT'], 'sa')
    fluent.send(log_dict, 'sa.' + settings.SERVICE_CONFIGURATIONS['SERVER_TYPE'])

    return HttpResponse(json.dumps(r_dict, sort_keys=True, indent=4), content_type="application/json; charset=utf-8", status=response_status)


# When a client requested for channel information.
# This function could be called either in a global server or in a local server.
@csrf_exempt
def client_info_client(request):

    return client_info_body(request)


@csrf_exempt
def recording_info_body(request):

    r_dict = dict()
    log_dict = dict()
    log_dict['REMOTE_ADDR'] = request.META['REMOTE_ADDR']
    log_dict['SERVER_NAME'] = 'global' if settings.SERVICE_CONFIGURATIONS['SERVER_TYPE'] == 'global' else settings.SERVICE_CONFIGURATIONS['LOCAL_SERVER_NAME']
    log_dict['CLIENT_TYPE'] = 'client'
    log_dict['REQUEST_PATH'] = request.path
    log_dict['METHOD'] = request.method
    log_dict['PARAM'] = request.POST
    response_status = 200

    mac = request.POST.get('mac')
    begin = request.POST.get("begin")
    end = request.POST.get("end")
    if mac is None or begin is None or end is None:
        r_dict['success'] = False
        r_dict['message'] = 'A requested parameter is none.'
        response_status = 400
    else:
        try:
            target_client = Client.objects.get(mac=mac)
            r_dict['bed'] = target_client.bed.name
            r_dict['success'] = True
            r_dict['message'] = 'Recording info was added correctly.'
            if settings.SERVICE_CONFIGURATIONS['SERVER_TYPE'] == 'local':
                form = UploadFileForm(request.POST, request.FILES)
                if form.is_valid():
                    try:
                        begin = datetime.datetime.strptime(begin, "%Y-%m-%dT%H:%M:%S%z")
                        end = datetime.datetime.strptime(end, "%Y-%m-%dT%H:%M:%S%z")
                        date_str = begin.strftime("%y%m%d")
                        time_str = begin.strftime("%H%M%S")
                        pathname = os.path.join(settings.SERVICE_CONFIGURATIONS['LOCAL_SERVER_DATAPATH'], target_client.bed.name, date_str)
                        filename = '%s_%s_%s.vital' % (target_client.bed.name, date_str, time_str)
                        recorded, created = FileRecorded.objects.get_or_create(file_basename=filename, defaults={
                            'client': target_client, 'bed': target_client.bed, 'begin_date': begin,
                            'end_date': end, 'file_path': os.path.join(pathname, filename)
                        })
                        if not created:
                            recorded.client = target_client
                            recorded.bed = target_client.bed
                            recorded.begin_date = begin
                            recorded.end_date = end
                            recorded.file_path = os.path.join(pathname, filename)
                            recorded.save()
                        if not os.path.exists(pathname):
                            os.makedirs(pathname)
                        with open(os.path.join(pathname, filename), 'wb+') as destination:
                            for chunk in request.FILES['attachment'].chunks():
                                destination.write(chunk)
                        if settings.SERVICE_CONFIGURATIONS['STORAGE_SERVER']:
                            file_upload_storage(date_str, recorded.client.bed.name, os.path.join(pathname, filename))
                        recorded.migrate_vital()
                    except Exception as e:
                        r_dict['success'] = False
                        r_dict['exception'] = str(e)
                        r_dict['message'] = 'An exception was raised.'
                        response_status = 500
                else:
                    r_dict['success'] = False
                    r_dict['message'] = 'File attachment is not valid.'
                    response_status = 400
        except Client.DoesNotExist:
            r_dict['success'] = False
            r_dict['message'] = 'Requested client is none.'
            response_status = 400

    log_dict['RESPONSE_STATUS'] = response_status
    log_dict['RESULT'] = r_dict

    fluent = FluentSender(settings.SERVICE_CONFIGURATIONS['LOG_SERVER_HOSTNAME'], settings.SERVICE_CONFIGURATIONS['LOG_SERVER_PORT'], 'sa')
    fluent.send(log_dict, 'sa.' + settings.SERVICE_CONFIGURATIONS['SERVER_TYPE'])

    return HttpResponse(json.dumps(r_dict, sort_keys=True, indent=4), content_type="application/json; charset=utf-8", status=response_status)


# When a local server requested for channel information.
# This function could be called only in a global server.
@csrf_exempt
def recording_info_server(request):

    r_dict = dict()
    r_dict['success'] = False
    r_dict['message'] = 'Recording info API cannot be called from a local server.'
    response_status = 400
    log_dict = dict()
    log_dict['REMOTE_ADDR'] = request.META['REMOTE_ADDR']
    log_dict['SERVER_NAME'] = settings.SERVICE_CONFIGURATIONS['LOCAL_SERVER_NAME']
    log_dict['CLIENT_TYPE'] = 'server'
    log_dict['REQUEST_PATH'] = request.path
    log_dict['METHOD'] = request.method
    log_dict['PARAM'] = request.GET
    log_dict['RESPONSE_STATUS'] = response_status
    log_dict['RESULT'] = r_dict
    fluent = FluentSender(settings.SERVICE_CONFIGURATIONS['LOG_SERVER_HOSTNAME'],
                          settings.SERVICE_CONFIGURATIONS['LOG_SERVER_PORT'], 'sa')
    fluent.send(log_dict, 'sa.' + settings.SERVICE_CONFIGURATIONS['SERVER_TYPE'])

    return HttpResponse(json.dumps(r_dict, sort_keys=True, indent=4), content_type="application/json; charset=utf-8", status=response_status)


# When a client requested for channel information.
# This function could be called either in a global server or in a local server.
@csrf_exempt
def recording_info_client(request):

    return recording_info_body(request)


@csrf_exempt
def report_status_client(request):
    r_dict = dict()
    log_dict = dict()
    log_dict['REMOTE_ADDR'] = request.META['REMOTE_ADDR']
    log_dict['SERVER_NAME'] = 'global' if settings.SERVICE_CONFIGURATIONS['SERVER_TYPE'] == 'global' else settings.SERVICE_CONFIGURATIONS['LOCAL_SERVER_NAME']
    log_dict['CLIENT_TYPE'] = 'client'
    log_dict['REQUEST_PATH'] = request.path
    log_dict['METHOD'] = request.method
    log_dict['PARAM'] = request.GET

    mac = request.GET.get('mac')
    report_dt = request.GET.get('report_dt')
    record_begin_dt = request.GET.get('record_begin_dt')
    ip_address = request.GET.get('ip_address')
    client_version = request.GET.get('client_version')
    uptime = int(request.GET.get('uptime'))
    bus_raw = request.GET.get('bus_info')
    response_status = 200

    if request.GET.get('status') == 'Unknown':
        status = Client.STATUS_UNKNOWN
    elif request.GET.get('status') == 'Standby':
        status = Client.STATUS_STANDBY
    elif request.GET.get('status') == 'Recording':
        status = Client.STATUS_RECORDING
    else:
        status = None

    if mac is None or report_dt is None or status is None or bus_raw is None or uptime is None or ip_address is None or client_version is None:
        r_dict['success'] = False
        r_dict['message'] = 'A requested parameter is none.'
        response_status = 400
    else:
        try:
            target_client = Client.objects.get(mac=mac)
            target_client.dt_report = report_dt
            target_client.dt_start_recording = record_begin_dt
            target_client.ip_address = ip_address
            target_client.client_version = client_version
            target_client.uptime = datetime.timedelta(seconds=uptime)
            target_client.status = status
            target_client.save()
            bus = json.loads(bus_raw)
            remaining_slot = ClientBusSlot.objects.filter(client=target_client, active=True)
            for bus_name, bus_info in bus.items():
                for slot_info in bus_info:
                    slot_name = slot_info['slot']
                    remaining_slot = remaining_slot.exclude(bus=bus_name, name=slot_name)
                    target_clientbusslot, _ = ClientBusSlot.objects.get_or_create(client=target_client, bus=bus_name, name=slot_name)
                    if slot_info['device_type'] != '':
                        target_device, _ = Device.objects.get_or_create(device_type=slot_info['device_type'], defaults={'displayed_name': slot_info['device_type']})
                        target_clientbusslot.device = target_device
                    else:
                        target_clientbusslot.device = None
                    target_clientbusslot.active = True
                    target_clientbusslot.save()
            remaining_slot.update(active=False)

            r_dict['success'] = True
            r_dict['message'] = 'Client status was updated correctly.'
        except Client.DoesNotExist:
            r_dict['success'] = False
            r_dict['message'] = 'Requested client is none.'
            response_status = 400

    log_dict['RESPONSE_STATUS'] = response_status
    log_dict['RESULT'] = r_dict

    fluent = FluentSender(settings.SERVICE_CONFIGURATIONS['LOG_SERVER_HOSTNAME'], settings.SERVICE_CONFIGURATIONS['LOG_SERVER_PORT'], 'sa')
    fluent.send(log_dict, 'sa.' + settings.SERVICE_CONFIGURATIONS['SERVER_TYPE'])

    return HttpResponse(json.dumps(r_dict, sort_keys=True, indent=4), content_type="application/json; charset=utf-8", status=response_status)


# When a server requested for a upload_review API function.
@csrf_exempt
def upload_review(request):
    r_dict = dict()
    log_dict = dict()
    log_dict['REMOTE_ADDR'] = request.META['REMOTE_ADDR']
    log_dict['SERVER_NAME'] = 'global' if settings.SERVICE_CONFIGURATIONS['SERVER_TYPE'] == 'global' else settings.SERVICE_CONFIGURATIONS['LOCAL_SERVER_NAME']
    log_dict['CLIENT_TYPE'] = 'client'
    log_dict['REQUEST_PATH'] = request.path
    log_dict['METHOD'] = request.method
    log_dict['PARAM'] = request.POST
    response_status = 200

    dt_report = request.POST.get('dt_report')
    name = request.POST.get('name')
    bed = request.POST.get('bed')
    local_server_name = request.POST.get('local_server_name')

    if dt_report is None or name is None or bed is None:
        r_dict['success'] = False
        r_dict['message'] = 'A requested parameter is missing.'
        response_status = 400
    elif settings.SERVICE_CONFIGURATIONS['SERVER_TYPE'] == 'global' and local_server_name is None:
        r_dict['success'] = False
        r_dict['message'] = 'A local server name is missing for global api.'
        response_status = 400
    else:
        comment = request.POST.get('comment')
        if comment is None:
            comment = ''
        if local_server_name is None:
            local_server_name = settings.SERVICE_CONFIGURATIONS['LOCAL_SERVER_NAME']
        form = UploadReviewForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                target_bed = Bed.objects.get(name=bed)
                try:
                    obj_review = Review.objects.get(name=name)
                    obj_review.chart = request.FILES['chart']
                    obj_review.save()
                    r_dict['success'] = True
                    r_dict['message'] = 'An existing review was successfully updated.'
                except Review.DoesNotExist:
                    Review.objects.create(dt_report=dt_report, name=name, local_server_name=local_server_name,
                                          bed=target_bed, chart=request.FILES['chart'], comment=comment)
                    r_dict['success'] = True
                    r_dict['message'] = 'A review was successfully uploaded.'
            except Bed.DoesNotExist:
                r_dict['success'] = False
                r_dict['message'] = 'The requested bed does not exist.'
                response_status = 400
            except Bed.MultipleObjectsReturned:
                r_dict['success'] = False
                r_dict['message'] = 'Multiple objects are returned.'
                response_status = 400
        else:
            r_dict['success'] = False
            r_dict['message'] = 'An attached file form is not valid.'
            response_status = 400

    log_dict['RESPONSE_STATUS'] = response_status
    log_dict['RESULT'] = r_dict

    fluent = FluentSender(settings.SERVICE_CONFIGURATIONS['LOG_SERVER_HOSTNAME'], settings.SERVICE_CONFIGURATIONS['LOG_SERVER_PORT'], 'sa')
    fluent.send(log_dict, 'sa.' + settings.SERVICE_CONFIGURATIONS['SERVER_TYPE'])

    return HttpResponse(json.dumps(r_dict, sort_keys=True, indent=4), content_type="application/json; charset=utf-8",
                        status=response_status)