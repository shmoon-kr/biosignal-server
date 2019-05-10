import re
import json
import pytz
import os.path
import datetime
import requests
import MySQLdb
import sa_api.AMCVitalReader as vr
from .forms import UploadFileForm, UploadReviewForm
from pyfluent.client import FluentSender
from ftplib import FTP
from itertools import product
from django.conf import settings
from django.http import HttpResponse, HttpResponseBadRequest
from django.template import loader
from django.shortcuts import get_object_or_404, render
from sa_api.models import Device, Client, Bed, Channel, Room, FileRecorded, ClientBusSlot, Review
from django.views.decorators.csrf import csrf_exempt

tz = pytz.timezone(settings.TIME_ZONE)

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

    table_name_info = {'GE/Carescape': 'number_ge', 'Philips/IntelliVue': 'number_ph'}

    col_list = dict()
    col_list['summary'] = ['HR', 'TEMP', 'NIBP_SYS', 'NIBP_DIA']
    col_list['Philips/IntelliVue'] = col_list['summary']
    col_list['GE/Carescape'] = ['ECG_HR', 'TEMP', 'NIBP_SYS', 'NIBP_DIA']
    agg_list = ['MIN', 'MAX', 'AVG', 'COUNT']

    val_list = dict()
    val_list['summary'] = product(col_list['summary'], agg_list)
    val_list['Philips/IntelliVue'] = product(col_list['Philips/IntelliVue'], agg_list)
    val_list['GE/Carescape'] = product(col_list['GE/Carescape'], agg_list)

    db = MySQLdb.connect(host=settings.SERVICE_CONFIGURATIONS['DB_SERVER_HOSTNAME'],
                         user=settings.SERVICE_CONFIGURATIONS['DB_SERVER_USER'],
                         password=settings.SERVICE_CONFIGURATIONS['DB_SERVER_PASSWORD'],
                         db=settings.SERVICE_CONFIGURATIONS['DB_SERVER_DATABASE'])
    cursor = db.cursor()

    for device_displayed_name, table in table_name_info.items():
        field_list = list()
        for val in val_list[device_displayed_name]:
            field_list.append('%s(%s) %s_%s' % (val[1], val[0], val[0], val[1]))

        query = 'SELECT COUNT(*) TOTAL_COUNT, %s' % ', '.join(field_list)
        query += " FROM %s WHERE bed = '%s' AND" % (table, record.bed.name)
        query += " dt BETWEEN '%s' and '%s'" % (record.begin_date.astimezone(tz), record.end_date.astimezone(tz))

        cursor.execute(query)

        summary = cursor.fetchall()[0]
        if summary[0]:
            field_list = list()
            field_list.append('device_displayed_name')
            field_list.append('file_basename')
            field_list.append('rosette')
            field_list.append('bed')
            field_list.append('begin_date')
            field_list.append('end_date')
            field_list.append('effective')
            field_list.append('TOTAL_COUNT')
            for val in val_list['summary']:
                field_list.append('%s_%s' % (val[0], val[1]))
            value_list = list()
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

