import time
import json
import os.path
import datetime
from fluent import sender
from ftplib import FTP
from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render
from sa_api.models import Device, Client, Bed, Channel, Room, FileRecorded
from django.views.decorators.csrf import csrf_exempt

# Create your views here.

def file_upload_storage(date_string, bed_name, filepath):
    ftp = FTP(host=settings.SERVICE_CONFIGURATIONS['STORAGE_SERVER_HOSTNAME'], user=settings.SERVICE_CONFIGURATIONS['STORAGE_SERVER_USER'], passwd=settings.SERVICE_CONFIGURATIONS['STORAGE_SERVER_PASSWORD'])
    ftp.connect(host=settings.SERVICE_CONFIGURATIONS['STORAGE_SERVER_HOSTNAME'])
    ftp.login(user=settings.SERVICE_CONFIGURATIONS['STORAGE_SERVER_USER'], passwd=settings.SERVICE_CONFIGURATIONS['STORAGE_SERVER_PASSWWORD'])
    ftp.cwd(settings.SERVICE_CONFIGURATIONS['STORAGE_SERVER_PATH'])
    if bed_name not in ftp.nlst():
        ftp.mkd(bed_name)
    ftp.cwd(bed_name)
    if date_string not in ftp.nlst():
        ftp.mkd(date_string)
    ftp.cwd(date_string)
    file = open(settings.SERVICE_CONFIGURATIONS['LOCAL_SERVER_DATAPATH']+filepath, 'rb')
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
    log_dict['REQUEST_PATH'] = request.path
    log_dict['CLIENT_TYPE'] = api_type
    if device_type is not None:
        target_devices = Device.objects.filter(device_type=device_type)
        if target_devices.count() == 0:
            if settings.SERVICE_CONFIGURATIONS['SERVER_TYPE'] == 'global':
                new_device = Device(device_type=device_type, displayed_name=device_type)
                new_device.save()
                log_dict['success'] = r_dict['success'] = True
                log_dict['message'] = r_dict['message'] = 'New device was added.'
            else:
                log_dict['success'] = r_dict['success'] = False
                log_dict['message'] = r_dict['message'] = 'Code was not written yet. A global server device info api should be called here.'
        elif target_devices.count() > 1:
            log_dict['success'] = r_dict['success'] = False
            log_dict['message'] = r_dict['message'] = 'Multiple devices was for %s found.' % (device_type)
        else:
            log_dict['device_type'] = r_dict['device_type'] = target_devices[0].device_type
            log_dict['displayed_name'] = r_dict['displayed_name'] = target_devices[0].displayed_name
            log_dict['is_main'] = r_dict['is_main'] = target_devices[0].is_main
            log_dict['success'] = r_dict['success'] = True
            log_dict['message'] = r_dict['message'] = 'Device information was returned correctly.'
    else:
        log_dict['success'] = r_dict['success'] = False
        log_dict['message'] = r_dict['message'] = 'Requested device type is none.'

    logger = sender.FluentSender('sa', host=settings.SERVICE_CONFIGURATIONS['LOG_SERVER_HOSTNAME'], port=settings.SERVICE_CONFIGURATIONS['LOG_SERVER_PORT'], nanosecond_precision=True)
    logger.emit(settings.SERVICE_CONFIGURATIONS['SERVER_TYPE'], log_dict)

    return HttpResponse(json.dumps(r_dict, sort_keys=True, indent=4))

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
    log_dict['REQUEST_PATH'] = request.path
    log_dict['CLIENT_TYPE'] = api_type

    device_type = request.GET.get("device_type")
    channel_name = request.GET.get("channel_name")
    if device_type is not None and channel_name is not None:
        target_channel = Channel.objects.filter(name=channel_name, device_type=device_type)
        if target_channel.count() == 0:
            if settings.SERVICE_CONFIGURATIONS['SERVER_TYPE'] == 'global':
                new_channel = Channel(name=channel_name, device_type=device_type)
                new_channel.save()
                log_dict['success'] = r_dict['success'] = True
                log_dict['message'] = r_dict['message'] = 'A new channel was added.'
            else:
                log_dict['success'] = r_dict['success'] = False
                log_dict['message'] = r_dict['message'] = 'Code was not written yet. A global server device info api should be called here.'
        elif target_channel.count() > 1:
            log_dict['success'] = r_dict['success'] = False
            log_dict['message'] = r_dict['message'] = 'Multiple channels was for %s/%s found.' % (device_type, channel_name)
        else:
            log_dict['is_unknown'] = r_dict['is_unknown'] = target_channel[0].is_unknown
            if target_channel[0].is_unknown:
                log_dict['success'] = r_dict['success'] = True
                log_dict['message'] = r_dict['message'] = 'Channel information was not configured by an admin.'
            else:
                log_dict['use_custom_setting'] = r_dict['use_custom_setting'] = target_channel[0].use_custom_setting
                log_dict['channel_name'] = r_dict['channel_name'] = target_channel[0].name
                log_dict['device_type'] = r_dict['device_type'] = target_channel[0].device_type
                log_dict['abbreviation'] = r_dict['abbreviation'] = target_channel[0].abbreviation
                log_dict['recording_type'] = r_dict['recording_type'] = target_channel[0].recording_type
                log_dict['recording_format'] = r_dict['recording_format'] = target_channel[0].recording_format
                log_dict['unit'] = r_dict['unit'] = target_channel[0].unit
                log_dict['minval'] = r_dict['minval'] = target_channel[0].minval
                log_dict['maxval'] = r_dict['maxval'] = target_channel[0].maxval
                log_dict['color_a'] = r_dict['color_a'] = target_channel[0].color_a
                log_dict['color_r'] = r_dict['color_r'] = target_channel[0].color_r
                log_dict['color_g'] = r_dict['color_g'] = target_channel[0].color_g
                log_dict['color_b'] = r_dict['color_b'] = target_channel[0].color_b
                log_dict['srate'] = r_dict['srate'] = target_channel[0].srate
                log_dict['adc_gain'] = r_dict['adc_gain'] = target_channel[0].adc_gain
                log_dict['adc_offset'] = r_dict['adc_offset'] = target_channel[0].adc_offset
                log_dict['mon_type'] = r_dict['mon_type'] = target_channel[0].mon_type
                log_dict['success'] = r_dict['success'] = True
                log_dict['message'] = r_dict['message'] = 'Channel information was returned correctly.'
    else:
        log_dict['success'] = r_dict['success'] = False
        log_dict['message'] = r_dict['message'] = 'Requested device type or channel name is none.'

    logger = sender.FluentSender('sa', host=settings.SERVICE_CONFIGURATIONS['LOG_SERVER_HOSTNAME'], port=settings.SERVICE_CONFIGURATIONS['LOG_SERVER_PORT'], nanosecond_precision=True)
    logger.emit(settings.SERVICE_CONFIGURATIONS['SERVER_TYPE'], log_dict)

    return HttpResponse(json.dumps(r_dict, sort_keys=True, indent=4))

