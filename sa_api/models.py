from django.db import models, connection, utils, transaction
from django.db.models import Avg, Max, Min, Count
from django.utils import timezone
from django.utils.html import format_html
from django.conf import settings
from django.core.files import File
from django.core.files.storage import FileSystemStorage
from pyfluent.client import FluentSender
from scipy import stats
import re
import os
import pytz
import math
import datetime
import MySQLdb
import numpy as np
import sa_api.VitalFileHandler as VFH

# Create your models here.

tz = pytz.timezone(settings.TIME_ZONE)


class SingleFloatField(models.Field):
    def db_type(self, connection):
        return 'float'


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

    @staticmethod
    def map_device_alias(alias):
        mapping = {
            'CardioQ': 'Deltex/CardioQ',
            'Vigilance': 'Edwards/Vigilance',
            'Invos': 'Medtronic/INVOS',
            'BIS': 'Covidien/BIS',
            'Intellivue': 'Philips/IntelliVue',
            'EV1000': 'Edwards/EV1000',
            'Bx50': 'GE/Carescape',
            'Primus': 'Dräger/Primus',
            'Philips/M8000': 'Philips/IntelliVue',
            'GE/s5': 'GE/Carescape',
            'Drager/Primus': 'Dräger/Primus'
        }
        return mapping[alias] if alias in mapping.keys() else alias

    def cleansing(self, timestamp, col_dict, val):

        if self.displayed_name in ('GE/Carescape', 'Philips/IntelliVue'):
            if 'NIBP_SBP' in col_dict.keys() and 'NIBP_DBP' in col_dict.keys() and 'NIBP_MBP' in col_dict.keys():
                for i in range(len(val)):
                    if np.isnan(val[i, col_dict['NIBP_SBP']]) or np.isnan(val[i, col_dict['NIBP_DBP']]) or np.isnan(val[i, col_dict['NIBP_MBP']]):
                        val[i, col_dict['NIBP_SBP']] = val[i, col_dict['NIBP_DBP']] = val[i, col_dict['NIBP_MBP']] = np.nan
                    elif not val[i, col_dict['NIBP_SBP']] > val[i, col_dict['NIBP_MBP']] > val[i, col_dict['NIBP_DBP']]:
                        val[i, col_dict['NIBP_SBP']] = val[i, col_dict['NIBP_DBP']] = val[i, col_dict['NIBP_MBP']] = np.nan
            if 'ABP_SBP' in col_dict.keys() and 'ABP_DBP' in col_dict.keys() and 'ABP_MBP' in col_dict.keys():
                for i in range(len(val)):
                    if np.isnan(val[i, col_dict['ABP_SBP']]) or np.isnan(val[i, col_dict['ABP_DBP']]) or np.isnan(val[i, col_dict['ABP_MBP']]):
                        val[i, col_dict['ABP_SBP']] = val[i, col_dict['ABP_DBP']] = val[i, col_dict['ABP_MBP']] = np.nan
                    elif not val[i, col_dict['ABP_SBP']] > val[i, col_dict['ABP_MBP']] > val[i, col_dict['ABP_DBP']]:
                        val[i, col_dict['ABP_SBP']] = val[i, col_dict['ABP_DBP']] = val[i, col_dict['ABP_MBP']] = np.nan
                    elif not 300 > val[i, col_dict['ABP_SBP']] > 20:
                        val[i, col_dict['ABP_SBP']] = val[i, col_dict['ABP_DBP']] = val[i, col_dict['ABP_MBP']] = np.nan
                    elif not 225 > val[i, col_dict['ABP_DBP']] > 5:
                        val[i, col_dict['ABP_SBP']] = val[i, col_dict['ABP_DBP']] = val[i, col_dict['ABP_MBP']] = np.nan
                val[:, col_dict['ABP_SBP']] = NumberInfoFile.smoothing_number(val[:, col_dict['ABP_SBP']], timestamp)
                val[:, col_dict['ABP_DBP']] = NumberInfoFile.smoothing_number(val[:, col_dict['ABP_DBP']], timestamp)
                val[:, col_dict['ABP_MBP']] = NumberInfoFile.smoothing_number(val[:, col_dict['ABP_MBP']], timestamp)
            if 'RAP' in col_dict.keys():
                for i in range(len(val)):
                    if not 60 > val[i, col_dict['RAP']] > -5:
                        val[i, col_dict['RAP']] = np.nan
                val[:, col_dict['RAP']] = NumberInfoFile.smoothing_number(val[:, col_dict['RAP']], timestamp)
            if 'CVP' in col_dict.keys():
                for i in range(len(val)):
                    if not 60 > val[i, col_dict['CVP']] > -5:
                        val[i, col_dict['CVP']] = np.nan
                val[:, col_dict['CVP']] = NumberInfoFile.smoothing_number(val[:, col_dict['CVP']], timestamp)
            if 'ABP_HR' in col_dict.keys():
                val[:, col_dict['ABP_HR']] = NumberInfoFile.smoothing_number(val[:, col_dict['ABP_HR']], timestamp)
            if 'PLETH_HR' in col_dict.keys():
                val[:, col_dict['PLETH_HR']] = NumberInfoFile.smoothing_number(val[:, col_dict['PLETH_HR']], timestamp)
            if 'HR' in col_dict.keys():
                val[:, col_dict['HR']] = NumberInfoFile.smoothing_number(val[:, col_dict['HR']], timestamp)
            if 'ECG_HR' in col_dict.keys():
                val[:, col_dict['ECG_HR']] = NumberInfoFile.smoothing_number(val[:, col_dict['ECG_HR']], timestamp)

        return val

    def __str__(self):
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
        (6, "Recovery Room"),
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
        return format_html('<span style="color: %s;">%s</span>' % (
        self.color_info()[1], self.bed.name if self.bed is not None else 'NULL'))

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
    abbreviation = models.CharField(max_length=64)
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
        return format_html(
            '<span style="color: #%s; background-color: black;">%s</span>' % (color_code, self.abbreviation))

    colored_abbreviation.allow_tags = True
    colored_abbreviation.admin_order_field = 'abbreviation'
    colored_abbreviation.short_description = 'abbreviation'

    class Meta:
        unique_together = (("name", "device"),)

    def __str__(self):
        return '%s, %s' % (self.device.displayed_name, self.abbreviation)


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

    @staticmethod
    def map_channel_name(displayed_name, channel_name):

        r = channel_name

        if displayed_name == 'GE/Carescape':
            mapping = {
                'ART_SBP': 'ABP_SBP',
                'ART_DBP': 'ABP_DBP',
                'ART_MBP': 'ABP_MBP',
                'ART_HR': 'ABP_HR',
                'BT': 'BT_PA',
                'CVP_MBP': 'CVP',
                'CVP_SBP': None,
                'CVP_DBP': None,
                'CVP_HR': None,
                'LAP_MBP': 'LAP',
                'LAP_SBP': None,
                'LAP_DBP': None,
                'LAP_HR': None,
                'RAP_MBP': 'RAP',
                'RAP_SBP': None,
                'RAP_DBP': None,
                'RAP_HR': None,
                'RVP_MBP': 'RVP',
                'RVP_SBP': None,
                'RVP_DBP': None,
                'RVP_HR': None,
                'ICP_MBP': 'ICP',
                'ICP_SBP': None,
                'ICP_DBP': None,
                'ICP_HR': None,
                'AGENT_MAC_AGE': 'MAC_AGE',
                'AMB_PRES': 'CO2_AMB_PRESS',
                'ETCO2': 'CO2_ET',
                'ETCO2_PERCENT': 'CO2_ET_PERCENT',
                'FEO2': 'O2_FE',
                'FIO2': 'O2_FI',
                'FLOW_MV_EXP': 'MV',
                'FLOW_PPEAK': 'PPEAK',
                'FLOW_PPLAT': 'PPLAT',
                'FLOW_RR': 'RR_VENT',
                'FLOW_TV_INSP': 'TV_INSP',
                'FLOWVOL_epeep': None,
                'FLOWVOL_ie_ratio': None,
                'FLOWVOL_pmean': None,
                'FLOWVOL_mv_spont': None,
                'INCO2': 'CO2_IN',
                'INCO2_PERCENT': 'CO2_IN_PERCENT',
                'MV_EXP': 'MV',
                'PLETH2_HR': 'PLETH_HR',
                'PLETH2_IR_AMP': 'PLETH_IRAMP',
                'PLETH_IR_AMP': 'PLETH_IRAMP',
                'PLETH2_SPO2': 'PLETH_SPO2',
                'RR_CO2': 'CO2_RR',
                'HR_ECG': 'ECG_HR',
                'HR_MIN': 'ECG_HR_MIN',
                'HR_MAX': 'ECG_HR_MAX',
                'ST': 'ECG_ST',
                'ST_I': 'ECG_ST_I',
                'ST_II': 'ECG_ST_II',
                'ST_III': 'ECG_ST_III',
                'ST_V': 'ECG_ST_V',
                'ST_AVF': 'ECG_ST_AVF',
                'ST_AVL': 'ECG_ST_AVL',
                'ST_AVR': 'ECG_ST_AVR',
                'TEMP': 'BT_PA',
                'TOF_COUNT': 'NMT_TOF_CNT',
                'NIBP_MEAN': 'NIBP_MBP',
                'NIBP_SYS': 'NIBP_SBP',
                'NIBP_DIA': 'NIBP_DBP'
            }
            if re.compile('^(ABP|ART|FEM|PA|CVP|LAP|RAP|RVP|ICP)[1-8]_(SBP|DBP|MBP|HR)$').match(r) or re.compile(
                    '^(CVP|LAP|RAP|RVP|ICP)[1-8]$').match(r):
                r = r.replace('1', '')
                r = r.replace('2', '')
                r = r.replace('3', '')
                r = r.replace('4', '')
                r = r.replace('5', '')
                r = r.replace('6', '')
                r = r.replace('7', '')
                r = r.replace('8', '')
            elif re.compile('^BT[1-4]$').match(r):
                r = r.replace('1', '')
                r = r.replace('2', '')
                r = r.replace('3', '')
                r = r.replace('4', '')
            if re.compile('^T[1-4]$').match(r):
                r = 'BT_PA'
            if re.compile('^EEG[1-4]_(ALPHA|BETA|DELTA|THETA|AMP|BSR|MF|SEF)$').match(r):
                r = None
            if r in mapping.keys():
                r = mapping[r]
        elif displayed_name == 'Philips/IntelliVue':
            mapping = {
                'AWAY_CO2_ET': 'CO2_ET',
                'AWAY_CO2_INSP_MIN': 'CO2_INSP_MIN',
                'MEAN': 'ABP_MBP',
                'SYS': 'ABP_SBP',
                'DIA': 'ABP_DBP',
                'ABP_MEAN': 'ABP_MBP',
                'ABP_SYS': 'ABP_SBP',
                'ABP_DIA': 'ABP_DBP',
                'ART_MEAN': 'ABP_MBP',
                'ART_SYS': 'ABP_SBP',
                'ART_DIA': 'ABP_DBP',
                'AOP_MEAN': 'AOP_MBP',
                'AOP_SYS': 'AOP_SBP',
                'AOP_DIA': 'AOP_DBP',
                'BT_ESOPH': 'TEMP_ESOPH',
                'CO_CTS': 'CO',
                'CI_CTS': 'CI',
                'CVP_MEAN': 'CVP_MBP',
                'CVP_SYS': 'CVP_SBP',
                'CVP_DIA': 'CVP_DBP',
                'DES_ET_PERC': 'DESFL_ET',
                'DES_INSP_PERC': 'DESFL_INSP',
                'ENF_ET_PERC': 'ENFL_ET',
                'ENF_INSP_PERC': 'ENFL_INSP',
                'HAL_ET_PERC': 'HAL_ET',
                'HAL_INSP_PERC': 'HAL_INSP',
                'ICP_MEAN': 'ICP_MBP',
                'LAP_MEAN': 'LAP_MBP',
                'LAP_SYS': 'LAP_SBP',
                'LAP_DIA': 'LAP_DBP',
                'PRESS_CEREB_PERF': 'CPP',
                'PERF_REL': 'PLETH_PERF_REL',
                'RAP_MEAN': 'RAP_MBP',
                'RAP_SYS': 'RAP_SBP',
                'RAP_DIA': 'RAP_DBP',
                'ST_I': 'ECG_ST_I',
                'ST_II': 'ECG_ST_II',
                'ST_III': 'ECG_ST_III',
                'ST_V': 'ECG_ST_V',
                'ST_AVF': 'ECG_ST_AVF',
                'ST_AVL': 'ECG_ST_AVL',
                'ST_AVR': 'ECG_ST_AVR',
                'ST_MCL': 'ECG_ST_MCL',
                'TOF1': 'TOF_1',
                'TOF2': 'TOF_2',
                'TOF3': 'TOF_3',
                'TOF4': 'TOF_4',
                'EEG_BIS': 'BIS_BIS',
                'EEG_BIS_SQI': 'BIS_SQI',
                'EEG_FREQ_PWR_SPEC_CRTX_SPECTRAL_EDGE': 'BIS_SEF',
                'EEG_RATIO_SUPPRN': 'BIS_SR',
                'EMG_ELEC_POTL_MUSCL': 'BIS_EMG',
                'NIBP_MEAN': 'NIBP_MBP',
                'NIBP_SYS': 'NIBP_SBP',
                'NIBP_DIA': 'NIBP_DBP',
                'O2_ET_PERC': 'O2_ET',
                'O2_INSP_PERC': 'O2_INSP',
                'PAP_MEAN': 'PAP_MBP',
                'PAP_SYS': 'PAP_SBP',
                'PAP_DIA': 'PAP_DBP',
                'QT_HR': 'ECG_QT_HR',
                'QT_GL': 'ECG_QT_GL',
                'QTc': 'ECG_QTc',
                'QTc_DELTA': 'ECG_QTc_DELTA',
                'SEVO_ET_PERC': 'SEVOFL_ET',
                'SEVO_INSP_PERC': 'SEVOFL_INSP',
                'UA_MEAN': 'UA_MBP',
                'UA_SYS': 'UA_SBP',
                'UA_DIA': 'UA_DBP',
                'VOL_BLD_STROKE': 'SV',
                'VOL_BLD_STROKE_INDEX': 'SI',
                'VOL_BLD_STROKE_VAR': 'SVV'
            }
            if r in mapping.keys():
                r = mapping[r]
        elif displayed_name == 'Masimo/Root':
            mapping = {
                'EEG_SEFL': 'SEFL',
                'EEG_SEFR': 'SEFR',
                'EEG_ARTF': 'ARTF',
                'EEG_SR': 'SR',
                'EEG_EMG': 'EMG',
                'EEG_PSI': 'PSI'
            }
            if r in mapping.keys():
                r = mapping[r]

        return r

    def load_summary(self):

        if self.end_date is None:
            return
        elif self.end_date - self.begin_date <= datetime.timedelta(seconds=600):
            return

        try:
            nif = NumberInfoFile.objects.get(record=self, device__is_main=True)
        except NumberInfoFile.MultipleObjectsReturned as e:
            log_dict = dict()
            log_dict['SERVER_NAME'] = 'global' \
                if settings.SERVICE_CONFIGURATIONS['SERVER_TYPE'] == 'global' \
                else settings.SERVICE_CONFIGURATIONS['LOCAL_SERVER_NAME']
            log_dict['ACTION'] = 'SUMMARY_MAIN'
            log_dict['FILE_NAME'] = self.file_basename
            log_dict['MESSAGE'] = 'Multiple main devices were found.'
            log_dict['EXCEPTION'] = str(e)
            fluent = FluentSender(settings.SERVICE_CONFIGURATIONS['LOG_SERVER_HOSTNAME'],
                                  settings.SERVICE_CONFIGURATIONS['LOG_SERVER_PORT'], 'sa')
            fluent.send(log_dict, 'sa.' + settings.SERVICE_CONFIGURATIONS['SERVER_TYPE'])
            return
        except NumberInfoFile.DoesNotExist as e:
            return

        summary, _ = SummaryFileRecorded.objects.get_or_create(record=self, main_device=nif.device)
        if summary.main_device.displayed_name == 'GE/Carescape':
            vals = NumberGEC.objects.filter(record=self)
            summary.cnt_total = vals.count()
            agg = vals.aggregate(Count('NIBP_SBP'), Min('NIBP_SBP'), Max('NIBP_SBP'), Avg('NIBP_SBP'),
                                 Count('NIBP_DBP'), Min('NIBP_DBP'), Max('NIBP_DBP'), Avg('NIBP_DBP'),
                                 Count('NIBP_MBP'), Min('NIBP_MBP'), Max('NIBP_MBP'), Avg('NIBP_MBP'),
                                 Count('ABP_HR'), Min('ABP_HR'), Max('ABP_HR'), Avg('ABP_HR'),
                                 Count('ABP_SBP'), Min('ABP_SBP'), Max('ABP_SBP'), Avg('ABP_SBP'),
                                 Count('ABP_DBP'), Min('ABP_DBP'), Max('ABP_DBP'), Avg('ABP_DBP'),
                                 Count('ABP_MBP'), Min('ABP_MBP'), Max('ABP_MBP'), Avg('ABP_MBP'),
                                 Count('PLETH_HR'), Min('PLETH_HR'), Max('PLETH_HR'), Avg('PLETH_HR'),
                                 Count('HR'), Min('HR'), Max('HR'), Avg('HR'),
                                 Count('BT_PA'), Min('BT_PA'), Max('BT_PA'), Avg('BT_PA'),
                                 Count('PLETH_SPO2'), Min('PLETH_SPO2'), Max('PLETH_SPO2'), Avg('PLETH_SPO2'))
            if agg['ABP_MBP__count'] > summary.cnt_total / 2:
                summary.bp_channel = 'ABP'
            elif agg['NIBP_MBP__count'] > summary.cnt_total / 2:
                summary.bp_channel = 'NIBP'
            else:
                summary.bp_channel = None

            if summary.bp_channel is not None:
                summary.cnt_bp = agg[summary.bp_channel + '_MBP__count']
                summary.min_sbp = agg[summary.bp_channel + '_SBP__min']
                summary.max_sbp = agg[summary.bp_channel + '_SBP__max']
                summary.avg_sbp = agg[summary.bp_channel + '_SBP__avg']
                summary.min_dbp = agg[summary.bp_channel + '_DBP__min']
                summary.max_dbp = agg[summary.bp_channel + '_DBP__max']
                summary.avg_dbp = agg[summary.bp_channel + '_DBP__avg']
                summary.min_mbp = agg[summary.bp_channel + '_MBP__min']
                summary.max_mbp = agg[summary.bp_channel + '_MBP__max']
                summary.avg_mbp = agg[summary.bp_channel + '_MBP__avg']

            if agg['PLETH_HR__avg'] > 5 if agg['PLETH_HR__count'] else False:
                summary.hr_channel = 'PLETH_HR'
            elif summary.bp_channel == 'ABP':
                summary.hr_channel = 'ABP_HR'
            elif agg['HR__count']:
                summary.hr_channel = 'HR'
            else:
                summary.hr_channel = None

            if summary.hr_channel is not None:
                summary.cnt_hr = agg[summary.hr_channel + '__count']
                summary.min_hr = agg[summary.hr_channel + '__min']
                summary.max_hr = agg[summary.hr_channel + '__max']
                summary.avg_hr = agg[summary.hr_channel + '__avg']

            summary.cnt_bt = agg['BT_PA__count']
            summary.min_bt = agg['BT_PA__min']
            summary.max_bt = agg['BT_PA__max']
            summary.avg_bt = agg['BT_PA__avg']

            summary.cnt_spo2 = agg['PLETH_SPO2__count']
            summary.min_spo2 = agg['PLETH_SPO2__min']
            summary.max_spo2 = agg['PLETH_SPO2__max']
            summary.avg_spo2 = agg['PLETH_SPO2__avg']

            summary.save()
            return True

        elif summary.main_device.displayed_name == 'Philips/IntelliVue':
            vals = NumberPIV.objects.filter(record=self)
            summary.cnt_total = vals.count()
            agg = vals.aggregate(Count('NIBP_SBP'), Min('NIBP_SBP'), Max('NIBP_SBP'), Avg('NIBP_SBP'),
                                 Count('NIBP_DBP'), Min('NIBP_DBP'), Max('NIBP_DBP'), Avg('NIBP_DBP'),
                                 Count('NIBP_MBP'), Min('NIBP_MBP'), Max('NIBP_MBP'), Avg('NIBP_MBP'),
                                 Count('ABP_SBP'), Min('ABP_SBP'), Max('ABP_SBP'), Avg('ABP_SBP'),
                                 Count('ABP_DBP'), Min('ABP_DBP'), Max('ABP_DBP'), Avg('ABP_DBP'),
                                 Count('ABP_MBP'), Min('ABP_MBP'), Max('ABP_MBP'), Avg('ABP_MBP'),
                                 Count('PLETH_HR'), Min('PLETH_HR'), Max('PLETH_HR'), Avg('PLETH_HR'),
                                 Count('HR'), Min('HR'), Max('HR'), Avg('HR'),
                                 Count('ECG_HR'), Min('ECG_HR'), Max('ECG_HR'), Avg('ECG_HR'),
                                 Count('TEMP'), Min('TEMP'), Max('TEMP'), Avg('TEMP'),
                                 Count('PLETH_SAT_O2'), Min('PLETH_SAT_O2'), Max('PLETH_SAT_O2'), Avg('PLETH_SAT_O2'))
            if agg['ABP_MBP__count'] > summary.cnt_total / 2:
                summary.bp_channel = 'ABP'
            elif agg['NIBP_MBP__count'] > summary.cnt_total / 2:
                summary.bp_channel = 'NIBP'
            else:
                summary.bp_channel = None

            if summary.bp_channel is not None:
                summary.cnt_bp = agg[summary.bp_channel + '_MBP__count']
                summary.min_sbp = agg[summary.bp_channel + '_SBP__min']
                summary.max_sbp = agg[summary.bp_channel + '_SBP__max']
                summary.avg_sbp = agg[summary.bp_channel + '_SBP__avg']
                summary.min_dbp = agg[summary.bp_channel + '_DBP__min']
                summary.max_dbp = agg[summary.bp_channel + '_DBP__max']
                summary.avg_dbp = agg[summary.bp_channel + '_DBP__avg']
                summary.min_mbp = agg[summary.bp_channel + '_MBP__min']
                summary.max_mbp = agg[summary.bp_channel + '_MBP__max']
                summary.avg_mbp = agg[summary.bp_channel + '_MBP__avg']

            if agg['PLETH_HR__avg'] > 5 if agg['PLETH_HR__avg'] is not None else False:
                summary.hr_channel = 'PLETH_HR'
            elif summary.bp_channel == 'ABP':
                summary.hr_channel = 'HR'
            elif agg['ECG_HR__count']:
                summary.hr_channel = 'ECG_HR'
            else:
                summary.hr_channel = None

            if summary.hr_channel is not None:
                summary.cnt_hr = agg[summary.hr_channel + '__count']
                summary.min_hr = agg[summary.hr_channel + '__min']
                summary.max_hr = agg[summary.hr_channel + '__max']
                summary.avg_hr = agg[summary.hr_channel + '__avg']

            summary.cnt_bt = agg['TEMP__count']
            summary.min_bt = agg['TEMP__min']
            summary.max_bt = agg['TEMP__max']
            summary.avg_bt = agg['TEMP__avg']

            summary.cnt_spo2 = agg['PLETH_SAT_O2__count']
            summary.min_spo2 = agg['PLETH_SAT_O2__min']
            summary.max_spo2 = agg['PLETH_SAT_O2__max']
            summary.avg_spo2 = agg['PLETH_SAT_O2__avg']

            summary.save()
            return True

        else:
            return False

    def load_number(self, reload=False):

        for ni in NumberInfoFile.objects.filter(record=self):
            try:
                ni.load_number(reload=reload)
            except Exception as e:
                log_dict = dict()
                log_dict['SERVER_NAME'] = 'global' \
                    if settings.SERVICE_CONFIGURATIONS['SERVER_TYPE'] == 'global' \
                    else settings.SERVICE_CONFIGURATIONS['LOCAL_SERVER_NAME']
                log_dict['ACTION'] = 'LOAD_NUMBER'
                log_dict['FILE_NAME'] = self.file_basename
                log_dict['MESSAGE'] = 'An exception was raised during a DB loading process.'
                log_dict['EXCEPTION'] = str(e)
                fluent = FluentSender(settings.SERVICE_CONFIGURATIONS['LOG_SERVER_HOSTNAME'],
                                      settings.SERVICE_CONFIGURATIONS['LOG_SERVER_PORT'], 'sa')
                fluent.send(log_dict, 'sa.' + settings.SERVICE_CONFIGURATIONS['SERVER_TYPE'])

        return

    def decompose(self):

        connection.connect()
        filename_split = self.file_basename.split('_')
        decompose_path = os.path.join('decompose', filename_split[0], filename_split[1])
        os.makedirs(os.path.join(settings.MEDIA_ROOT, decompose_path), mode=0o775, exist_ok=True)

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
            elif tmp_aligned['device'] != ri[0] or ri[1] - tmp_aligned['timestamp'] > timestamp_interval or ri[2] in tmp_aligned:
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

        # dt_datetime = np.dtype(datetime.datetime)
        dt_str = np.dtype(str)

        numberinfofiles = NumberInfoFile.objects.filter(record=self)
        for numberinfofile in numberinfofiles:
            if os.path.exists(os.path.join(settings.MEDIA_ROOT, numberinfofile.file.name)):
                os.remove(os.path.join(settings.MEDIA_ROOT, numberinfofile.file.name))
        numberinfofiles.delete()

        waveinfofiles = WaveInfoFile.objects.filter(record=self)
        for waveinfofile in waveinfofiles:
            if os.path.exists(os.path.join(settings.MEDIA_ROOT, waveinfofile.file.name)):
                os.remove(os.path.join(settings.MEDIA_ROOT, waveinfofile.file.name))
        waveinfofiles.delete()

        unknown_device = set()
        end_dt = list()

        for found_device, cols in column_info.items():
            try:
                device = Device.objects.get(displayed_name=Device.map_device_alias(found_device))
            except Device.DoesNotExist:
                device = None
            if True if device is None else device.code is None:
                unknown_device.add(found_device)
                log_dict = dict()
                log_dict['ACTION'] = 'DECOMPOSE'
                log_dict['EVENT'] = 'UNDEFINED_DEVICE'
                log_dict['FILE_BASENAME'] = self.file_basename
                if device is None:
                    log_dict['MESSAGE'] = 'A new device %s was found.' % found_device
                else:
                    log_dict['MESSAGE'] = 'A code for device %s was not defiened.' % found_device
                fluent = FluentSender(settings.SERVICE_CONFIGURATIONS['LOG_SERVER_HOSTNAME'],
                                      settings.SERVICE_CONFIGURATIONS['LOG_SERVER_PORT'], 'sa')
                fluent.send(log_dict, 'sa.' + settings.SERVICE_CONFIGURATIONS['SERVER_TYPE'])
            else:
                if not os.path.exists(os.path.join(settings.MEDIA_ROOT, decompose_path)):
                    os.makedirs(os.path.join(settings.MEDIA_ROOT, decompose_path))
                file_path = os.path.join(decompose_path,
                                         os.path.splitext(self.file_basename)[0] + '_%s.npz' % device.code)
                file_path_media = os.path.join(settings.MEDIA_ROOT, file_path)
                end_dt.append(max(timestamp_number[found_device]))
                np.savez_compressed(file_path_media, col_list=np.array([*cols], dtype=dt_str),
                                    timestamp=np.array(timestamp_number[found_device], dtype=np.float64),
                                    number=np.array(val_number[found_device], dtype=np.float32))
                nif, created = NumberInfoFile.objects.get_or_create(record=self, device=device, defaults={
                    'file': file_path
                })
                if not created:
                    log_dict = dict()
                    log_dict['ACTION'] = 'DECOMPOSE'
                    log_dict['EVENT'] = 'DUPLICATED_DEVICE'
                    log_dict['FILE_BASENAME'] = self.file_basename
                    log_dict['MESSAGE'] = 'Duplicated device %s was found.' % device
                    fluent = FluentSender(settings.SERVICE_CONFIGURATIONS['LOG_SERVER_HOSTNAME'],
                                          settings.SERVICE_CONFIGURATIONS['LOG_SERVER_PORT'], 'sa')
                    fluent.send(log_dict, 'sa.' + settings.SERVICE_CONFIGURATIONS['SERVER_TYPE'])
        if len(end_dt):
            self.end_date = datetime.datetime.fromtimestamp(max(end_dt)).astimezone(tz)
            self.save()

        for track_info in handle.get_track_info():
            if track_info[0] not in unknown_device and track_info[2] in (1, 6):
                try:
                    device = Device.objects.get(displayed_name=Device.map_device_alias(track_info[0]))
                except Device.DoesNotExist:
                    device = None
                if device is not None:
                    file_path = os.path.join(decompose_path, os.path.splitext(self.file_basename)[0] + '_%s_%s.npz' % (
                        device.code, track_info[1]))
                    file_path_media = os.path.join(settings.MEDIA_ROOT, file_path)
                    if not os.path.exists(os.path.join(settings.MEDIA_ROOT, decompose_path)):
                        os.makedirs(os.path.join(settings.MEDIA_ROOT, decompose_path))
                    dt, packet_pointer, val = handle.export_wave(track_info[0], track_info[1])
                    np.savez_compressed(file_path_media, timestamp=dt, packet_pointer=packet_pointer, val=val)
                    WaveInfoFile.objects.create(record=self, device=device, channel_name=track_info[1], file=file_path,
                                                num_packets=len(dt), sampling_rate=track_info[3])

        return

    def migrate_vital(self):

        self.decompose()
        self.load_number(reload=True)
        self.load_summary()

    def __str__(self):
        return self.file_path


