import json
import os.path
import datetime
import requests
from .forms import UploadFileForm
from fluent import sender
from ftplib import FTP
from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render
from sa_api.models import Device, Client, Bed, Channel, Room, FileRecorded, ClientBusSlot
from django.views.decorators.csrf import csrf_exempt

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

    if device_type is not None:
        target_devices = Device.objects.filter(device_type=device_type)
        if target_devices.count() == 0:
            if settings.SERVICE_CONFIGURATIONS['SERVER_TYPE'] == 'global':
                t_dev = Device.objects.create(device_type=device_type, displayed_name=device_type)
                r_dict['device_type'] = t_dev.device_type
                r_dict['displayed_name'] = t_dev.displayed_name
                r_dict['is_main'] = t_dev.is_main
                r_dict['success'] = True
                r_dict['message'] = 'New device was added.'
            else:
                result = requests.get('http://%s:%d/server/device_info' % (settings.SERVICE_CONFIGURATIONS['GLOBAL_SERVER_HOSTNAME'], settings.SERVICE_CONFIGURATIONS['GLOBAL_SERVER_PORT']), params=request.GET)
                if int(result.status_code/100) != 2:
                    r_dict['success'] = False
                    r_dict['message'] = 'A Global API server returned status code %d' % ( result.status_code )
                else:
                    server_result = json.loads(result.content)
                    t_dev = Device.objects.create(device_type=server_result['device_type'], displayed_name=server_result['device_type'], is_main=server_result['is_main'])
                    r_dict['device_type'] = t_dev.device_type
                    r_dict['displayed_name'] = t_dev.displayed_name
                    r_dict['is_main'] = t_dev.is_main
                    r_dict['success'] = True
                    r_dict['message'] = 'Device information was acquired from a global server.'
        elif target_devices.count() == 1:
            r_dict['device_type'] = target_devices[0].device_type
            r_dict['displayed_name'] = target_devices[0].displayed_name
            r_dict['is_main'] = target_devices[0].is_main
            r_dict['success'] = True
            r_dict['message'] = 'Device information was returned correctly.'
        else:
            r_dict['success'] = False
            r_dict['message'] = 'Multiple devices was for %s found.' % (device_type)
    else:
        r_dict['success'] = False
        r_dict['message'] = 'Requested device type is none.'

    log_dict['RESULT'] = r_dict
    logger = sender.FluentSender('sa', host=settings.SERVICE_CONFIGURATIONS['LOG_SERVER_HOSTNAME'], port=settings.SERVICE_CONFIGURATIONS['LOG_SERVER_PORT'], nanosecond_precision=True)
    logger.emit(settings.SERVICE_CONFIGURATIONS['SERVER_TYPE'], log_dict)

    return HttpResponse(json.dumps(r_dict, sort_keys=True, indent=4), content_type="application/json; charset=utf-8")

# When a local server requested for device information.
# This function could be called only in a global server.
@csrf_exempt
def device_info_server(request):

    return device_info_body(request, 'server')

# When a client requested for device information.
# This function could be called either in a global server or in a local server.
@csrf_exempt
def device_info_client(request):

    return device_info_body(request, 'client')

# Main body of device_info API function
def channel_info_body(request, api_type):

    r_dict = dict()
    log_dict = dict()
    log_dict['REMOTE_ADDR'] = request.META['REMOTE_ADDR']
    log_dict['SERVER_NAME'] = 'global' if settings.SERVICE_CONFIGURATIONS['SERVER_TYPE'] == 'global' else settings.SERVICE_CONFIGURATIONS['LOCAL_SERVER_NAME']
    log_dict['CLIENT_TYPE'] = api_type
    log_dict['REQUEST_PATH'] = request.path
    log_dict['METHOD'] = request.method
    log_dict['PARAM'] = request.GET

    device_type = request.GET.get("device_type")
    channel_name = request.GET.get("channel_name")

    if device_type is not None and channel_name is not None:
        target_device = Device.objects.get_or_create(device_type=device_type)[0]
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
                else:
                    server_result = json.loads(result.content)
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

    log_dict['RESULT'] = r_dict
    logger = sender.FluentSender('sa', host=settings.SERVICE_CONFIGURATIONS['LOG_SERVER_HOSTNAME'], port=settings.SERVICE_CONFIGURATIONS['LOG_SERVER_PORT'], nanosecond_precision=True)
    logger.emit(settings.SERVICE_CONFIGURATIONS['SERVER_TYPE'], log_dict)

    return HttpResponse(json.dumps(r_dict, sort_keys=True, indent=4), content_type="application/json; charset=utf-8")