# When a local server requested for channel information.
# This function could be called only in a global server.
@csrf_exempt
def channel_info_server(request):

    return channel_info_body(request, 'server')

# When a client requested for channel information.
# This function could be called either in a global server or in a local server.
@csrf_exempt
def channel_info_client(request):

    return channel_info_body(request, 'client')

@csrf_exempt
def client_info(request):

    r_dict = dict()
    log_dict = dict()
    log_dict['REMOTE_ADDR'] = request.META['REMOTE_ADDR']
    log_dict['SERVER_NAME'] = 'global' if settings.SERVICE_CONFIGURATIONS['SERVER_TYPE'] == 'global' else settings.SERVICE_CONFIGURATIONS['LOCAL_SERVER_NAME']
    log_dict['REQUEST_PATH'] = request.path

    if settings.SERVICE_CONFIGURATIONS['SERVER_TYPE'] == 'global':
        mac = request.GET.get('mac')
        if mac is not None:
            target_client = Client.objects.filter(mac=mac)
            if target_client.count() == 1:
                target_client[0].registered = 1
                target_client[0].save()
                log_dict['client_name'] = r_dict['client_name'] = target_client[0].name
                log_dict['bed_name'] = r_dict['bed_name'] = target_client[0].bed.name
                log_dict['room_name'] = r_dict['room_name'] = target_client[0].bed.room.name
                log_dict['success'] = r_dict['success'] = True
                log_dict['message'] = r_dict['message'] = 'Client information was returned correctly.'
            elif target_client.count() > 1:
                log_dict['success'] = r_dict['success'] = False
                log_dict['message'] = r_dict['message'] = 'Multiple clients for mac %s were found.'%(mac)
            else:
                unknown_bed = Bed.objects.filter(name='Unknown')
                if unknown_bed.count() == 0: # If unknown room and bed don't exist.
                    unknown_room = Room.objects.create(name='Uknown')
                    unknown_room.save()
                    unknown_bed = Bed.objects.create(name='Uknown', room=unknown_room)
                    unknown_bed.save()
                new_client = Client.objects.create(mac=mac, name='Unknown', bed=unknown_bed)
                new_client.save()
                log_dict['client_name'] = r_dict['client_name'] = new_client.name
                log_dict['bed_name'] = r_dict['bed_name'] = new_client.bed.name
                log_dict['room_name'] = r_dict['room_name'] = new_client.bed.room.name
                log_dict['success'] = r_dict['success'] = True
                log_dict['message'] = r_dict['message'] = 'A new client was added.'
        else:
            log_dict['success'] = r_dict['success'] = False
            log_dict['message'] = r_dict['message'] = 'Requested mac is none.'
    else:
        mac = request.GET.get('mac')
        if mac is not None:
            target_client = Client.objects.get(mac=mac)
            if target_client is not None:
                target_client.registered = 1
                target_client.save()
                log_dict['client_name'] = r_dict['client_name'] = target_client.name
                target_bed = Bed.objects.get(pk=target_client.bed_id)
                log_dict['bed_name'] = r_dict['bed_name'] = target_bed.name
                log_dict['bed_id'] = r_dict['bed_id'] = target_bed.id
                log_dict['room_name'] = r_dict['room_name'] = target_bed.room.name
                log_dict['room_id'] = r_dict['room_id'] = target_bed.room.id
                log_dict['success'] = r_dict['success'] = True
                log_dict['message'] = r_dict['message'] = 'Client information was returned correctly.'
            else:
                log_dict['success'] = r_dict['success'] = False
                log_dict['message'] = r_dict['message'] = 'Requested client is none.'
        else:
            log_dict['success'] = r_dict['success'] = False
            log_dict['message'] = r_dict['message'] = 'Requested mac is none.'

    logger = sender.FluentSender('sa', host=settings.SERVICE_CONFIGURATIONS['LOG_SERVER_HOSTNAME'], port=settings.SERVICE_CONFIGURATIONS['LOG_SERVER_PORT'], nanosecond_precision=True)
    logger.emit(settings.SERVICE_CONFIGURATIONS['SERVER_TYPE'], log_dict)

    return HttpResponse(json.dumps(r_dict, sort_keys=True, indent=4), content_type="application/json; charset=utf-8")