class SummaryFileRecorded(models.Model):
    record = models.OneToOneField('FileRecorded', on_delete=models.CASCADE, primary_key=True)
    main_device = models.ForeignKey('Device', on_delete=models.CASCADE)
    bp_channel = models.CharField(max_length=64, null=True, blank=True)
    hr_channel = models.CharField(max_length=64, null=True, blank=True)
    cnt_total = models.IntegerField(default=0)
    cnt_bp = models.IntegerField(default=0)
    cnt_hr = models.IntegerField(default=0)
    cnt_bt = models.IntegerField(default=0)
    cnt_spo2 = models.IntegerField(default=0)
    min_sbp = SingleFloatField(null=True)
    max_sbp = SingleFloatField(null=True)
    avg_sbp = SingleFloatField(null=True)
    min_dbp = SingleFloatField(null=True)
    max_dbp = SingleFloatField(null=True)
    avg_dbp = SingleFloatField(null=True)
    min_mbp = SingleFloatField(null=True)
    max_mbp = SingleFloatField(null=True)
    avg_mbp = SingleFloatField(null=True)
    min_hr = SingleFloatField(null=True)
    max_hr = SingleFloatField(null=True)
    avg_hr = SingleFloatField(null=True)
    min_bt = SingleFloatField(null=True)
    max_bt = SingleFloatField(null=True)
    avg_bt = SingleFloatField(null=True)
    min_spo2 = SingleFloatField(null=True)
    max_spo2 = SingleFloatField(null=True)
    avg_spo2 = SingleFloatField(null=True)

    def __str__(self):
        return self.record.file_basename