# When a local server requested for channel information.
# This function could be called only in a global server.
@csrf_exempt
def channel_info_server(request):

    if settings.SERVICE_CONFIGURATIONS['SERVER_TYPE'] != 'global':
        r_dict = dict()
        r_dict['success'] = False
        r_dict['message'] = 'A local server received a server API request.'
        return HttpResponse(json.dumps(r_dict, sort_keys=True, indent=4), content_type="application/json; charset=utf-8")

    return channel_info_body(request, 'server')

# When a client requested for channel information.
# This function could be called either in a global server or in a local server.
@csrf_exempt
def channel_info_client(request):

    return channel_info_body(request, 'client')

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

    if settings.SERVICE_CONFIGURATIONS['SERVER_TYPE'] == 'global':
        mac = request.GET.get('mac')
        if mac is not None:
            target_client = Client.objects.filter(mac=mac)
            if target_client.count() == 1:
                target_client[0].registered = 1
                target_client[0].save()
                r_dict['client_name'] = target_client[0].name
                r_dict['bed_name'] = target_client[0].bed.name
                r_dict['room_name'] = target_client[0].bed.room.name
                r_dict['success'] = True
                r_dict['message'] = 'Client information was returned correctly.'
            elif target_client.count() > 1:
                r_dict['success'] = False
                r_dict['message'] = 'Multiple clients for mac %s were found.'%(mac)
            else:
                unknown_bed = Bed.objects.filter(name='Unknown')
                if unknown_bed.count() == 0: # If unknown room and bed don't exist.
                    unknown_room = Room.objects.create(name='Uknown')
                    unknown_room.save()
                    unknown_bed = Bed.objects.create(name='Uknown', room=unknown_room)
                    unknown_bed.save()
                new_client = Client.objects.create(mac=mac, name='Unknown', bed=unknown_bed)
                new_client.save()
                r_dict['client_name'] = new_client.name
                r_dict['bed_name'] = new_client.bed.name
                r_dict['room_name'] = new_client.bed.room.name
                r_dict['success'] = True
                r_dict['message'] = 'A new client was added.'
        else:
            r_dict['success'] = False
            r_dict['message'] = 'Requested mac is none.'
    else:
        mac = request.GET.get('mac')
        if mac is not None:
            target_client = Client.objects.get(mac=mac)
            if target_client is not None:
                target_client.registered = 1
                target_client.save()
                r_dict['client_name'] = target_client.name
                target_bed = Bed.objects.get(pk=target_client.bed_id)
                r_dict['bed_name'] = target_bed.name
                r_dict['bed_id'] = target_bed.id
                r_dict['room_name'] = target_bed.room.name
                r_dict['room_id'] = target_bed.room.id
                r_dict['success'] = True
                r_dict['message'] = 'Client information was returned correctly.'
            else:
                r_dict['success'] = False
                r_dict['message'] = 'Requested client is none.'
        else:
            r_dict['success'] = False
            r_dict['message'] = 'Requested mac is none.'

    log_dict['RESULT'] = r_dict
    logger = sender.FluentSender('sa', host=settings.SERVICE_CONFIGURATIONS['LOG_SERVER_HOSTNAME'], port=settings.SERVICE_CONFIGURATIONS['LOG_SERVER_PORT'], nanosecond_precision=True)
    logger.emit(settings.SERVICE_CONFIGURATIONS['SERVER_TYPE'], log_dict)

    return HttpResponse(json.dumps(r_dict, sort_keys=True, indent=4), content_type="application/json; charset=utf-8")