@csrf_exempt
def recording_info(request):

    r_dict = dict()
    log_dict = dict()
    log_dict['REMOTE_ADDR'] = request.META['REMOTE_ADDR']
    log_dict['SERVER_NAME'] = 'global' if settings.SERVICE_CONFIGURATIONS['SERVER_TYPE'] == 'global' else settings.SERVICE_CONFIGURATIONS['LOCAL_SERVER_NAME']
    log_dict['REQUEST_PATH'] = request.path

    if settings.SERVICE_CONFIGURATIONS['SERVER_TYPE'] == 'global':
        mac = request.GET.get('mac')
        begin = request.GET.get("begin")
        end = request.GET.get("end")
        if mac is None:
            log_dict['success'] = r_dict['success'] = False
            log_dict['message'] = r_dict['message'] = 'Requested mac address is none.'
        elif begin is None:
            log_dict['success'] = r_dict['success'] = False
            log_dict['message'] = r_dict['message'] = 'Requested begining date is none.'
        elif end is None:
            log_dict['success'] = r_dict['success'] = False
            log_dict['message'] = r_dict['message'] = 'Requested end date is none.'
        else:
            target_client = Client.objects.get(mac=mac)
            if target_client is not None:
                recorded = FileRecorded.objects.create(client=target_client, begin_date=begin, end_date=end)
                recorded.save()
                log_dict['success'] = r_dict['success'] = True
                log_dict['message'] = r_dict['message'] = 'Recording info was added correctly.'
            else:
                log_dict['success'] = r_dict['success'] = False
                log_dict['message'] = r_dict['message'] = 'Requested client is none.'
    else:
        log_dict['success'] = r_dict['success'] = False
        log_dict['message'] = r_dict['message'] = 'A code was not written yet. A local server recording info api should be called here.'

    logger = sender.FluentSender('sa', host=settings.SERVICE_CONFIGURATIONS['LOG_SERVER_HOSTNAME'], port=settings.SERVICE_CONFIGURATIONS['LOG_SERVER_PORT'], nanosecond_precision=True)
    logger.emit(settings.SERVICE_CONFIGURATIONS['SERVER_TYPE'], log_dict)

    return HttpResponse(json.dumps(r_dict, sort_keys=True, indent=4))