class NumberInfoFile(models.Model):
    record = models.ForeignKey('FileRecorded', null=True, on_delete=models.CASCADE)
    device = models.ForeignKey('Device', null=True, on_delete=models.CASCADE)
    db_load = models.BooleanField(null=False, default=False)
    file = models.FileField(null=True)

    @staticmethod
    def smoothing_number(before_smoothing, timestamp, propotiontocut=0.05, windowsize=30, side=2, type='unixtime'):
        r = np.array(before_smoothing, dtype=np.float32)
        p_start = 0
        p_end = 0
        for i in range(len(r)):
            if type == 'unixtime':
                while timestamp[p_start] + windowsize <= timestamp[i]:
                    p_start += 1
            elif type == 'datetime':
                while timestamp[p_start] - timestamp[i] <= datetime.timedelta(seconds=-windowsize):
                    p_start += 1
            else:
                assert False, 'Unknown timestamp type.'
            if side == 1:
                r[i] = stats.trim_mean(before_smoothing[p_start:i + 1], propotiontocut)
            elif side == 2:
                if type == 'unixtime':
                    while timestamp[p_end] - windowsize <= timestamp[i] if p_end < len(r) else False:
                        p_end += 1
                elif type == 'datetime':
                    while timestamp[p_end] - timestamp[i] <= datetime.timedelta(seconds=windowsize) if p_end < len(r) else False:
                        p_end += 1
                else:
                    assert False, 'Unknown timestamp type.'

                r[i] = stats.trim_mean(before_smoothing[p_start:p_end], propotiontocut)
        return r

    def get_channel_info(self):
        db = MySQLdb.connect(host=settings.SERVICE_CONFIGURATIONS['DB_SERVER_HOSTNAME'],
                             user=settings.SERVICE_CONFIGURATIONS['DB_SERVER_USER'],
                             password=settings.SERVICE_CONFIGURATIONS['DB_SERVER_PASSWORD'],
                             db=settings.SERVICE_CONFIGURATIONS['DB_SERVER_DATABASE'])
        cursor = db.cursor()

        query = 'DESCRIBE %s' % self.device.db_table_name
        cursor.execute(query)
        rows = cursor.fetchall()

        column_info_db = list()
        for i, column in enumerate(rows):
            if column[0] != 'id':
                column_info_db.append(column[0])
        db.close()

        npz = np.load(self.file_path)
        col_list = np.array(npz['col_list'])

        col_dict = dict()
        unknown_columns = list()
        duplicated_columns = list()
        for i, col in enumerate(col_list):
            converted_col = FileRecorded.map_channel_name(self.device.displayed_name, col)
            if converted_col is not None:
                if converted_col not in col_dict.keys():
                    col_dict[converted_col] = i
                    if converted_col not in column_info_db:
                        unknown_columns.append(col)
                elif converted_col in ('ABP_SBP', 'ABP_MBP', 'ABP_DBP', 'ABP_HR'):
                    if col.startswith('ABP_'):
                        col_dict[converted_col] = i
                else:
                    duplicated_columns.append(col)
        return unknown_columns, duplicated_columns

    def load_number(self, reload=True, batch_size=1000):

        connection.connect()

        if self.device.db_table_name is None:
            log_dict = dict()
            log_dict['ACTION'] = 'LOAD_NUMBER'
            log_dict['FILE'] = self.file.name
            log_dict['MESSAGE'] = 'DB table for device %s does not exists.' % self.device.displayed_name
            fluent = FluentSender(settings.SERVICE_CONFIGURATIONS['LOG_SERVER_HOSTNAME'],
                                  settings.SERVICE_CONFIGURATIONS['LOG_SERVER_PORT'], 'sa')
            fluent.send(log_dict, 'sa.' + settings.SERVICE_CONFIGURATIONS['SERVER_TYPE'])
            return False

        if not os.path.exists(os.path.join(settings.MEDIA_ROOT, self.file.name)):
            log_dict = dict()
            log_dict['ACTION'] = 'LOAD_NUMBER'
            log_dict['FILE_PATH'] = self.file.name
            log_dict['MESSAGE'] = 'A decomposed number file does not exists.'
            fluent = FluentSender(settings.SERVICE_CONFIGURATIONS['LOG_SERVER_HOSTNAME'],
                                  settings.SERVICE_CONFIGURATIONS['LOG_SERVER_PORT'], 'sa')
            fluent.send(log_dict, 'sa.' + settings.SERVICE_CONFIGURATIONS['SERVER_TYPE'])
            return False

        with connection.cursor() as cursor:
            try:
                cursor.execute('DESCRIBE %s' % self.device.db_table_name)
                self.db_load = False
                self.save()
            except MySQLdb.Error as e:
                log_dict = dict()
                log_dict['ACTION'] = 'LOAD_NUMBER'
                log_dict['MESSAGE'] = 'An exception was raised during mysql query execution.'
                log_dict['EXCEPTION'] = str(e)
                fluent = FluentSender(settings.SERVICE_CONFIGURATIONS['LOG_SERVER_HOSTNAME'],
                                      settings.SERVICE_CONFIGURATIONS['LOG_SERVER_PORT'], 'sa')
                fluent.send(log_dict, 'sa.' + settings.SERVICE_CONFIGURATIONS['SERVER_TYPE'])
                return False
            except utils.OperationalError as e:
                log_dict = dict()
                log_dict['ACTION'] = 'LOAD_NUMBER'
                log_dict['MESSAGE'] = 'An exception was raised during mysql query execution.'
                log_dict['EXCEPTION'] = str(e)
                fluent = FluentSender(settings.SERVICE_CONFIGURATIONS['LOG_SERVER_HOSTNAME'],
                                      settings.SERVICE_CONFIGURATIONS['LOG_SERVER_PORT'], 'sa')
                fluent.send(log_dict, 'sa.' + settings.SERVICE_CONFIGURATIONS['SERVER_TYPE'])
                return False

            rows = cursor.fetchall()

            column_info_db = list()
            for i, column in enumerate(rows):
                if column[0] != 'id':
                    column_info_db.append(column[0])

            npz = np.load(os.path.join(settings.MEDIA_ROOT, self.file.name))
            timestamp = np.array(npz['timestamp'])
            number = np.array(npz['number'])
            col_list = np.array(npz['col_list'])

            col_dict = dict()
            unknown_columns = list()
            duplicated_columns = list()
            for i, col in enumerate(col_list):
                converted_col = FileRecorded.map_channel_name(self.device.displayed_name, col)
                if converted_col is not None:
                    if converted_col not in col_dict.keys():
                        col_dict[converted_col] = i
                        if converted_col not in column_info_db:
                            unknown_columns.append(col)
                    elif converted_col in ('ABP_SBP', 'ABP_MBP', 'ABP_DBP', 'ABP_HR'):
                        if col.startswith('ABP_'):
                            col_dict[converted_col] = i
                    else:
                        duplicated_columns.append(col)

            if reload:
                query = "DELETE FROM %s WHERE record_id=%d" % (self.device.db_table_name, self.record_id)
                cursor.execute(query)
                connection.commit()

            number = self.device.cleansing(timestamp, col_dict, number)

            query = "INSERT IGNORE INTO %s (%s) VALUES " % (self.device.db_table_name, ', '.join(column_info_db))

            current_row_count = 0

            for i in range(len(timestamp)):
                if current_row_count:
                    query += ','
                else:
                    query = "INSERT IGNORE INTO %s (%s) VALUES " % (self.device.db_table_name, ', '.join(column_info_db))
                query += "('%s'" % str(datetime.datetime.utcfromtimestamp(timestamp[i]))
                for col in column_info_db:
                    if col != 'dt':
                        if col == 'record_id':
                            query += ', %d' % self.record_id
                        elif col not in col_dict:
                            query += ', NULL'
                        elif np.isnan(number[i, col_dict[col]]) or number[i, col_dict[col]]==math.inf:
                            query += ', NULL'
                        else:
                            query += ', %f' % number[i, col_dict[col]]
                query += ")"
                current_row_count += 1
                if current_row_count == batch_size or i == len(timestamp)-1:
                    current_row_count = 0
                    try:
                        cursor.execute('SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0')
                        cursor.execute('SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0')
                        cursor.execute("SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO'")
                        cursor.execute('SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0')
                        cursor.execute('LOCK TABLES `%s` WRITE' % self.device.db_table_name)
                        cursor.execute(query)
                        connection.commit()
                        cursor.execute('UNLOCK TABLES')
                        cursor.execute('SET SQL_MODE=@OLD_SQL_MODE')
                        cursor.execute('SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS')
                        cursor.execute('SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS')
                        cursor.execute('SET SQL_NOTES=@OLD_SQL_NOTES')
                    except utils.OperationalError as e:
                        log_dict = dict()
                        log_dict['ACTION'] = 'LOAD_NUMBER'
                        log_dict['MESSAGE'] = 'An exception was raised during mysql query execution.'
                        log_dict['EXCEPTION'] = str(e)
                        fluent = FluentSender(settings.SERVICE_CONFIGURATIONS['LOG_SERVER_HOSTNAME'],
                                              settings.SERVICE_CONFIGURATIONS['LOG_SERVER_PORT'], 'sa')
                        fluent.send(log_dict, 'sa.' + settings.SERVICE_CONFIGURATIONS['SERVER_TYPE'])
                        return False
                    except MySQLdb.Error as e:
                        log_dict = dict()
                        log_dict['ACTION'] = 'LOAD_NUMBER'
                        log_dict['MESSAGE'] = 'An exception was raised during mysql query execution.'
                        log_dict['EXCEPTION'] = str(e)
                        fluent = FluentSender(settings.SERVICE_CONFIGURATIONS['LOG_SERVER_HOSTNAME'],
                                              settings.SERVICE_CONFIGURATIONS['LOG_SERVER_PORT'], 'sa')
                        fluent.send(log_dict, 'sa.' + settings.SERVICE_CONFIGURATIONS['SERVER_TYPE'])

            log_dict = dict()
            log_dict['SERVER_NAME'] = 'global' \
                if settings.SERVICE_CONFIGURATIONS['SERVER_TYPE'] == 'global' \
                else settings.SERVICE_CONFIGURATIONS['LOCAL_SERVER_NAME']
            log_dict['ACTION'] = 'LOAD_NUMBER'
            log_dict['TARGET_FILE_VITAL'] = self.record.file_basename
            log_dict['TARGET_FILE_DECOMPOSED'] = self.file.name
            log_dict['TARGET_DEVICE'] = self.device.displayed_name
            log_dict['NEW_CHANNEL'] = unknown_columns
            log_dict['DUPLICATED_CHANNEL'] = duplicated_columns
            log_dict['NUM_RECORDS_QUERY'] = len(npz['timestamp'])
            self.db_load = True
            self.save()
            fluent = FluentSender(settings.SERVICE_CONFIGURATIONS['LOG_SERVER_HOSTNAME'],
                                  settings.SERVICE_CONFIGURATIONS['LOG_SERVER_PORT'], 'sa')
            fluent.send(log_dict, 'sa.' + settings.SERVICE_CONFIGURATIONS['SERVER_TYPE'])

        return True

    def __str__(self):
        return '%s, %s' % (self.record.file_basename, self.device.displayed_name)

    class Meta:
        unique_together = ("record", "device")


