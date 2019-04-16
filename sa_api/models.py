from django.db import models
from django.utils import timezone
from django.conf import settings
from django.core.files.storage import FileSystemStorage
import os

# Create your models here.


class OverwriteStorage(FileSystemStorage):
    def get_available_name(self, name, max_length=None):
        if self.exists(name):
            os.remove(os.path.join(settings.MEDIA_ROOT, name))
        return name


class Device(models.Model):
    device_type = models.CharField(max_length=64, unique=True)
    displayed_name = models.CharField(max_length=64, unique=True, null=True)
    is_main = models.BooleanField(default=False)
    use_custom_setting = models.BooleanField(default=False)

    def __str__(self):
        print(1, self.displayed_name)
        return self.displayed_name


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
    client_version = models.CharField(max_length=32, null=True)
    bed = models.ForeignKey('Bed', on_delete=models.SET_NULL, blank=True, null=True)
    registered = models.IntegerField(default=0)
    STATUS_UNKNOWN = 0
    STATUS_STANDBY = 1
    STATUS_RECORDING = 2
    CLIENT_STATUS_CHOICES = (
        (STATUS_UNKNOWN, "Unknown"),
        (STATUS_STANDBY, "Standby"),
        (STATUS_RECORDING, "Recording"),
    )
    status = models.IntegerField(choices=CLIENT_STATUS_CHOICES, default=0)

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

    class Meta:
        unique_together = (("name", "device"),)

    def __str__(self):
        return '%s, %s' % (self.device.device_type, self.name)


class FileRecorded(models.Model):
    client = models.ForeignKey('Client', on_delete=models.SET_NULL, blank=True, null=True)
    upload_date = models.DateTimeField(auto_now_add=True)
    begin_date = models.DateTimeField()
    end_date = models.DateTimeField()
    file_path = models.CharField(max_length=256, blank=True)

    def __str__(self):
        return self.file_path


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