@csrf_exempt
def file_upload(request):
    r_dict = dict()
    r_dict['code'] = 0
    mac = request.GET.get("mac")
    begin = request.GET.get("begin")
    end = request.GET.get("end")
    path = request.GET.get("path")
    room_id = request.GET.get("room_id")
    bed_id = request.GET.get("bed_id")
    if mac is not None and begin is not None \
        and end is not None and path is not None \
        and room_id is not None and bed_id is not None:

        client = Client.objects.get(mac=mac)
        if client is not None:
            bed_name = client.bed.name
            room_name = client.bed.room.name
            file_data = FileRecorded.objects.create(client=client,
                begin_date=begin, end_date=end, file_path=path,
                room_id=client.bed.room.id, bed_id=client.bed.id,
                bed_name=bed_name, room_name=room_name)
            date_string = datetime.datetime.strptime(begin,"%Y-%m-%d %H:%M:%S").strftime("%y%m%d")
            # file_upload_storage(date_string, bed_name, path)
            # file_data.bed_name = bed_name
            # file_data.room_name = room_name
            # file_data.bed_id = client.bed.id
            # file_data.room_id = client.bed.room.id
            # file_data.begin_date = begin
            # file_data.end_date = end
            # file_data.file_path = path
            file_data.save();
            if config.storage_server:
                file_upload_storage(date_string, bed_name, path)
            r_dict['code'] = 1
            r_dict['result'] = 'File record registered'
        else:
            r_dict['result'] = 'Invalid MAC'
    else:
        r_dict['result'] = 'Invalid arguments'

    # request.POST.
    #
    # target_client = Client.objects.filter(mac=mac)
    #
    # if target_client.count() == 0:
    #     r_dict['result'] = 'No such a device exists.'
    # elif target_client.count() == 1:
    #     target_client[0].registered = 1
    #     target_client[0].save()
    #
    #     r_dict['code'] = 1
    #     r_dict['result'] = 'Valid mac address.'
    # else:
    #     r_dict['result'] = 'Duplicated mac address.'
    # Write a file upload function here.
    return HttpResponse(json.dumps(r_dict, sort_keys=True, indent=4))

@csrf_exempt
def alive(request, mac):
    #    client = get_object_or_404(Client, mac=mac)
    target_client = Client.objects.get(mac=mac)
    r_dict = dict()
    r_dict['code'] = 0
    if target_client is not None:
        target_client.registered = 1
        target_client.save()
        r_dict['code'] = 1
        r_dict['result'] = 'Valid mac address.'
    else:
        r_dict['result'] = 'Invalid mac address.'
    return HttpResponse(json.dumps(r_dict, sort_keys=True, indent=4))