class WaveInfoFile(models.Model):
    record = models.ForeignKey('FileRecorded', null=True, on_delete=models.CASCADE)
    device = models.ForeignKey('Device', null=True, on_delete=models.CASCADE)
    channel_name = models.CharField(max_length=64)
    file = models.FileField(null=True)
    sampling_rate = models.FloatField(null=True)
    num_packets = models.IntegerField(null=True)

    def __str__(self):
        return '%s, %s, %s' % (self.record.file_basename, self.device.displayed_name, self.channel_name)

    class Meta:
        unique_together = ("record", "device", "channel_name")


class NumberPIV(models.Model):
    record = models.ForeignKey('FileRecorded', on_delete=models.CASCADE)
    dt = models.DateTimeField()
    ABP_SBP = SingleFloatField(null=True)
    ABP_DBP = SingleFloatField(null=True)
    ABP_MBP = SingleFloatField(null=True)
    AOP_SBP = SingleFloatField(null=True)
    AOP_DBP = SingleFloatField(null=True)
    AOP_MBP = SingleFloatField(null=True)
    AWAY_RR = SingleFloatField(null=True)
    AWAY_TOT = SingleFloatField(null=True)
    AWAY_O2_INSP = SingleFloatField(null=True)
    BIS_BIS = SingleFloatField(null=True)
    BIS_EMG = SingleFloatField(null=True)
    BIS_SQI = SingleFloatField(null=True)
    BIS_SEF = SingleFloatField(null=True)
    BIS_SR = SingleFloatField(null=True)
    BT_BLD = SingleFloatField(null=True)
    BT_NASOPH = SingleFloatField(null=True)
    BT_RECT = SingleFloatField(null=True)
    BT_SKIN = SingleFloatField(null=True)
    CI = SingleFloatField(null=True)
    CO = SingleFloatField(null=True)
    CO2_ET = SingleFloatField(null=True)
    CO2_INSP_MIN = SingleFloatField(null=True)
    CPP = SingleFloatField(null=True)
    CVP_SBP = SingleFloatField(null=True)
    CVP_DBP = SingleFloatField(null=True)
    CVP_MBP = SingleFloatField(null=True)
    DESFL_INSP = SingleFloatField(null=True)
    DESFL_ET = SingleFloatField(null=True)
    ECG_HR = SingleFloatField(null=True)
    ECG_ST_I = SingleFloatField(null=True)
    ECG_ST_II = SingleFloatField(null=True)
    ECG_ST_III = SingleFloatField(null=True)
    ECG_ST_MCL = SingleFloatField(null=True)
    ECG_ST_V = SingleFloatField(null=True)
    ECG_ST_AVF = SingleFloatField(null=True)
    ECG_ST_AVL = SingleFloatField(null=True)
    ECG_ST_AVR = SingleFloatField(null=True)
    ECG_QT_GL = SingleFloatField(null=True)
    ECG_QT_HR = SingleFloatField(null=True)
    ECG_QTc = SingleFloatField(null=True)
    ECG_QTc_DELTA = SingleFloatField(null=True)
    ECG_VPC_CNT = SingleFloatField(null=True)
    ENFL_ET = SingleFloatField(null=True)
    ENFL_INSP = SingleFloatField(null=True)
    HAL_ET = SingleFloatField(null=True)
    HAL_INSP = SingleFloatField(null=True)
    HR = SingleFloatField(null=True)
    ICP_MBP = SingleFloatField(null=True)
    ISOFL_ET = SingleFloatField(null=True)
    ISOFL_INSP = SingleFloatField(null=True)
    LAP_MBP = SingleFloatField(null=True)
    LAP_DBP = SingleFloatField(null=True)
    LAP_SBP = SingleFloatField(null=True)
    N2O_ET = SingleFloatField(null=True)
    N2O_INSP = SingleFloatField(null=True)
    NIBP_HR = SingleFloatField(null=True)
    NIBP_SBP = SingleFloatField(null=True)
    NIBP_DBP = SingleFloatField(null=True)
    NIBP_MBP = SingleFloatField(null=True)
    O2_ET = SingleFloatField(null=True)
    O2_INSP = SingleFloatField(null=True)
    PAP_SBP = SingleFloatField(null=True)
    PAP_DBP = SingleFloatField(null=True)
    PAP_MBP = SingleFloatField(null=True)
    PLETH_PERF_REL = SingleFloatField(null=True)
    PLETH_HR = SingleFloatField(null=True)
    PLETH_SAT_O2 = SingleFloatField(null=True)
    PLAT_TIME = SingleFloatField(null=True)
    PPV = SingleFloatField(null=True)
    PTC_CNT = SingleFloatField(null=True)
    RAP_SBP = SingleFloatField(null=True)
    RAP_DBP = SingleFloatField(null=True)
    RAP_MBP = SingleFloatField(null=True)
    RISE_TIME = SingleFloatField(null=True)
    RR = SingleFloatField(null=True)
    REF = SingleFloatField(null=True)
    SET_SPEEP = SingleFloatField(null=True)
    SET_INSP_TIME = SingleFloatField(null=True)
    SEVOFL_ET = SingleFloatField(null=True)
    SEVOFL_INSP = SingleFloatField(null=True)
    SI = SingleFloatField(null=True)
    SV = SingleFloatField(null=True)
    SVV = SingleFloatField(null=True)
    TEMP = SingleFloatField(null=True)
    TEMP_ESOPH = SingleFloatField(null=True)
    TV_IN = SingleFloatField(null=True)
    TOF_RATIO = SingleFloatField(null=True)
    TOF_CNT = SingleFloatField(null=True)
    TOF_1 = SingleFloatField(null=True)
    TOF_2 = SingleFloatField(null=True)
    TOF_3 = SingleFloatField(null=True)
    TOF_4 = SingleFloatField(null=True)
    UA_MBP = SingleFloatField(null=True)
    UA_DBP = SingleFloatField(null=True)
    UA_SBP = SingleFloatField(null=True)

    class Meta:
        indexes = [
            models.Index(fields=['dt']),
        ]
        constraints = [
            models.UniqueConstraint(fields=['record', 'dt'], name='unique_piv'),
        ]
        db_table = 'number_piv'


