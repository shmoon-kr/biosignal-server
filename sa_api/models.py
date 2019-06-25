from django.db import models, connection
from django.utils import timezone
from django.utils.html import format_html
from django.conf import settings
from django.core.files.storage import FileSystemStorage
from pyfluent.client import FluentSender
import os
import datetime
import pytz
import numpy as np
import sa_api.VitalFileHandler as VFH


# Create your models here.

tz = pytz.timezone(settings.TIME_ZONE)


class OverwriteStorage(FileSystemStorage):
    def get_available_name(self, name, max_length=None):
        if self.exists(name):
            os.remove(os.path.join(settings.MEDIA_ROOT, name))
        return name


class Device(models.Model):
    dt_update = models.DateTimeField(auto_now=True)
    device_type = models.CharField(max_length=64, unique=True)
    displayed_name = models.CharField(max_length=64, unique=True, null=True, default=None)
    code = models.CharField(max_length=16, unique=True, null=True, default=None)
    db_table_name = models.CharField(max_length=64, unique=True, null=True, default=None)
    is_main = models.BooleanField(default=False)
    use_custom_setting = models.BooleanField(default=False)

    def __str__(self):
        return self.displayed_name


class DeviceAlias(models.Model):
    dt_update = models.DateTimeField(auto_now=True)
    alias = models.CharField(max_length=64, unique=True)
    device = models.ForeignKey('Device', on_delete=models.CASCADE)

    def __str__(self):
        return '%s -> %s' % (self.alias, self.device.displayed_name)

    class Meta:
        indexes = [
            models.Index(fields=['alias'], name='idx_alias'),
        ]


class Room(models.Model):
    name = models.CharField(max_length=64)

    def __str__(self):
        return self.name


class Bed(models.Model):
    name = models.CharField(max_length=64)
    BED_TYPE_CHOICES = (
        (0, "Others"),
        (1, "Operation Room"),
        (2, "Intensive Care Unit"),
        (3, "Emergency Room"),
        (4, "Acute Care Unit"),
        (5, "Delivery Floor"),
    )
    bed_type = models.IntegerField(choices=BED_TYPE_CHOICES, default=0)
    room = models.ForeignKey('Room', on_delete=models.CASCADE)

    def __str__(self):
        return self.name


class Client(models.Model):
    dt_update = models.DateTimeField(auto_now=True)
    dt_report = models.DateTimeField(default=timezone.now)
    dt_start_recording = models.DateTimeField(null=True)
    uptime = models.DurationField(null=True)
    name = models.CharField(max_length=64)
    mac = models.CharField(max_length=17, unique=True)
    ip_address = models.CharField(max_length=32, null=True)
    client_version = models.CharField(max_length=32, default='1.0.0', editable=False)
    bed = models.ForeignKey('Bed', on_delete=models.SET_NULL, blank=True, null=True)
    STATUS_UNKNOWN = 0
    STATUS_STANDBY = 1
    STATUS_RECORDING = 2
    CLIENT_STATUS_CHOICES = (
        (STATUS_UNKNOWN, "Unknown"),
        (STATUS_STANDBY, "Standby"),
        (STATUS_RECORDING, "Recording"),
    )
    status = models.IntegerField(choices=CLIENT_STATUS_CHOICES, default=0)

    def color_info(self):

        if self.bed.name == 'Reserved' if self.bed is not None else False:
            return 3, 'grey'
        elif self.dt_report + datetime.timedelta(seconds=3600) < timezone.now():
            return 0, 'red'
        elif not ClientBusSlot.objects.filter(client=self, active=True).count():
            return 1, 'orange'
        else:
            return 2, 'black'

    def colored_bed(self):
        return format_html('<span style="color: %s;">%s</span>' % (self.color_info()[1], self.bed.name if self.bed is not None else 'NULL'))

    colored_bed.allow_tags = True
#    colored_bed.admin_order_field = 'color_info'
    colored_bed.admin_order_field = 'bed__name'
    colored_bed.short_description = 'bed'

    def __str__(self):
        return self.name


