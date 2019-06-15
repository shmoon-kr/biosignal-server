import re
import csv
import json
import pytz
import os.path
import datetime
import requests
import MySQLdb
import tempfile
import numpy as np
import sa_api.AMCVitalReader as vr
from .forms import UploadFileForm, UploadReviewForm
from pyfluent.client import FluentSender
from ftplib import FTP
from itertools import product
from django.conf import settings
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseNotFound, Http404
from django.template import loader
from django.shortcuts import get_object_or_404, render
from sa_api.models import Device, Client, Bed, Channel, Room, FileRecorded, ClientBusSlot, Review, DeviceConfigPresetBed, DeviceConfigItem, AnesthesiaRecordEvent, ManualInputEventItem, NumberInfoFile, WaveInfoFile
from django.views.decorators.csrf import csrf_exempt

tz = pytz.timezone(settings.TIME_ZONE)


def get_device_abb():
    r = dict()
    r['GE/Carescape'] = 'GEC'
    r['Philips/IntelliVue'] = 'PIV'
    r['Dräger/Primus'] = 'PRM'
    r['Masimo/Root'] = 'MSM'
    r['Covidien/BIS'] = 'BIS'
    return r


def get_sidebar_menu(selected=None):

    r = dict()
    r['Dashboard'] = dict()
    r['Dashboard']['active'] = True if selected in ('dashboard_rosette', 'dashboard_etc', 'dashboard_trend') else False
    r['Dashboard']['submenu'] = list()
    r['Dashboard']['submenu'].append([selected == 'dashboard_rosette', 'Rosette', '/dashboard?target=rosette'])
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


def get_table_name_info(main_only=True):
    r = dict()
    r['GE/Carescape'] = 'number_ge'
    r['Philips/IntelliVue'] = 'number_ph'
    if not main_only:
        r['Masimo/Root'] = 'number_mr'
    return r


def get_agg_list():
    return ['MIN', 'MAX', 'AVG', 'COUNT']


def get_table_col_val_list():

    table_col_list = dict()
    table_col_list['summary_by_file'] = ['ECG_HR', 'TEMP', 'NIBP_SYS', 'NIBP_DIA', 'NIBP_MEAN', 'PLETH_SPO2']
    table_col_list['Philips/IntelliVue'] = ['ECG_HR', 'TEMP', 'NIBP_SYS', 'NIBP_DIA', 'NIBP_MEAN', 'PLETH_SAT_O2']
    table_col_list['GE/Carescape'] = ['ECG_HR', 'TEMP', 'NIBP_SYS', 'NIBP_DIA', 'NIBP_MEAN', 'PLETH_SPO2']

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
            tmp_row.append('<a href="/preview?rosette=%s&bed=%s&begin_date=%s&end_date=%s">Preview</a>' % (
                row[col_dict["rosette"]], row[col_dict["bed"]], row[col_dict["begin_date"]], row[col_dict["end_date"]]
            ))
            if settings.SERVICE_CONFIGURATIONS['LOCAL_SERVER_NAME'] == 'AMC_Anesthesiology':
                begin_date = row[col_dict["begin_date"]]
                file_path = os.path.join('/mnt/Data/CloudStation', row[col_dict["bed"]], begin_date.strftime('%y%m%d'))
                file_name = '%s_%s.vital' % (row[col_dict["bed"]], begin_date.strftime('%y%m%d_%H%M%S'))
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