class NumberGEC(models.Model):
    record = models.ForeignKey('FileRecorded', on_delete=models.CASCADE)
    dt = models.DateTimeField()
    ABP_SBP = SingleFloatField(null=True)
    ABP_DBP = SingleFloatField(null=True)
    ABP_MBP = SingleFloatField(null=True)
    ABP_HR = SingleFloatField(null=True)
    AGENT_ET = SingleFloatField(null=True)
    AGENT_FI = SingleFloatField(null=True)
    AGENT_IN = SingleFloatField(null=True)
    AGENT_MAC = SingleFloatField(null=True)
    ARRH_ECG_HR = SingleFloatField(null=True)
    BAL_GAS_ET = SingleFloatField(null=True)
    BIS_BIS = SingleFloatField(null=True)
    BIS_BSR = SingleFloatField(null=True)
    BIS_EMG = SingleFloatField(null=True)
    BIS_SQI = SingleFloatField(null=True)
    BT_AXIL = SingleFloatField(null=True)
    BT_PA = SingleFloatField(null=True)
    BT_ROOM = SingleFloatField(null=True)
    CO = SingleFloatField(null=True)
    COMPLIANCE = SingleFloatField(null=True)
    CO2_AMB_PRESS = SingleFloatField(null=True)
    CO2_ET = SingleFloatField(null=True)
    CO2_ET_PERCENT = SingleFloatField(null=True)
    CO2_FI = SingleFloatField(null=True)
    CO2_RR = SingleFloatField(null=True)
    CO2_IN = SingleFloatField(null=True)
    CO2_IN_PERCENT = SingleFloatField(null=True)
    CVP = SingleFloatField(null=True)
    ECG_HR = SingleFloatField(null=True)
    ECG_HR_ECG = SingleFloatField(null=True)
    ECG_HR_MAX = SingleFloatField(null=True)
    ECG_HR_MIN = SingleFloatField(null=True)
    ECG_IMP_RR = SingleFloatField(null=True)
    ECG_ST = SingleFloatField(null=True)
    ECG_ST_AVF = SingleFloatField(null=True)
    ECG_ST_AVL = SingleFloatField(null=True)
    ECG_ST_AVR = SingleFloatField(null=True)
    ECG_ST_I = SingleFloatField(null=True)
    ECG_ST_II = SingleFloatField(null=True)
    ECG_ST_III = SingleFloatField(null=True)
    ECG_ST_V = SingleFloatField(null=True)
    EEG_FEMG = SingleFloatField(null=True)
    ENT_BSR = SingleFloatField(null=True)
    ENT_EEG = SingleFloatField(null=True)
    ENT_EMG = SingleFloatField(null=True)
    ENT_RD_BSR = SingleFloatField(null=True)
    ENT_RD_EEG = SingleFloatField(null=True)
    ENT_RD_EMG = SingleFloatField(null=True)
    ENT_RE = SingleFloatField(null=True)
    ENT_SE = SingleFloatField(null=True)
    ENT_SR = SingleFloatField(null=True)
    EPEEP = SingleFloatField(null=True)
    FEM_SBP = SingleFloatField(null=True)
    FEM_DBP = SingleFloatField(null=True)
    FEM_MBP = SingleFloatField(null=True)
    FEM_HR = SingleFloatField(null=True)
    HR = SingleFloatField(null=True)
    ICP = SingleFloatField(null=True)
    IE_RATIO = SingleFloatField(null=True)
    LAP = SingleFloatField(null=True)
    MAC_AGE = SingleFloatField(null=True)
    MV = SingleFloatField(null=True)
    N2O_ET = SingleFloatField(null=True)
    N2O_FI = SingleFloatField(null=True)
    N2O_IN = SingleFloatField(null=True)
    NIBP_DBP = SingleFloatField(null=True)
    NIBP_SBP = SingleFloatField(null=True)
    NIBP_HR = SingleFloatField(null=True)
    NIBP_MBP = SingleFloatField(null=True)
    NMT_CURRENT = SingleFloatField(null=True)
    NMT_PTC_CNT = SingleFloatField(null=True)
    NMT_PULSE_WIDTH = SingleFloatField(null=True)
    NMT_T1 = SingleFloatField(null=True)
    NMT_T4_T1 = SingleFloatField(null=True)
    NMT_TOF_CNT = SingleFloatField(null=True)
    O2_ET = SingleFloatField(null=True)
    O2_FE = SingleFloatField(null=True)
    O2_FI = SingleFloatField(null=True)
    PA_SBP = SingleFloatField(null=True)
    PA_DBP = SingleFloatField(null=True)
    PA_MBP = SingleFloatField(null=True)
    PA_HR = SingleFloatField(null=True)
    PCWP = SingleFloatField(null=True)
    PEEP = SingleFloatField(null=True)
    PLETH_HR = SingleFloatField(null=True)
    PLETH_IRAMP = SingleFloatField(null=True)
    PLETH_SPO2 = SingleFloatField(null=True)
    PPEAK = SingleFloatField(null=True)
    PPLAT = SingleFloatField(null=True)
    PPV = SingleFloatField(null=True)
    RAP = SingleFloatField(null=True)
    RR = SingleFloatField(null=True)
    RR_VENT = SingleFloatField(null=True)
    RVEF = SingleFloatField(null=True)
    RVP = SingleFloatField(null=True)
    SPI = SingleFloatField(null=True)
    SPV = SingleFloatField(null=True)
    TOF_T1 = SingleFloatField(null=True)
    TOF_T2 = SingleFloatField(null=True)
    TOF_T3 = SingleFloatField(null=True)
    TOF_T4 = SingleFloatField(null=True)
    TV_EXP = SingleFloatField(null=True)
    TV_INSP = SingleFloatField(null=True)

    class Meta:
        indexes = [
            models.Index(fields=['dt']),
        ]
        constraints = [
            models.UniqueConstraint(fields=['record', 'dt'], name='unique_gec'),
        ]
        db_table = 'number_gec'