class Channel(models.Model):
    dt_create = models.DateTimeField(auto_now_add=True)
    dt_update = models.DateTimeField(auto_now=True)
    is_unknown = models.BooleanField(default=True)
    use_custom_setting = models.BooleanField(default=False)
    name = models.CharField(max_length=64)
    abbreviation = models.CharField(max_length=32)
    device = models.ForeignKey('Device', on_delete=models.CASCADE, null=True)
    RECORDING_TYPE_CHOICES = (
        (1, "TYPE_WAV"),
        (2, "TYPE_NUM"),
        (3, "TYPE_IMG"),
        (5, "TYPE_STR"),
    )
    recording_type = models.IntegerField(choices=RECORDING_TYPE_CHOICES, default=2)
    RECORDING_FORMAT_CHOICES = (
        (0, "FMT_NULL"),
        (1, "FMT_FLOAT"),
        (2, "FMT_DOUBLE"),
        (3, "FMT_CHAR"),
        (4, "FMT_BYTE"),
        (5, "FMT_SHORT"),
        (6, "FMT_WORD"),
        (7, "FMT_LONG"),
        (8, "FMT_DWORD"),
    )
    recording_format = models.IntegerField(choices=RECORDING_FORMAT_CHOICES, default=0)
    unit = models.CharField(max_length=32)
    minval = models.FloatField(default=-100)
    maxval = models.FloatField(default=100)
    color_a = models.PositiveSmallIntegerField(default=255)
    color_r = models.PositiveSmallIntegerField(default=255)
    color_g = models.PositiveSmallIntegerField(default=255)
    color_b = models.PositiveSmallIntegerField(default=255)
    srate = models.FloatField(default=0)
    adc_gain = models.FloatField(default=1.0)
    adc_offset = models.FloatField(default=0.0)
    MON_TYPE_CHOICES = (
        (0, "UNDEFINED"),
        (1, "MON_ECG_WAV"),
        (2, "MON_ECG_HR"),
        (3, "MON_ECG_PVC"),
        (4, "MON_IABP_WAV"),
        (5, "MON_IABP_SBP"),
        (6, "MON_IABP_DBP"),
        (7, "MON_IABP_MBP"),
        (8, "MON_PLETH_WAV"),
        (9, "MON_PLETH_HR"),
        (10, "MON_PLETH_SPO2"),
        (11, "MON_RESP_WAV"),
        (12, "MON_RESP_RR"),
        (13, "MON_CO2_WAV"),
        (14, "MON_CO2_RR"),
        (15, "MON_CO2_CONC"),
        (16, "MON_NIBP_SBP"),
        (17, "MON_NIBP_DBP"),
        (18, "MON_NIBP_MBP"),
        (19, "MON_BT"),
        (20, "MON_CVP_WAV"),
        (21, "MON_CVP_CVP"),
    )
    mon_type = models.IntegerField(choices=MON_TYPE_CHOICES, default=0)

    def colored_abbreviation(self):
        color_code = format(self.color_r, '02x') + format(self.color_g, '02x') + format(self.color_b, '02x')
        return format_html('<span style="color: #%s; background-color: black;">%s</span>' % (color_code, self.abbreviation))

    colored_abbreviation.allow_tags = True
    colored_abbreviation.admin_order_field = 'abbreviation'
    colored_abbreviation.short_description = 'abbreviation'

    class Meta:
        unique_together = (("name", "device"),)

    def __str__(self):
        return '%s, %s' % (self.device.device_type, self.name)


class ChannelAlias(models.Model):
    dt_update = models.DateTimeField(auto_now=True)
    alias = models.CharField(max_length=64, unique=True)
    channel = models.ForeignKey('Channel', on_delete=models.CASCADE)

    def __str__(self):
        return '%s, %s -> %s' % (self.channel.device.displayed_name, self.alias, self.channel.abbreviation)