# When a local server requested for channel information.
# This function could be called only in a global server.
@csrf_exempt
def client_info_server(request):

    r_dict = dict()
    r_dict['success'] = False
    r_dict['message'] = 'Client info API cannot be called from a local server.'

    return HttpResponse(json.dumps(r_dict, sort_keys=True, indent=4), content_type="application/json; charset=utf-8")

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

    mac = request.POST.get('mac')
    begin = request.POST.get("begin")
    end = request.POST.get("end")
    if mac is None:
        r_dict['success'] = False
        r_dict['message'] = 'Requested mac address is none.'
    elif begin is None:
        r_dict['success'] = False
        r_dict['message'] = 'Requested begining date is none.'
    elif end is None:
        r_dict['success'] = False
        r_dict['message'] = 'Requested end date is none.'
    else:
        target_client = Client.objects.get(mac=mac)
        if target_client is not None:
            r_dict['success'] = True
            r_dict['message'] = 'Recording info was added correctly.'
            if settings.SERVICE_CONFIGURATIONS['SERVER_TYPE'] == 'local':
                form = UploadFileForm(request.POST, request.FILES)
                if form.is_valid():
                    recorded = FileRecorded.objects.create(client=target_client, begin_date=begin, end_date=end)
                    date_str = datetime.datetime.strptime(recorded.begin_date, "%Y-%m-%dT%H:%M:%S%z").strftime("%y%m%d")
                    time_str = datetime.datetime.strptime(recorded.begin_date, "%Y-%m-%dT%H:%M:%S%z").strftime("%H%M%S")
                    pathname = '%s/%s'%(settings.SERVICE_CONFIGURATIONS['LOCAL_SERVER_DATAPATH'], recorded.client.bed.name)
                    if not os.path.exists(pathname):
                        os.makedirs(pathname)
                    filename = '%s_%s_%s.vital'%(recorded.client.bed.name, date_str, time_str)
                    with open(os.path.join(pathname, filename), 'wb+') as destination:
                        for chunk in request.FILES['attachment'].chunks():
                            destination.write(chunk)
                    recorded.file_path = os.path.join(pathname, filename)
                    recorded.save(update_fields=['file_path'])
                    if settings.SERVICE_CONFIGURATIONS['STORAGE_SERVER']:
                        file_upload_storage(date_str, recorded.client.bed.name, os.path.join(pathname, filename))
                    r_dict['success'] = True
                    r_dict['message'] = 'Recording info was added and file was uploaded correctly.'
                else:
                    r_dict['success'] = False
                    r_dict['message'] = 'File attachment is not valid.'
            else:
                FileRecorded.objects.create(client=target_client, begin_date=begin, end_date=end)
                r_dict['success'] = True
                r_dict['message'] = 'Recording info was added correctly.'
        else:
            r_dict['success'] = False
            r_dict['message'] = 'Requested client is none.'

    log_dict['RESULT'] = r_dict
    logger = sender.FluentSender('sa', host=settings.SERVICE_CONFIGURATIONS['LOG_SERVER_HOSTNAME'], port=settings.SERVICE_CONFIGURATIONS['LOG_SERVER_PORT'], nanosecond_precision=True)
    logger.emit(settings.SERVICE_CONFIGURATIONS['SERVER_TYPE'], log_dict)

    return HttpResponse(json.dumps(r_dict, sort_keys=True, indent=4), content_type="application/json; charset=utf-8")

# When a local server requested for channel information.
# This function could be called only in a global server.
@csrf_exempt
def recording_info_server(request):

    r_dict = dict()
    r_dict['success'] = False
    r_dict['message'] = 'Recording info API cannot be called from a local server.'

    return HttpResponse(json.dumps(r_dict, sort_keys=True, indent=4), content_type="application/json; charset=utf-8")

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
    uptime = int(request.GET.get('uptime'))
    status = request.GET.get('status')
    bus_raw = request.GET.get('bus_info')

    if mac is None or report_dt is None or status is None or bus_raw is None or uptime is None:
        r_dict['success'] = False
        r_dict['message'] = 'A requested parameter is none.'
    else:
        target_client = Client.objects.get(mac=mac)
        if target_client is not None:
            target_client.dt_report = report_dt
            target_client.dt_start_recording = record_begin_dt
            target_client.uptime = datetime.timedelta(seconds=uptime)
            target_client.save()
            bus = json.loads(bus_raw)
            remaining_slot = ClientBusSlot.objects.filter(client=target_client, active=True)
            for bus_name, bus_info in bus.items():
                for slot_info in bus_info:
                    slot_name = slot_info['slot']
                    remaining_slot = remaining_slot.exclude(bus=bus_name, name=slot_name)
                    target_clientbusslot = ClientBusSlot.objects.get_or_create(client=target_client, bus=bus_name, name=slot_name)[0]
                    if slot_info['device']!='':
                        target_device = Device.objects.get_or_create(device_type=slot_info['device'])[0]
                        target_clientbusslot.device = target_device
                    else:
                        target_clientbusslot.device = None
                    target_clientbusslot.save()
            remaining_slot.update(active=False)

            r_dict['success'] = True
            r_dict['message'] = 'Client status was updated correctly.'
        else:
            r_dict['success'] = False
            r_dict['message'] = 'Requested client is none.'

    return HttpResponse(json.dumps(r_dict, sort_keys=True, indent=4), content_type="application/json; charset=utf-8")