class NumberINV(models.Model):
    record = models.ForeignKey('FileRecorded', on_delete=models.CASCADE)
    dt = models.DateTimeField()
    AUC_L = SingleFloatField(null=True)
    AUC_R = SingleFloatField(null=True)
    BASELINE_L = SingleFloatField(null=True)
    BASELINE_R = SingleFloatField(null=True)
    SCO2_L = SingleFloatField(null=True)
    SCO2_R = SingleFloatField(null=True)
    SCO2_S1 = SingleFloatField(null=True)
    SCO2_S2 = SingleFloatField(null=True)
    rSO2_L = SingleFloatField(null=True)
    rSO2_R = SingleFloatField(null=True)

    class Meta:
        indexes = [
            models.Index(fields=['dt']),
        ]
        constraints = [
            models.UniqueConstraint(fields=['record', 'dt'], name='unique_inv'),
        ]
        db_table = 'number_inv'


class NumberVIG(models.Model):
    record = models.ForeignKey('FileRecorded', on_delete=models.CASCADE)
    dt = models.DateTimeField()
    ART_MBP = SingleFloatField(null=True)
    BT_PA = SingleFloatField(null=True)
    CI = SingleFloatField(null=True)
    CI_STAT = SingleFloatField(null=True)
    CO = SingleFloatField(null=True)
    CO_STAT = SingleFloatField(null=True)
    CVP = SingleFloatField(null=True)
    DO2 = SingleFloatField(null=True)
    EDV = SingleFloatField(null=True)
    EDVI = SingleFloatField(null=True)
    EDVI_STAT = SingleFloatField(null=True)
    EDV_STAT = SingleFloatField(null=True)
    ESV = SingleFloatField(null=True)
    ESVI = SingleFloatField(null=True)
    HR_AVG = SingleFloatField(null=True)
    ICI = SingleFloatField(null=True)
    ICI_AVG = SingleFloatField(null=True)
    ICO_AVG = SingleFloatField(null=True)
    O2EI = SingleFloatField(null=True)
    RVEF = SingleFloatField(null=True)
    RVEF_STAT = SingleFloatField(null=True)
    SAO2 = SingleFloatField(null=True)
    SCVO2 = SingleFloatField(null=True)
    SNR = SingleFloatField(null=True)
    SQI = SingleFloatField(null=True)
    SV = SingleFloatField(null=True)
    SVI = SingleFloatField(null=True)
    SVI_STAT = SingleFloatField(null=True)
    SVO2 = SingleFloatField(null=True)
    SVR = SingleFloatField(null=True)
    SVRI = SingleFloatField(null=True)
    SVV = SingleFloatField(null=True)
    SV_STAT = SingleFloatField(null=True)
    VO2 = SingleFloatField(null=True)

    class Meta:
        indexes = [
            models.Index(fields=['dt']),
        ]
        constraints = [
            models.UniqueConstraint(fields=['record', 'dt'], name='unique_vig'),
        ]
        db_table = 'number_vig'