class FileRecorded(models.Model):
    client = models.ForeignKey('Client', on_delete=models.SET_NULL, blank=True, null=True)
    bed = models.ForeignKey('Bed', on_delete=models.SET_NULL, blank=True, null=True)
    upload_date = models.DateTimeField(auto_now_add=True)
    begin_date = models.DateTimeField()
    end_date = models.DateTimeField(null=True)
    file_path = models.CharField(max_length=256, blank=True)
    file_basename = models.CharField(max_length=256, blank=True)
    METHOD_CHOICES = (
        (0, "client"),
        (1, "migration"),
    )
    method = models.IntegerField(choices=METHOD_CHOICES, default=0)

    def decompose(self):

        connection.connect()

        filename_split = self.file_basename.split('_')
        decompose_path = os.path.join('decompose', filename_split[0], filename_split[1])

        timestamp_interval = 0.5

        read_start = datetime.datetime.now()
        try:
            handle = VFH.VitalFileHandler(self.file_path)
            raw_data_number = handle.export_number()
        except Exception as e:
            log_dict = dict()
            log_dict['ACTION'] = 'DECOMPOSE'
            log_dict['EVENT'] = 'EXCEPTION'
            log_dict['FILE_BASENAME'] = self.file_basename
            log_dict['MESSAGE'] = 'An exception %s was raised during vital file processing.' % e
            fluent = FluentSender(settings.SERVICE_CONFIGURATIONS['LOG_SERVER_HOSTNAME'],
                                  settings.SERVICE_CONFIGURATIONS['LOG_SERVER_PORT'], 'sa')
            fluent.send(log_dict, 'sa.' + settings.SERVICE_CONFIGURATIONS['SERVER_TYPE'])
            return

        if not len(raw_data_number):
            log_dict = dict()
            log_dict['ACTION'] = 'DECOMPOSE'
            log_dict['EVENT'] = 'ERROR'
            log_dict['FILE_BASENAME'] = self.file_basename
            log_dict['MESSAGE'] = 'No number data was found in vital file.'
            fluent = FluentSender(settings.SERVICE_CONFIGURATIONS['LOG_SERVER_HOSTNAME'],
                                  settings.SERVICE_CONFIGURATIONS['LOG_SERVER_PORT'], 'sa')
            fluent.send(log_dict, 'sa.' + settings.SERVICE_CONFIGURATIONS['SERVER_TYPE'])
            return

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
            elif tmp_aligned['device'] != ri[0] or ri[1] - tmp_aligned['timestamp'] > timestamp_interval or ri[
                2] in tmp_aligned:
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

        #dt_datetime = np.dtype(datetime.datetime)
        dt_str = np.dtype(str)

        numberinfofiles = NumberInfoFile.objects.filter(record=self)
        for numberinfofile in numberinfofiles:
            if os.path.exists(numberinfofile.file_path):
                os.remove(numberinfofile.file_path)
        numberinfofiles.delete()

        waveinfofiles = WaveInfoFile.objects.filter(record=self)
        for waveinfofile in waveinfofiles:
            if os.path.exists(waveinfofile.file_path):
                os.remove(waveinfofile.file_path)
        waveinfofiles.delete()

        unknown_device = set()

        end_dt = list()

        for found_device, cols in column_info.items():
            try:
                device = Device.objects.get(displayed_name=found_device)
            except Device.DoesNotExist:
                try:
                    device = DeviceAlias.objects.get(alias=found_device).device
                except DeviceAlias.DoesNotExist:
                    device = None
            if True if device is None else device.code is None:
                unknown_device.add(found_device)
                log_dict = dict()
                log_dict['ACTION'] = 'DECOMPOSE'
                log_dict['EVENT'] = 'UNDEFINED_DEVICE'
                log_dict['FILE_BASENAME'] = self.file_basename
                if found_device is None:
                    log_dict['MESSAGE'] = 'A new device %s was found.' % found_device
                else:
                    log_dict['MESSAGE'] = 'A code for device %s was not defiened.' % found_device
                fluent = FluentSender(settings.SERVICE_CONFIGURATIONS['LOG_SERVER_HOSTNAME'],
                                      settings.SERVICE_CONFIGURATIONS['LOG_SERVER_PORT'], 'sa')
                fluent.send(log_dict, 'sa.' + settings.SERVICE_CONFIGURATIONS['SERVER_TYPE'])
            else:
                if not os.path.exists(decompose_path):
                    os.makedirs(decompose_path)
                file_path = os.path.join(decompose_path, os.path.splitext(self.file_basename)[0] + '_%s.npz' % device.code)
                end_dt.append(max(timestamp_number[found_device]))
                np.savez_compressed(file_path, col_list=np.array([*cols], dtype=dt_str),
                                    timestamp=np.array(timestamp_number[found_device], dtype=np.float64),
                                    number=np.array(val_number[found_device], dtype=np.float32))

                NumberInfoFile.objects.create(record=self, device=device, file_path=file_path)

        if len(end_dt) and self.end_date is None:
            self.end_date = datetime.datetime.fromtimestamp(max(end_dt)).astimezone(tz) + datetime.timedelta(minutes=5)
            self.save()

        for track_info in handle.get_track_info():
            if track_info[0] not in unknown_device and track_info[2] in (1, 6):
                try:
                    device = Device.objects.get(displayed_name=track_info[0])
                except Device.DoesNotExist:
                    try:
                        device = DeviceAlias.objects.get(alias=track_info[0]).device
                    except DeviceAlias.DoesNotExist:
                        device = None
                if device is not None:
                    if not os.path.exists(decompose_path):
                        os.makedirs(decompose_path)
                    dt, packet_pointer, val = handle.export_wave(track_info[0], track_info[1])
                    file_path = os.path.join(decompose_path, os.path.splitext(self.file_basename)[0] + '_%s_%s.npz' % (
                                             device.code, track_info[1]))
                    np.savez_compressed(file_path, timestamp=dt, packet_pointer=packet_pointer, val=val)

                    WaveInfoFile.objects.create(record=self, device=device, channel_name=track_info[1],
                                                file_path=file_path, num_packets=len(dt), sampling_rate=track_info[3])

    def __str__(self):
        return self.file_path