def db_upload_main_numeric(filepath, room, bed, db_writing=True):

    table_name_info = {'GE/Carescape': 'number_ge', 'Philips/IntelliVue': 'number_ph'}
    timestamp_interval = 0.5

    read_start = datetime.datetime.now()
    vr_file = vr.vital_reader(filepath)
    vr_file.read_header()
    vr_file.read_packets(skip_wave=True)
    raw_data = vr_file.export_db_data([*table_name_info])
    del vr_file

    if not len(raw_data):
        raise ValueError('No number data was found in vital file.')

    def sort_by_time(val):
        return val[:3]

    raw_data.sort(key=sort_by_time)

    aligned_data = []
    tmp_aligned = {}
    column_info = {}
    for i, ri in enumerate(raw_data):
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

    log_dict = dict()
    log_dict['SERVER_NAME'] = 'global' \
        if settings.SERVICE_CONFIGURATIONS['SERVER_TYPE'] == 'global' \
        else settings.SERVICE_CONFIGURATIONS['LOCAL_SERVER_NAME']
    log_dict['ACTION'] = 'DB_UPLOAD_FILE_READ'
    log_dict['FILE_NAME'] = filepath
    log_dict['NUM_RECORDS_FILE'] = len(raw_data)
    log_dict['NUM_RECORDS_ALIGNED'] = len(aligned_data)
    log_dict['READING_EXECUTION_TIME'] = str(file_read_execution_time)
    fluent = FluentSender(settings.SERVICE_CONFIGURATIONS['LOG_SERVER_HOSTNAME'],
                          settings.SERVICE_CONFIGURATIONS['LOG_SERVER_PORT'], 'sa')
    fluent.send(log_dict, 'sa.' + settings.SERVICE_CONFIGURATIONS['SERVER_TYPE'])
    del log_dict

    insert_query = {}
    db = MySQLdb.connect(host=settings.SERVICE_CONFIGURATIONS['DB_SERVER_HOSTNAME'],
                         user=settings.SERVICE_CONFIGURATIONS['DB_SERVER_USER'],
                         password=settings.SERVICE_CONFIGURATIONS['DB_SERVER_PASSWORD'],
                         db=settings.SERVICE_CONFIGURATIONS['DB_SERVER_DATABASE'])
    cursor = db.cursor()

    column_info_db = {}
    num_records = {}

    for device_type in [*column_info]:
        num_records[device_type] = 0
        query = 'DESCRIBE %s' % (table_name_info[device_type])
        cursor.execute(query)
        rows = cursor.fetchall()

        insert_query[device_type] = 'INSERT IGNORE INTO %s (' % (table_name_info[device_type])
        column_info_db[device_type] = {}
        for i, column in enumerate(rows):
            if column[0] != 'id':
                column_info_db[device_type][len(column_info_db[device_type])] = column[0]
                if len(column_info_db[device_type]) == 1:
                    insert_query[device_type] += column[0]
                else:
                    insert_query[device_type] += ', ' + column[0]
        insert_query[device_type] += ') VALUES '

    for i, ad in enumerate(aligned_data):
        tmp_query = '(\'%s\', \'%s\'' % (room, bed)
        tmp_query += ', \'%s\'' % (datetime.datetime.fromtimestamp(ad['timestamp']).isoformat())
        device_type = ad['device']
        num_records[device_type] += 1
        for key, val in column_info_db[device_type].items():
            if val not in ['rosette', 'bed', 'dt']:
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
def dashboard(request):

    beds_red = list()
    beds_green = list()
    beds_yellow = list()

    bed_re = re.compile('[B-K]-[0-9]{2}')

    clients_all = Client.objects.all()

    for client in clients_all:
        if bed_re.match(client.bed.name):
            tmp_bed_name = client.bed.name.replace('-', '').lower()
            if client.color_info() == 'red':
                beds_red.append("'%s'" % tmp_bed_name)
            elif client.status == Client.STATUS_RECORDING:
                beds_yellow.append("'%s'" % tmp_bed_name)
            else:
                beds_green.append("'%s'" % tmp_bed_name)

    template = loader.get_template('dashboard.html')
    context = {
        'beds_red': ','.join(beds_red),
        'beds_green': ','.join(beds_green),
        'beds_yellow': ','.join(beds_yellow),
    }

    return HttpResponse(template.render(context, request))