class NumberDCQ(models.Model):
    record = models.ForeignKey('FileRecorded', on_delete=models.CASCADE)
    dt = models.DateTimeField()
    CI = SingleFloatField(null=True)
    CO = SingleFloatField(null=True)
    FTc = SingleFloatField(null=True)
    FTp = SingleFloatField(null=True)
    HR = SingleFloatField(null=True)
    MA = SingleFloatField(null=True)
    MD = SingleFloatField(null=True)
    PV = SingleFloatField(null=True)
    SD = SingleFloatField(null=True)
    SV = SingleFloatField(null=True)
    SVI = SingleFloatField(null=True)

    class Meta:
        indexes = [
            models.Index(fields=['dt']),
        ]
        constraints = [
            models.UniqueConstraint(fields=['record', 'dt'], name='unique_dcq'),
        ]
        db_table = 'number_dcq'


class NumberBIS(models.Model):
    record = models.ForeignKey('FileRecorded', on_delete=models.CASCADE)
    dt = models.DateTimeField()
    BIS = SingleFloatField(null=True)
    EMG = SingleFloatField(null=True)
    SR = SingleFloatField(null=True)
    SEF = SingleFloatField(null=True)
    SQI = SingleFloatField(null=True)
    TOTPOW = SingleFloatField(null=True)

    class Meta:
        indexes = [
            models.Index(fields=['dt']),
        ]
        constraints = [
            models.UniqueConstraint(fields=['record', 'dt'], name='unique_bis'),
        ]
        db_table = 'number_bis'


class NumberEEV(models.Model):
    record = models.ForeignKey('FileRecorded', on_delete=models.CASCADE)
    dt = models.DateTimeField()
    ADBP = SingleFloatField(null=True)
    ART_MBP = SingleFloatField(null=True)
    ART_MBP_INT = SingleFloatField(null=True)
    ASBP = SingleFloatField(null=True)
    BT_INT = SingleFloatField(null=True)
    BT_PA = SingleFloatField(null=True)
    CDBP = SingleFloatField(null=True)
    CFI_INT = SingleFloatField(null=True)
    CI = SingleFloatField(null=True)
    CI_STAT = SingleFloatField(null=True)
    CMBP = SingleFloatField(null=True)
    CO = SingleFloatField(null=True)
    CO_STAT = SingleFloatField(null=True)
    CSBP = SingleFloatField(null=True)
    CVP = SingleFloatField(null=True)
    CVP_INT = SingleFloatField(null=True)
    DO2 = SingleFloatField(null=True)
    EDV = SingleFloatField(null=True)
    EDVI = SingleFloatField(null=True)
    EDVI_INT = SingleFloatField(null=True)
    EDVI_STAT = SingleFloatField(null=True)
    EDV_INT = SingleFloatField(null=True)
    EDV_STAT = SingleFloatField(null=True)
    EF_INT = SingleFloatField(null=True)
    ESV = SingleFloatField(null=True)
    ESVI = SingleFloatField(null=True)
    EVLWI_INT = SingleFloatField(null=True)
    EVLW_INT = SingleFloatField(null=True)
    HR = SingleFloatField(null=True)
    HR_AVG = SingleFloatField(null=True)
    HR_INT = SingleFloatField(null=True)
    ICI = SingleFloatField(null=True)
    ICI_AVG = SingleFloatField(null=True)
    ICO = SingleFloatField(null=True)
    ICO_AVG = SingleFloatField(null=True)
    INPUT_HB = SingleFloatField(null=True)
    INPUT_SPO2 = SingleFloatField(null=True)
    ITBVI_INT = SingleFloatField(null=True)
    ITBV_INT = SingleFloatField(null=True)
    O2EI = SingleFloatField(null=True)
    RVEF = SingleFloatField(null=True)
    RVEF_STAT = SingleFloatField(null=True)
    SAO2 = SingleFloatField(null=True)
    SCVO2 = SingleFloatField(null=True)
    SNR = SingleFloatField(null=True)
    SQI = SingleFloatField(null=True)
    SV = SingleFloatField(null=True)
    SVI = SingleFloatField(null=True)
    SVI_STAT = SingleFloatField(null=True)
    SVO2 = SingleFloatField(null=True)
    SVR = SingleFloatField(null=True)
    SVRI = SingleFloatField(null=True)
    SVV = SingleFloatField(null=True)
    SV_STAT = SingleFloatField(null=True)
    VO2 = SingleFloatField(null=True)
    VO2I_INT = SingleFloatField(null=True)

    class Meta:
        indexes = [
            models.Index(fields=['dt']),
        ]
        constraints = [
            models.UniqueConstraint(fields=['record', 'dt'], name='unique_eev'),
        ]
        db_table = 'number_eev'