class NumberInfoFile(models.Model):
    record = models.ForeignKey('FileRecorded', null=True, on_delete=models.CASCADE)
    device = models.ForeignKey('Device', null=True, on_delete=models.CASCADE)
    file_path = models.CharField(max_length=256, blank=True)

    def __str__(self):
        return '%s, %s' % (self.record.file_basename, self.device.displayed_name)

    class Meta:
        unique_together = ("record", "device")


class WaveInfoFile(models.Model):
    record = models.ForeignKey('FileRecorded', null=True, on_delete=models.CASCADE)
    device = models.ForeignKey('Device', null=True, on_delete=models.CASCADE)
    channel_name = models.CharField(max_length=64)
    file_path = models.CharField(max_length=256, blank=True)
    sampling_rate = models.FloatField(null=True)
    num_packets = models.IntegerField(null=True)

    def __str__(self):
        return '%s, %s, %s' % (self.record.file_basename, self.device.displayed_name, self.channel_name)

    class Meta:
        unique_together = ("record", "device", "channel_name")


class ClientBusSlot(models.Model):
    client = models.ForeignKey('Client', on_delete=models.CASCADE, null=True)
    name = models.CharField(max_length=64)
    bus = models.CharField(max_length=64, blank=True, null=True)
    device = models.ForeignKey('Device', on_delete=models.SET_NULL, blank=True, null=True)
    active = models.BooleanField(default=True)

    def __str__(self): # __str__ on Python 3
        if self.device is None:
            device = 'Not Connected'
        else:
            device = self.device.displayed_name
        return '%s, %s' % (self.name, device)

    class Meta:
        unique_together = ("client", "name", "bus")


class Review(models.Model):
    dt_report = models.DateField(default=timezone.now)
    name = models.CharField(max_length=255, blank=True)
    local_server_name = models.CharField(max_length=255, default=settings.SERVICE_CONFIGURATIONS['LOCAL_SERVER_NAME'])
    bed = models.ForeignKey('Bed', on_delete=models.SET_NULL, blank=True, null=True)
    chart = models.ImageField(upload_to='reviews', storage=OverwriteStorage())
    comment = models.TextField(blank=True)

    def __str__(self):
        return self.name

    class Meta:
        unique_together = ("name", "local_server_name")


class DeviceConfigPreset(models.Model):
    dt_update = models.DateTimeField(default=timezone.now)
    device = models.ForeignKey('Device', on_delete=models.CASCADE)
    name = models.CharField(max_length=255, blank=True, null=True)

    def __str__(self):
        return '%s, %s' % (self.device, self.name)

    class Meta:
        unique_together = ("device", "name")


class DeviceConfigPresetBed(models.Model):
    bed = models.ForeignKey('Bed', on_delete=models.CASCADE)
    preset = models.ForeignKey('DeviceConfigPreset', on_delete=models.CASCADE)

    def __str__(self):
        return self.preset.name


class DeviceConfigItem(models.Model):
    preset = models.ForeignKey('DeviceConfigPreset', on_delete=models.CASCADE)
    variable = models.CharField(max_length=255, blank=True, null=True)
    value = models.CharField(max_length=255, blank=True, null=True)

    def __str__(self):
        return '%s, %s' % (self.preset, self.variable)

    class Meta:
        unique_together = ("preset", "variable")


class AnesthesiaRecordEvent(models.Model):
    dt = models.DateTimeField(default=timezone.now)
    record = models.ForeignKey('AnesthesiaRecord', on_delete=models.CASCADE)
    category = models.CharField(max_length=255, blank=True, null=True)
    description = models.CharField(max_length=255, blank=True, null=True)


class AnesthesiaRecord(models.Model):
    dt_operation = models.DateField(default=timezone.now)
    bed = models.ForeignKey('Bed', on_delete=models.CASCADE)
    raw_record = models.TextField(blank=True)


class ManualInputEventItem(models.Model):
    dt = models.DateTimeField(default=timezone.now)
    record = models.ForeignKey('ManualInputEvent', on_delete=models.CASCADE)
    category = models.CharField(max_length=255, blank=True, null=True, default='Manual')
    description = models.CharField(max_length=255, blank=True, null=True)


class ManualInputEvent(models.Model):
    dt_operation = models.DateField(default=timezone.now)
    bed = models.ForeignKey('Bed', on_delete=models.CASCADE)