def db_upload_summary(record):

    table_name_info = get_table_name_info()
    table_col_list, table_val_list = get_table_col_val_list()

    db = MySQLdb.connect(host=settings.SERVICE_CONFIGURATIONS['DB_SERVER_HOSTNAME'],
                         user=settings.SERVICE_CONFIGURATIONS['DB_SERVER_USER'],
                         password=settings.SERVICE_CONFIGURATIONS['DB_SERVER_PASSWORD'],
                         db=settings.SERVICE_CONFIGURATIONS['DB_SERVER_DATABASE'])
    cursor = db.cursor()

    for device_displayed_name, table in table_name_info.items():
        field_list = list()
        for val in table_val_list[device_displayed_name]:
            field_list.append('%s(%s) %s_%s' % (val[1], val[0], val[0], val[1]))

        query = 'SELECT COUNT(*) TOTAL_COUNT, %s' % ', '.join(field_list)
        query += " FROM %s WHERE rosette = '%s' AND bed = '%s' AND" % (table, record.bed.room.name, record.bed.name)
        query += " dt BETWEEN '%s' and '%s'" % (record.begin_date.astimezone(tz), record.end_date.astimezone(tz))

        cursor.execute(query)

        summary = cursor.fetchall()[0]
        if summary[0]:
            field_list = list()
            field_list.append('method')
            field_list.append('device_displayed_name')
            field_list.append('file_basename')
            field_list.append('rosette')
            field_list.append('bed')
            field_list.append('begin_date')
            field_list.append('end_date')
            field_list.append('effective')
            field_list.append('TOTAL_COUNT')
            for val in table_val_list['summary_by_file']:
                field_list.append('%s_%s' % (val[0], val[1]))
            value_list = list()
            value_list.append(str(0))
            value_list.append("'%s'" % device_displayed_name)
            value_list.append("'%s'" % os.path.basename(record.file_path))
            value_list.append("'%s'" % record.bed.room.name)
            value_list.append("'%s'" % record.bed.name)
            value_list.append("'%s'" % record.begin_date.astimezone(tz).isoformat())
            value_list.append("'%s'" % record.end_date.astimezone(tz).isoformat())
            value_list.append('1' if record.end_date - record.begin_date > datetime.timedelta(minutes=10) else '0')
            for i in summary:
                if i is None:
                    value_list.append('NULL')
                else:
                    value_list.append(str(i))
            query = 'INSERT IGNORE INTO %s (%s)' % ('summary_by_file', ', '.join(field_list))
            query += ' VALUES (%s)' % ', '.join(value_list)

            try:
                cursor.execute(query)
                db.commit()
            except MySQLdb.Error as e:
                log_dict = dict()
                log_dict['SERVER_NAME'] = 'global' \
                    if settings.SERVICE_CONFIGURATIONS['SERVER_TYPE'] == 'global' \
                    else settings.SERVICE_CONFIGURATIONS['LOCAL_SERVER_NAME']
                log_dict['ACTION'] = 'DB_UPLOAD_FILE_READ'
                log_dict['FILE_NAME'] = record.file_path
                log_dict['MESSAGE'] = 'An exception was raised during mysql query execution.'
                log_dict['EXCEPTION'] = str(e)
                fluent = FluentSender(settings.SERVICE_CONFIGURATIONS['LOG_SERVER_HOSTNAME'],
                                      settings.SERVICE_CONFIGURATIONS['LOG_SERVER_PORT'], 'sa')
                fluent.send(log_dict, 'sa.' + settings.SERVICE_CONFIGURATIONS['SERVER_TYPE'])
                return

    db.close()
    return


# Create your views here.