class NumberMRT(models.Model):
    record = models.ForeignKey('FileRecorded', on_delete=models.CASCADE)
    dt = models.DateTimeField()
    ARTF = SingleFloatField(null=True)
    EMG = SingleFloatField(null=True)
    PSI = SingleFloatField(null=True)
    SEFL = SingleFloatField(null=True)
    SEFR = SingleFloatField(null=True)
    SR = SingleFloatField(null=True)

    class Meta:
        indexes = [
            models.Index(fields=['dt']),
        ]
        constraints = [
            models.UniqueConstraint(fields=['record', 'dt'], name='unique_mrt'),
        ]
        db_table = 'number_mrt'


class NumberPRM(models.Model):
    record = models.ForeignKey('FileRecorded', on_delete=models.CASCADE)
    dt = models.DateTimeField()
    ART_MBP = SingleFloatField(null=True)
    CI = SingleFloatField(null=True)
    CO = SingleFloatField(null=True)
    COMPLIANCE = SingleFloatField(null=True)
    CONSUMPTION_AIR = SingleFloatField(null=True)
    CONSUMPTION_DES = SingleFloatField(null=True)
    CONSUMPTION_ENF = SingleFloatField(null=True)
    CONSUMPTION_HALO = SingleFloatField(null=True)
    CONSUMPTION_ISO = SingleFloatField(null=True)
    CONSUMPTION_N2O = SingleFloatField(null=True)
    CONSUMPTION_O2 = SingleFloatField(null=True)
    CONSUMPTION_SEVO = SingleFloatField(null=True)
    ETCO2 = SingleFloatField(null=True)
    ETCO2_KPA = SingleFloatField(null=True)
    ETCO2_PERCENT = SingleFloatField(null=True)
    EXP_DES = SingleFloatField(null=True)
    EXP_ENF = SingleFloatField(null=True)
    EXP_HALO = SingleFloatField(null=True)
    EXP_ISO = SingleFloatField(null=True)
    EXP_SEVO = SingleFloatField(null=True)
    FEN2O = SingleFloatField(null=True)
    FEO2 = SingleFloatField(null=True)
    FIN2O = SingleFloatField(null=True)
    FIO2 = SingleFloatField(null=True)
    FLOW_AIR = SingleFloatField(null=True)
    FLOW_N2O = SingleFloatField(null=True)
    FLOW_O2 = SingleFloatField(null=True)
    GAS2_EXPIRED = SingleFloatField(null=True)
    INCO2 = SingleFloatField(null=True)
    INCO2_KPA = SingleFloatField(null=True)
    INCO2_PERCENT = SingleFloatField(null=True)
    INSP_DES = SingleFloatField(null=True)
    INSP_ENF = SingleFloatField(null=True)
    INSP_HALO = SingleFloatField(null=True)
    INSP_ISO = SingleFloatField(null=True)
    INSP_SEVO = SingleFloatField(null=True)
    MAC = SingleFloatField(null=True)
    MAWP_MBAR = SingleFloatField(null=True)
    MV = SingleFloatField(null=True)
    MV_SPONT = SingleFloatField(null=True)
    NIBP_DBP = SingleFloatField(null=True)
    NIBP_MBP = SingleFloatField(null=True)
    NIBP_SBP = SingleFloatField(null=True)
    PAMB_MBAR = SingleFloatField(null=True)
    PEEP_MBAR = SingleFloatField(null=True)
    PIP_MBAR = SingleFloatField(null=True)
    PLETH_SPO2 = SingleFloatField(null=True)
    PPLAT_MBAR = SingleFloatField(null=True)
    RESISTANCE = SingleFloatField(null=True)
    RR_CO2 = SingleFloatField(null=True)
    RR_MANDATORY = SingleFloatField(null=True)
    RR_SPONT = SingleFloatField(null=True)
    RR_VF = SingleFloatField(null=True)
    RVSWI = SingleFloatField(null=True)
    SET_EXP_AGENT = SingleFloatField(null=True)
    SET_EXP_ENF = SingleFloatField(null=True)
    SET_EXP_HALO = SingleFloatField(null=True)
    SET_EXP_SEVO = SingleFloatField(null=True)
    SET_EXP_TM = SingleFloatField(null=True)
    SET_FIO2 = SingleFloatField(null=True)
    SET_FLOW_TRIG = SingleFloatField(null=True)
    SET_FRESH_AGENT = SingleFloatField(null=True)
    SET_FRESH_DES = SingleFloatField(null=True)
    SET_FRESH_ENF = SingleFloatField(null=True)
    SET_FRESH_FLOW = SingleFloatField(null=True)
    SET_FRESH_HALO = SingleFloatField(null=True)
    SET_FRESH_ISO = SingleFloatField(null=True)
    SET_FRESH_O2 = SingleFloatField(null=True)
    SET_IE_E = SingleFloatField(null=True)
    SET_IE_I = SingleFloatField(null=True)
    SET_INSP_PAUSE = SingleFloatField(null=True)
    SET_INSP_PRES = SingleFloatField(null=True)
    SET_INSP_TM = SingleFloatField(null=True)
    SET_INTER_PEEP = SingleFloatField(null=True)
    SET_PEEP = SingleFloatField(null=True)
    SET_PIP = SingleFloatField(null=True)
    SET_RR_IPPV = SingleFloatField(null=True)
    SET_SUPP_PRES = SingleFloatField(null=True)
    SET_TV = SingleFloatField(null=True)
    SET_TV_L = SingleFloatField(null=True)
    ST_AVF = SingleFloatField(null=True)
    ST_AVR = SingleFloatField(null=True)
    ST_I = SingleFloatField(null=True)
    ST_II = SingleFloatField(null=True)
    ST_III = SingleFloatField(null=True)
    ST_V5 = SingleFloatField(null=True)
    ST_VPLUS = SingleFloatField(null=True)
    SUPPLY_PRESSURE_O2 = SingleFloatField(null=True)
    SV = SingleFloatField(null=True)
    SVR = SingleFloatField(null=True)
    TV = SingleFloatField(null=True)
    TV_MANDATORY = SingleFloatField(null=True)
    VENT_LEAK = SingleFloatField(null=True)

    class Meta:
        indexes = [
            models.Index(fields=['dt']),
        ]
        constraints = [
            models.UniqueConstraint(fields=['record', 'dt'], name='unique_prm'),
        ]
        db_table = 'number_prm'


class ClientBusSlot(models.Model):
    client = models.ForeignKey('Client', on_delete=models.CASCADE, null=True)
    name = models.CharField(max_length=64)
    bus = models.CharField(max_length=64, blank=True, null=True)
    device = models.ForeignKey('Device', on_delete=models.SET_NULL, blank=True, null=True)
    active = models.BooleanField(default=True)

    def __str__(self):  # __str__ on Python 3
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


class Annotation(models.Model):
    dt = models.DateTimeField(default=timezone.now)
    dt_end = models.DateTimeField(null=True)
    record = models.ForeignKey('FileRecorded', on_delete=models.SET_NULL, null=True)
    bed = models.ForeignKey('Bed', on_delete=models.SET_NULL, null=True)
    ANNOTATION_METHOD_CHOICES = (
        (0, "offline"),
        (1, "online"),
        (2, "api"),
        (3, "migration"),
    )
    method = models.IntegerField(choices=ANNOTATION_METHOD_CHOICES, default=0)
    category_1 = models.CharField(max_length=255, null=True)
    category_2 = models.CharField(max_length=255, null=True)
    description = models.CharField(max_length=255, blank=True, null=True)


class AnnotationComment(models.Model):
    dt = models.DateTimeField(auto_now_add=True)
    annotation = models.ForeignKey('Annotation', on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    comment = models.CharField(max_length=255, blank=True, null=True)


class AnnotationLike(models.Model):
    annotation = models.ForeignKey('Annotation', on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    ANNOTATION_LIKE_CHOICES = (
        (0, "offline"),
        (1, "agree"),
        (2, "disagree"),
    )
    like = models.IntegerField(choices=ANNOTATION_LIKE_CHOICES, default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['annotation', 'user'], name='unique_like'),
        ]