@csrf_exempt
def summary_bed(request):

    start_date = request.GET.get("start_date")
    end_date = request.GET.get("end_date")

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

    col_list_ph = ['HR', 'TEMP', 'NIBP_SYS', 'NIBP_DIA']
    col_list_ge = ['ECG_HR', 'TEMP', 'NIBP_SYS', 'NIBP_DIA']
    agg_list = ['MIN', 'MAX', 'AVG', 'COUNT']
    val_list_ph = product(col_list_ph, agg_list)
    val_list_ge = product(col_list_ge, agg_list)

    if start_date is None:
        start_date = tz.localize(datetime.datetime.now()) + datetime.timedelta(days=-1)
        start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
    else:
        start_date = tz.localize(datetime.datetime.strptime(start_date, '%Y-%m-%d'))

    if end_date is None:
        end_date = start_date + datetime.timedelta(days=1)
    else:
        end_date = tz.localize(datetime.datetime.strptime(end_date, '%Y-%m-%d'))

    record_all = FileRecorded.objects.filter(begin_date__range=(start_date, end_date))

    bed_stat = dict()

    for record in record_all:
        if record.bed.name not in bed_stat.keys():
            bed_stat[record.bed.name] = dict()
            bed_stat[record.bed.name]['rosette'] = record.bed.room.name
            bed_stat[record.bed.name]['files_total'] = 0
            bed_stat[record.bed.name]['files_effective'] = 0
            bed_stat[record.bed.name]['intervals'] = list()
            bed_stat[record.bed.name]['duration_effective'] = datetime.timedelta()
        bed_stat[record.bed.name]['files_total'] += 1
        if record.end_date - record.begin_date >= datetime.timedelta(seconds=600):
            bed_stat[record.bed.name]['files_effective'] += 1
            bed_stat[record.bed.name]['duration_effective'] += record.end_date - record.begin_date
            bed_stat[record.bed.name]['intervals'].append([record.begin_date.astimezone(tz), record.end_date.astimezone(tz)])

    field_list_ph = list()
    for val in val_list_ph:
        field_list_ph.append('%s(%s) %s_%s' % (val[1], val[0], val[0], val[1]))
    field_list_ge = list()
    for val in val_list_ge:
        field_list_ge.append('%s(%s) %s_%s' % (val[1], val[0], val[0], val[1]))

    db = MySQLdb.connect(host=settings.SERVICE_CONFIGURATIONS['DB_SERVER_HOSTNAME'],
                         user=settings.SERVICE_CONFIGURATIONS['DB_SERVER_USER'],
                         password=settings.SERVICE_CONFIGURATIONS['DB_SERVER_PASSWORD'],
                         db=settings.SERVICE_CONFIGURATIONS['DB_SERVER_DATABASE'])
    cursor = db.cursor()

    result_table = list()

    query = "SELECT bed, COUNT(*) TOTAL_COUNT, %s FROM number_ph WHERE dt BETWEEN '%s' AND '%s' GROUP BY bed" %\
            (', '.join(field_list_ph), start_date.isoformat(), end_date.isoformat())
    cursor.execute(query)

    for row in cursor.fetchall():
        if row[0] in bed_stat.keys():
            bed_stat[row[0]]['stat'] = row[1:]

    query = "SELECT bed, COUNT(*) TOTAL_COUNT, %s FROM number_ge WHERE dt BETWEEN '%s' AND '%s' GROUP BY bed" %\
            (', '.join(field_list_ge), start_date.isoformat(), end_date.isoformat())
    cursor.execute(query)

    for row in cursor.fetchall():
        if row[0] in bed_stat.keys():
            bed_stat[row[0]]['stat'] = row[1:]

    for bed, val in bed_stat.items():
        row = list()
        row.append(bed)
        row.append(val['rosette'])
        row.append(val['files_total'])
        row.append(val['files_effective'])
        row.append(val['duration_effective'])
        if 'stat' in val.keys():
            row.extend(val['stat'])
        else:
            row.append(0)
            row.extend([None] * len(field_list_ge))
        result_table.append(row)

    title = ['bed', 'rosette', 'files_total', 'files_effective', 'duration_effective', 'total count'] + field_list_ph

    template = loader.get_template('summary.html')
    context = {
        'title': title,
        'result_table': result_table
    }

    fluent = FluentSender(settings.SERVICE_CONFIGURATIONS['LOG_SERVER_HOSTNAME'], settings.SERVICE_CONFIGURATIONS['LOG_SERVER_PORT'], 'sa')
    fluent.send(log_dict, 'sa.' + settings.SERVICE_CONFIGURATIONS['SERVER_TYPE'])

    return HttpResponse(template.render(context, request))


# Main body of device_info API function
def device_info_body(request, api_type):

    tz = pytz.timezone(settings.TIME_ZONE)

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
                        recorded = FileRecorded.objects.create(client=target_client, bed=target_client.bed, begin_date=begin, end_date=end)
                        date_str = datetime.datetime.strptime(recorded.begin_date, "%Y-%m-%dT%H:%M:%S%z").strftime("%y%m%d")
                        time_str = datetime.datetime.strptime(recorded.begin_date, "%Y-%m-%dT%H:%M:%S%z").strftime("%H%M%S")
                        pathname = '%s/%s' % (settings.SERVICE_CONFIGURATIONS['LOCAL_SERVER_DATAPATH'], recorded.client.bed.name)
                        if not os.path.exists(pathname):
                            os.makedirs(pathname)
                        filename = '%s_%s_%s.vital' % (recorded.client.bed.name, date_str, time_str)
                        with open(os.path.join(pathname, filename), 'wb+') as destination:
                            for chunk in request.FILES['attachment'].chunks():
                                destination.write(chunk)
                        recorded.file_path = os.path.join(pathname, filename)
                        recorded.save(update_fields=['file_path'])
                        if settings.SERVICE_CONFIGURATIONS['STORAGE_SERVER']:
                            file_upload_storage(date_str, recorded.client.bed.name, os.path.join(pathname, filename))
                        if settings.SERVICE_CONFIGURATIONS['DB_SERVER']:
                            try:
                                db_upload_main_numeric(os.path.join(pathname, filename), target_client.bed.room.name, target_client.bed.name)
                                db_upload_summary(recorded)
                                r_dict['success'] = True
                                r_dict['message'] = 'Recording info was added and file was uploaded correctly.'
                            except Exception as e:
                                r_dict['success'] = True
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