def db_upload_main_numeric(recorded, method=0, db_writing=True):

    timestamp_interval = 0.5
    table_name_info = get_table_name_info(main_only=False)

    read_start = datetime.datetime.now()
    vr_file = vr.vital_reader(recorded.file_path)
    vr_file.read_header()
    vr_file.read_packets(skip_wave=True)
    raw_data = vr_file.export_db_data([*table_name_info])
    del vr_file

    if not len(raw_data):
        raise ValueError('No number data was found in vital file.')

    def sort_by_time(val):
        return val[:3]

    raw_data.sort(key=sort_by_time)

    aligned_data = list()
    tmp_aligned = dict()
    column_info = dict()
    for i, ri in enumerate(raw_data):
        if not ri[0] in column_info:
            column_info[ri[0]] = dict()
        if not ri[2] in column_info[ri[0]]:
            column_info[ri[0]][ri[2]] = len(column_info[ri[0]])
        if not i:
            tmp_aligned = {'device': ri[0], 'timestamp': ri[1], ri[2]: ri[3]}
        elif tmp_aligned['device'] != ri[0] or ri[1]-tmp_aligned['timestamp'] > timestamp_interval or ri[2] in tmp_aligned:
            aligned_data.append(tmp_aligned)
            tmp_aligned = {'device': ri[0], 'timestamp': ri[1], ri[2]: ri[3]}
        else:
            tmp_aligned[ri[2]] = ri[3]
    aligned_data.append(tmp_aligned)

    file_read_execution_time = datetime.datetime.now() - read_start

    log_dict = dict()
    log_dict['SERVER_NAME'] = 'global' \
        if settings.SERVICE_CONFIGURATIONS['SERVER_TYPE'] == 'global' \
        else settings.SERVICE_CONFIGURATIONS['LOCAL_SERVER_NAME']
    log_dict['ACTION'] = 'DB_UPLOAD_FILE_READ'
    log_dict['FILE_NAME'] = recorded.file_basename
    log_dict['NUM_RECORDS_FILE'] = len(raw_data)
    log_dict['NUM_RECORDS_ALIGNED'] = len(aligned_data)
    log_dict['READING_EXECUTION_TIME'] = str(file_read_execution_time)
    fluent = FluentSender(settings.SERVICE_CONFIGURATIONS['LOG_SERVER_HOSTNAME'],
                          settings.SERVICE_CONFIGURATIONS['LOG_SERVER_PORT'], 'sa')
    fluent.send(log_dict, 'sa.' + settings.SERVICE_CONFIGURATIONS['SERVER_TYPE'])
    del log_dict

    insert_query = dict()
    db = MySQLdb.connect(host=settings.SERVICE_CONFIGURATIONS['DB_SERVER_HOSTNAME'],
                         user=settings.SERVICE_CONFIGURATIONS['DB_SERVER_USER'],
                         password=settings.SERVICE_CONFIGURATIONS['DB_SERVER_PASSWORD'],
                         db=settings.SERVICE_CONFIGURATIONS['DB_SERVER_DATABASE'])
    cursor = db.cursor()

    column_info_db = dict()
    num_records = dict()

    for device_type in [*column_info]:
        num_records[device_type] = 0
        query = 'DESCRIBE %s' % (table_name_info[device_type])
        cursor.execute(query)
        rows = cursor.fetchall()

        insert_query[device_type] = 'INSERT IGNORE INTO %s (' % (table_name_info[device_type])
        column_info_db[device_type] = dict()
        for i, column in enumerate(rows):
            if column[0] != 'id':
                column_info_db[device_type][len(column_info_db[device_type])] = column[0]
                if len(column_info_db[device_type]) == 1:
                    insert_query[device_type] += column[0]
                else:
                    insert_query[device_type] += ', ' + column[0]
        insert_query[device_type] += ') VALUES '

    for i, ad in enumerate(aligned_data):
        tmp_query = "(%d, '%s', '%s'" % (method, recorded.bed.room.name, recorded.bed.name)
        tmp_query += ", '%s'" % (datetime.datetime.fromtimestamp(ad['timestamp']).isoformat())
        device_type = ad['device']
        num_records[device_type] += 1
        for key, val in column_info_db[device_type].items():
            if val not in ['method', 'rosette', 'bed', 'dt']:
                tmp_query += ', NULL' if val not in ad else ', %f' % (ad[val])
        tmp_query += ')'
        if i == 0:
            insert_query[device_type] += tmp_query
        else:
            insert_query[device_type] += ',' + tmp_query

    for device_type in [*column_info_db]:
        for key, val in column_info_db[device_type].items():
            column_info[device_type].pop(val, None)

    for key, val in insert_query.items():
        log_dict = dict()
        log_dict['SERVER_NAME'] = 'global'\
            if settings.SERVICE_CONFIGURATIONS['SERVER_TYPE'] == 'global'\
            else settings.SERVICE_CONFIGURATIONS['LOCAL_SERVER_NAME']
        log_dict['ACTION'] = 'DB_UPLOAD_%s' % ('REAL' if db_writing else 'FAKE')
        log_dict['TARGET_DEVICE'] = key
        log_dict['NEW_CHANNEL'] = [*column_info[key]]
        log_dict['NUM_RECORDS_QUERY'] = num_records[key]
        insert_start = datetime.datetime.now()
        try:
            if db_writing:
                cursor.execute(val)
        except MySQLdb.Error as e:
            log_dict['MESSAGE'] = 'An exception was raised during mysql query execution.'
            log_dict['EXCEPTION'] = str(e)
            fluent = FluentSender(settings.SERVICE_CONFIGURATIONS['LOG_SERVER_HOSTNAME'],
                                  settings.SERVICE_CONFIGURATIONS['LOG_SERVER_PORT'], 'sa')
            fluent.send(log_dict, 'sa.' + settings.SERVICE_CONFIGURATIONS['SERVER_TYPE'])

            return
        db.commit()
        db_upload_execution_time = datetime.datetime.now() - insert_start
        log_dict['NUM_RECORDS_AFFECTED'] = cursor.rowcount if db_writing else 0
        log_dict['DB_EXECUTION_TIME'] = str(db_upload_execution_time) if db_writing else 0

        fluent = FluentSender(settings.SERVICE_CONFIGURATIONS['LOG_SERVER_HOSTNAME'],
                              settings.SERVICE_CONFIGURATIONS['LOG_SERVER_PORT'], 'sa')
        fluent.send(log_dict, 'sa.' + settings.SERVICE_CONFIGURATIONS['SERVER_TYPE'])
        del log_dict

    db.close()

    return


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

    bed = request.GET.get("bed")
    rosette = request.GET.get("rosette")
    device = request.GET.get("device")
    begin_date = request.GET.get("begin_date")
    end_date = request.GET.get("end_date")

    table_name_info = get_table_name_info()

    if rosette is None or bed is None or begin_date is None or end_date is None:
        r_dict = dict()
        r_dict['REQUEST_PATH'] = request.path
        r_dict['METHOD'] = request.method
        r_dict['PARAM'] = request.GET
        r_dict['MESSAGE'] = 'Invalid parameters.'
        return HttpResponse(json.dumps(r_dict, sort_keys=True, indent=4), content_type="application/json; charset=utf-8", status=400)
    else:
        db = MySQLdb.connect(host=settings.SERVICE_CONFIGURATIONS['DB_SERVER_HOSTNAME'],
                             user=settings.SERVICE_CONFIGURATIONS['DB_SERVER_USER'],
                             password=settings.SERVICE_CONFIGURATIONS['DB_SERVER_PASSWORD'],
                             db=settings.SERVICE_CONFIGURATIONS['DB_SERVER_DATABASE'])
        cursor = db.cursor()

        query = "SELECT * FROM %s WHERE rosette='%s' AND bed='%s' AND dt BETWEEN '%s' AND '%s' ORDER BY dt" %\
                (table_name_info[device], rosette, bed, begin_date, end_date)
        cursor.execute(query)
        title = list()
        for col in cursor.description:
            title.append(col[0])
        query_results = cursor.fetchall()
        db.close()

        csvfile = tempfile.TemporaryFile(mode='w+')
        cyclewriter = csv.writer(csvfile, delimiter=',', quotechar='|', quoting=csv.QUOTE_MINIMAL)
        cyclewriter.writerow(title)
        for r in query_results:
            cyclewriter.writerow(r)
        csvfile.seek(0)

        start_dt = datetime.datetime.strptime(begin_date, '%Y-%m-%d %H:%M:%S')

        filename = '%s_%s_%s.csv' % (bed, start_dt.strftime('%y%m%d_%H%M%S'), device.replace('/', '_'))

        response = HttpResponse(csvfile, content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename=%s' % filename

        return response


@csrf_exempt
def preview(request):

    bed = request.GET.get("bed")
    rosette = request.GET.get("rosette")
    begin_date = request.GET.get("begin_date")
    end_date = request.GET.get("end_date")

    table_name_info = get_table_name_info()
    table_col_list, table_val_list = get_table_col_val_list()

    color_preview = ['green', 'blue', 'red', 'orange', 'gold', 'aqua']

    chart_data = dict()

    if rosette is not None and bed is not None and begin_date is not None and end_date is not None:

        db = MySQLdb.connect(host=settings.SERVICE_CONFIGURATIONS['DB_SERVER_HOSTNAME'],
                             user=settings.SERVICE_CONFIGURATIONS['DB_SERVER_USER'],
                             password=settings.SERVICE_CONFIGURATIONS['DB_SERVER_PASSWORD'],
                             db=settings.SERVICE_CONFIGURATIONS['DB_SERVER_DATABASE'])
        cursor = db.cursor()

        for device, table in table_name_info.items():
            query = "SELECT dt, %s FROM %s WHERE rosette='%s' AND bed='%s' AND dt BETWEEN '%s' AND '%s' ORDER BY dt" %\
                    (', '.join(table_col_list[device]), table, rosette, bed, begin_date, end_date)
            cursor.execute(query)
            query_results = cursor.fetchall()
            if len(query_results):
                chart_data[device] = dict()
                chart_data[device]['csv_download_params'] = 'rosette=%s&bed=%s&begin_date=%s&end_date=%s&device=%s' % (
                    rosette, bed, begin_date, end_date, device
                )
                chart_data[device]['timestamp'] = list()
                for col in table_col_list[device]:
                    chart_data[device][col] = list()
                for row in query_results:
                    chart_data[device]['timestamp'].append(str(row[0]))
                    for i, val in enumerate(row[1:]):
                        chart_data[device][table_col_list[device][i]].append(float('nan') if val is None else val)
                chart_data[device]['timestamp'] = json.dumps(chart_data[device]['timestamp'])
                dataset = list()
                for i, col in enumerate(table_col_list[device]): # rgb(75, 192, 192)
                    tmp_dataset = dict()
                    tmp_dataset["label"] = col
                    tmp_dataset["data"] = chart_data[device][col]
                    tmp_dataset["fill"] = False
                    tmp_dataset["pointRadius"] = 0
                    tmp_dataset["borderColor"] = color_preview[i]
                    tmp_dataset["lineTension"] = 0
                    dataset.append(tmp_dataset)
                chart_data[device]['dataset'] = json.dumps(dataset)
        db.close()

        events = ManualInputEventItem.objects.filter(record__bed__name=bed, dt__range=(begin_date, end_date))

        context = dict()
        context['data'] = chart_data
        context['bed'] = bed
        context['events'] = events
        context['date'] = datetime.datetime.strptime(begin_date, '%Y-%m-%d %H:%M:%S').strftime('%Y-%m-%d')
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

        bed_re = re.compile('[B-L]-[0-9]{2}')

        clients_all = Client.objects.all()

        for client in clients_all:
            if bed_re.match(client.bed.name):
                tmp_bed_name = client.bed.name.replace('-', '').lower()
                if client.color_info()[1] == 'red':
                    beds_red.append(tmp_bed_name)
                elif client.color_info()[1] == 'orange':
                    beds_orange.append(tmp_bed_name)
                elif client.status == Client.STATUS_RECORDING:
                    beds_blue.append(tmp_bed_name)
                else:
                    beds_green.append(tmp_bed_name)

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
    elif target == 'etc':
        template = loader.get_template('dashboard_etc.html')
        sidebar_menu, loc = get_sidebar_menu('dashboard_etc')
        raise Http404()
    elif target == 'trend':
        begin_date = request.GET.get('begin_date')
        end_date = request.GET.get('end_date')
        if begin_date is None:
            begin_date = datetime.date.today() - datetime.timedelta(days=7)
            end_date = datetime.datetime.now()
        elif end_date is None:
            end_date = begin_date + datetime.timedelta(days=7)
        db = MySQLdb.connect(host=settings.SERVICE_CONFIGURATIONS['DB_SERVER_HOSTNAME'],
                             user=settings.SERVICE_CONFIGURATIONS['DB_SERVER_USER'],
                             password=settings.SERVICE_CONFIGURATIONS['DB_SERVER_PASSWORD'],
                             db=settings.SERVICE_CONFIGURATIONS['DB_SERVER_DATABASE'])
        cursor = db.cursor()
        query = 'SELECT DATE(begin_date) dt, rosette, COUNT(*) files, SUM(TIMESTAMPDIFF(SECOND, begin_date, end_date)) DUR, SUM(TOTAL_COUNT) TOTAL_COUNT'
        query += " FROM summary_by_file WHERE begin_date BETWEEN '%s' AND '%s' GROUP BY dt, rosette" % (begin_date, end_date)
        cursor.execute(query)
        rows = cursor.fetchall()
        db.close()

        label_dates = set()
        for row in rows:
            label_dates.add(str(row[0]))
        label_dates = list(label_dates)
        label_dates.sort()
        label_dates_dict = dict()
        for i, label in enumerate(label_dates):
            label_dates_dict[label] = i

        data = dict()
        data['label_dates'] = label_dates
        data['collected_files'] = dict()
        data['collected_hours'] = dict()
        data['total_hours'] = dict()

        for row in rows:
            if row[1] not in data['total_hours']:
                data['collected_files'][row[1]] = [0] * len(label_dates)
                data['collected_hours'][row[1]] = [0] * len(label_dates)
                data['total_hours'][row[1]] = [0] * len(label_dates)
            data['collected_files'][row[1]][label_dates_dict[str(row[0])]] = row[2]
            data['collected_hours'][row[1]][label_dates_dict[str(row[0])]] = float(row[3])/3600

        template = loader.get_template('dashboard_chart.html')
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
    dt_from = request.GET.get('dt_from')
    dt_to = request.GET.get('dt_to')

    if dt_from is None:
        dt_from = datetime.date.today() - datetime.timedelta(days=7)
        dt_to = datetime.date.today()
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
        val['files'] = list()

    db = MySQLdb.connect(host=settings.SERVICE_CONFIGURATIONS['DB_SERVER_HOSTNAME'],
                         user=settings.SERVICE_CONFIGURATIONS['DB_SERVER_USER'],
                         password=settings.SERVICE_CONFIGURATIONS['DB_SERVER_PASSWORD'],
                         db=settings.SERVICE_CONFIGURATIONS['DB_SERVER_DATABASE'])

    cursor = db.cursor()
    query = "SELECT DATE(begin_date) dt, COUNT(*) num_files, SUM(TIMESTAMPDIFF(SECOND, begin_date, end_date)) TOTAL_DURATION, "
    query += "SUM(ECG_HR_AVG*ECG_HR_COUNT)/SUM(ECG_HR_COUNT), SUM(TEMP_AVG*TEMP_COUNT)/SUM(TEMP_COUNT), "
    query += "SUM(NIBP_SYS_AVG*NIBP_SYS_COUNT)/SUM(NIBP_SYS_COUNT), SUM(NIBP_DIA_AVG*NIBP_DIA_COUNT)/SUM(NIBP_DIA_COUNT), "
    query += "SUM(NIBP_MEAN_AVG*NIBP_MEAN_COUNT)/SUM(NIBP_MEAN_COUNT), SUM(PLETH_SPO2_AVG*PLETH_SPO2_COUNT)/SUM(PLETH_SPO2_COUNT) "
    query += "FROM summary_by_file WHERE rosette='%s' AND bed IN ('%s') " % (rosette, "','".join(bed_name))
    query += "AND begin_date BETWEEN '%s' AND '%s' GROUP BY DATE(begin_date) ORDER BY DATE(begin_date)" % (dt_from, dt_to)
    cursor.execute(query)
    trend_rosette = cursor.fetchall()

    for row in trend_rosette:
        data[rosette]['date'].append(str(row[0]))
        data[rosette]['num_files'].append(int(row[1]))
        data[rosette]['total_duration'].append(int(row[2]))

    query = "SELECT bed, DATE(begin_date) dt, COUNT(*) num_files, SUM(TIMESTAMPDIFF(SECOND, begin_date, end_date)) TOTAL_DURATION, "
    query += "SUM(ECG_HR_AVG*ECG_HR_COUNT)/SUM(ECG_HR_COUNT), SUM(TEMP_AVG*TEMP_COUNT)/SUM(TEMP_COUNT), "
    query += "SUM(NIBP_SYS_AVG*NIBP_SYS_COUNT)/SUM(NIBP_SYS_COUNT), SUM(NIBP_DIA_AVG*NIBP_DIA_COUNT)/SUM(NIBP_DIA_COUNT), "
    query += "SUM(NIBP_MEAN_AVG*NIBP_MEAN_COUNT)/SUM(NIBP_MEAN_COUNT), SUM(PLETH_SPO2_AVG*PLETH_SPO2_COUNT)/SUM(PLETH_SPO2_COUNT) "
    query += "FROM summary_by_file WHERE rosette='%s' AND bed IN ('%s') " % (rosette, "','".join(bed_name))
    query += "AND begin_date BETWEEN '%s' AND '%s' GROUP BY bed, DATE(begin_date)" % (dt_from, dt_to)
    cursor.execute(query)
    trend_bed = cursor.fetchall()

    for row in trend_bed:
        data[row[0]]['date'].append(str(row[1]))
        data[row[0]]['num_files'].append(int(row[2]))
        data[row[0]]['total_duration'].append(int(row[3]))

    query = "SELECT bed, file_basename, TIMESTAMPDIFF(SECOND, begin_date, end_date), ECG_HR_AVG, TEMP_AVG, NIBP_SYS_AVG, NIBP_DIA_AVG, NIBP_MEAN_AVG, PLETH_SPO2_AVG "
    query += "FROM summary_by_file WHERE rosette='%s' AND bed IN ('%s') " % (rosette, "','".join(bed_name))
    query += "AND begin_date BETWEEN '%s' AND '%s' ORDER BY begin_date DESC" % (dt_from, dt_to)
    cursor.execute(query)
    summary_files = cursor.fetchall()

    for row in summary_files:
        tmp = list(row)
        tmp[2] = str(datetime.timedelta(seconds=tmp[2]))
        for i in range(3, len(tmp)):
            if tmp[i] is not None:
                tmp[i] = format(tmp[i], '.2f')
        data[rosette]['files'].append(tmp)
        data[row[0]]['files'].append(tmp)

    db.close()

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


def decompose_vital_file(file_name, decomposed_path):

    timestamp_interval = 0.5
    device_abb = get_device_abb()

    read_start = datetime.datetime.now()
    vr_file = vr.vital_reader(file_name)
    vr_file.read_header()
    vr_file.read_packets()
    raw_data_number = vr_file.export_db_data()
    raw_data_wave = vr_file.export_db_data_wave()
    del vr_file

    if not len(raw_data_number):
        raise ValueError('No number data was found in vital file.')

    def sort_by_time(val):
        return val[:3]

    raw_data_number.sort(key=sort_by_time)

    aligned_data = list()
    tmp_aligned = dict()
    column_info = dict()
    for i, ri in enumerate(raw_data_number):
        if not ri[0] in column_info:
            column_info[ri[0]] = {}
        if not ri[2] in column_info[ri[0]]:
            column_info[ri[0]][ri[2]] = len(column_info[ri[0]])
        if not i:
            tmp_aligned = {'device': ri[0], 'timestamp': ri[1], ri[2]: ri[3]}
        elif tmp_aligned['device'] != ri[0] or ri[1]-tmp_aligned['timestamp'] > timestamp_interval or ri[2] in tmp_aligned:
            aligned_data.append(tmp_aligned)
            tmp_aligned = {'device': ri[0], 'timestamp': ri[1], ri[2]: ri[3]}
        else:
            tmp_aligned[ri[2]] = ri[3]
    aligned_data.append(tmp_aligned)

    file_read_execution_time = datetime.datetime.now() - read_start
    timestamp_number = dict()
    val_number = dict()

    for device in [*column_info]:
        timestamp_number[device] = list()
        val_number[device] = list()

    for i, ad in enumerate(aligned_data):
        timestamp_number[ad['device']].append(ad['timestamp'])
        tmp_val_list = [None] * len(column_info[ad['device']])
        for key, val in ad.items():
            if key not in ('device', 'timestamp'):
                tmp_val_list[column_info[ad['device']][key]] = val
        val_number[ad['device']].append(tmp_val_list)

    r_number = list()

    dt_datetime = np.dtype(datetime.datetime)
    dt_str = np.dtype(str)

    for device, cols in column_info.items():
        if device in device_abb.keys():
            if not os.path.exists(decomposed_path):
                os.makedirs(decomposed_path)
            file_path = os.path.join(decomposed_path, os.path.splitext(os.path.basename(file_name))[0]+'_%s.npz' % device_abb[device])
            np.savez_compressed(file_path, col_list=np.array(cols, dtype=dt_str),
                                timestamp=np.array(timestamp_number[device], dtype=dt_datetime),
                                number=np.array(val_number[device], dtype=np.float32))
            r_message = "OK"
        else:
            r_message = "Device infomation does not exists."
        r_number.append([device, r_message, file_path, len(timestamp_number[device]), len(column_info[device])])

    r_wave = list()
    for wave, val in raw_data_wave.items():
        if wave[0] in device_abb.keys():
            if not os.path.exists(decomposed_path):
                os.makedirs(decomposed_path)
            file_path = os.path.join(decomposed_path, os.path.splitext(os.path.basename(file_name))[0]+'_%s_%s.npz' % (device_abb[wave[0]], wave[1]))
            np.savez_compressed(file_path, timestamp=np.array(val['timestamp'], dtype=dt_datetime),
                                psize=np.array(val['psize'], dtype=np.int32), data=np.array(val['data'], dtype=np.float32))
            r_message = "OK"
        else:
            r_message = "Device infomation does not exists."
        r_wave.append([wave[0], wave[1], r_message, file_path, len(val['timestamp']), val['srate'], max(val['psize'])])

    return r_number, r_wave


def decompose_record(recorded):

    table_name_info = get_table_name_info(main_only=False)
    filename_split = recorded.file_basename.split('_')
    decompose_path = os.path.join('raw_decomposed', filename_split[0], filename_split[1])
    r_number, r_wave = decompose_vital_file(recorded.file_path, decompose_path)

    for number_npz in r_number:
        if number_npz[0] in table_name_info:
            ninfo, _ = NumberInfoFile.objects.get_or_create(record=recorded, device_displayed_name=number_npz[0])
            ninfo.db_table_name = table_name_info[number_npz[0]]
            ninfo.file_path = number_npz[2]
            ninfo.save()
        else:
            log_dict = dict()
            log_dict['SERVER_NAME'] = 'global' if settings.SERVICE_CONFIGURATIONS['SERVER_TYPE'] == 'global' else \
                settings.SERVICE_CONFIGURATIONS['LOCAL_SERVER_NAME']
            log_dict['FILE_PATH'] = recorded.file_path
            log_dict['FILE_BASENAME'] = recorded.file_basename
            log_dict['EVENT'] = 'DB table name was not defined for device %s.' % number_npz[0]
            fluent = FluentSender(settings.SERVICE_CONFIGURATIONS['LOG_SERVER_HOSTNAME'], settings.SERVICE_CONFIGURATIONS['LOG_SERVER_PORT'], 'sa')
            fluent.send(log_dict, 'sa.' + settings.SERVICE_CONFIGURATIONS['SERVER_TYPE'])

    for wave_npz in r_wave:
        winfo, _ = WaveInfoFile.objects.get_or_create(record=recorded, device_displayed_name=wave_npz[0], channel_name=wave_npz[1])
        winfo.file_path = wave_npz[3]
        winfo.num_packets = wave_npz[4]
        winfo.sampling_rate = wave_npz[5]
        winfo.max_psize = wave_npz[6]
        winfo.save()

    return


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
                        recorded = FileRecorded.objects.create(client=target_client, bed=target_client.bed, begin_date=begin, end_date=end)
                        date_str = begin.strftime("%y%m%d")
                        time_str = begin.strftime("%H%M%S")
                        pathname = os.path.join(settings.SERVICE_CONFIGURATIONS['LOCAL_SERVER_DATAPATH'], recorded.bed.name, date_str)
                        if not os.path.exists(pathname):
                            os.makedirs(pathname)
                        filename = '%s_%s_%s.vital' % (recorded.client.bed.name, date_str, time_str)
                        with open(os.path.join(pathname, filename), 'wb+') as destination:
                            for chunk in request.FILES['attachment'].chunks():
                                destination.write(chunk)
                        recorded.file_path = os.path.join(pathname, filename)
                        recorded.file_basename = filename
                        recorded.save(update_fields=['file_path', 'file_basename'])
                        if settings.SERVICE_CONFIGURATIONS['STORAGE_SERVER']:
                            file_upload_storage(date_str, recorded.client.bed.name, os.path.join(pathname, filename))
                        if settings.SERVICE_CONFIGURATIONS['DB_SERVER']:
                            try:
                                db_upload_main_numeric(recorded)
                                db_upload_summary(recorded)
                                r_dict['success'] = True
                                r_dict['message'] = 'Recording info was added and file was uploaded correctly.'
                            except Exception as e:
                                r_dict['success'] = True
                                r_dict['exception'] = str(e)
                                r_dict['message'] = 'Recording info was added and file was uploaded correctly. But DB upload was failed.'
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