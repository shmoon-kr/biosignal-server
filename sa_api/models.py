from django.db import models, connection
from django.utils import timezone
from django.utils.html import format_html
from django.conf import settings
from django.core.files.storage import FileSystemStorage
from pyfluent.client import FluentSender
from itertools import product
import re
import os
import datetime
import pytz
import MySQLdb
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
                'ART_HR': 'HR',
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

        agg_list = ('MIN', 'MAX', 'AVG', 'COUNT')

        table_col_list = dict()
        table_col_list['summary_by_file'] = ['ECG_HR', 'TEMP', 'NIBP_SBP', 'NIBP_DBP', 'NIBP_MBP', 'PLETH_SPO2']
        table_col_list['Philips/IntelliVue'] = ['ECG_HR', 'TEMP', 'NIBP_SBP', 'NIBP_DBP', 'NIBP_MBP', 'PLETH_SAT_O2']
        table_col_list['GE/Carescape'] = ['ECG_HR', 'BT', 'NIBP_SBP', 'NIBP_DBP', 'NIBP_MBP', 'PLETH_SPO2']

        table_val_list = dict()
        table_val_list['summary_by_file'] = product(table_col_list['summary_by_file'], agg_list)
        table_val_list['Philips/IntelliVue'] = product(table_col_list['Philips/IntelliVue'], agg_list)
        table_val_list['GE/Carescape'] = product(table_col_list['GE/Carescape'], agg_list)

        db = MySQLdb.connect(host=settings.SERVICE_CONFIGURATIONS['DB_SERVER_HOSTNAME'],
                             user=settings.SERVICE_CONFIGURATIONS['DB_SERVER_USER'],
                             password=settings.SERVICE_CONFIGURATIONS['DB_SERVER_PASSWORD'],
                             db=settings.SERVICE_CONFIGURATIONS['DB_SERVER_DATABASE'])
        cursor = db.cursor()

        main_devices = Device.objects.filter(is_main=True, db_table_name__isnull=False)

        for device in main_devices:  # device_displayed_name, table
            field_list = list()
            for val in table_val_list[device.displayed_name]:
                field_list.append('%s(%s) %s_%s' % (val[1], val[0], val[0], val[1]))

            query = 'SELECT COUNT(*) TOTAL_COUNT, %s' % ', '.join(field_list)
            query += " FROM %s WHERE rosette = '%s' AND bed = '%s' AND" % (
                device.db_table_name, self.bed.room.name, self.bed.name)
            query += " dt BETWEEN '%s' and '%s'" % (self.begin_date.astimezone(tz).replace(tzinfo=None),
                                                    self.end_date.astimezone(tz).replace(tzinfo=None))

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
                value_list.append("'%s'" % device.displayed_name)
                value_list.append("'%s'" % os.path.basename(self.file_path))
                value_list.append("'%s'" % self.bed.room.name)
                value_list.append("'%s'" % self.bed.name)
                value_list.append("'%s'" % str(self.begin_date.astimezone(tz).replace(tzinfo=None)))
                value_list.append("'%s'" % str(self.end_date.astimezone(tz).replace(tzinfo=None)))
                value_list.append('1' if self.end_date - self.begin_date > datetime.timedelta(minutes=10) else '0')
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
                    log_dict['ACTION'] = 'LOAD_SUMMARY'
                    log_dict['FILE_NAME'] = self.file_basename
                    log_dict['MESSAGE'] = 'An exception was raised during mysql query execution.'
                    log_dict['EXCEPTION'] = str(e)
                    fluent = FluentSender(settings.SERVICE_CONFIGURATIONS['LOG_SERVER_HOSTNAME'],
                                          settings.SERVICE_CONFIGURATIONS['LOG_SERVER_PORT'], 'sa')
                    fluent.send(log_dict, 'sa.' + settings.SERVICE_CONFIGURATIONS['SERVER_TYPE'])
                    return

        db.close()
        return

    def load_number(self, reload=False):

        for ni in NumberInfoFile.objects.filter(record=self):
            try:
                ni.load_number(reload)
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
        os.makedirs(decompose_path, mode=0o775, exist_ok=True)

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

        # dt_datetime = np.dtype(datetime.datetime)
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
                if not os.path.exists(decompose_path):
                    os.makedirs(decompose_path)
                file_path = os.path.join(decompose_path,
                                         os.path.splitext(self.file_basename)[0] + '_%s.npz' % device.code)
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
                    device = Device.objects.get(displayed_name=Device.map_device_alias(track_info[0]))
                except Device.DoesNotExist:
                    device = None
                if device is not None:
                    file_path = os.path.join(decompose_path, os.path.splitext(self.file_basename)[0] + '_%s_%s.npz' % (
                        device.code, track_info[1]))
                    if not os.path.exists(decompose_path):
                        os.makedirs(decompose_path)
                    dt, packet_pointer, val = handle.export_wave(track_info[0], track_info[1])
                    np.savez_compressed(file_path, timestamp=dt, packet_pointer=packet_pointer, val=val)

                    WaveInfoFile.objects.create(record=self, device=device, channel_name=track_info[1],
                                                file_path=file_path, num_packets=len(dt), sampling_rate=track_info[3])

        return

    def migrate_vital(self):

        self.decompose()
        if settings.SERVICE_CONFIGURATIONS['DB_SERVER']:
            try:
                self.load_number(reload=True)
                self.load_summary()
            except Exception as e:
                pass

    def __str__(self):
        return self.file_path


class NumberInfoFile(models.Model):
    record = models.ForeignKey('FileRecorded', null=True, on_delete=models.CASCADE)
    device = models.ForeignKey('Device', null=True, on_delete=models.CASCADE)
    file_path = models.CharField(max_length=256, blank=True)

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

    def load_number(self, reload=False):

        connection.connect()

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

        npz = np.load(self.file_path)
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
            query = "DELETE FROM %s WHERE rosette='%s' AND bed='%s' AND dt BETWEEN '%s' AND '%s'" % (
                self.device.db_table_name, self.record.bed.room.name, self.record.bed.name,
                self.record.begin_date.astimezone(tz).replace(tzinfo=None),
                self.record.end_date.astimezone(tz).replace(tzinfo=None))
            cursor.execute(query)
            db.commit()

        query = "INSERT IGNORE INTO %s (%s) VALUES " % (self.device.db_table_name, ', '.join(column_info_db))

        for i in range(len(timestamp)):
            if i:
                query += ','
            query += "(0, '%s', '%s', '%s'" % (
                self.record.bed.room.name, self.record.bed.name, str(datetime.datetime.fromtimestamp(timestamp[i])))
            for col in column_info_db:
                if col not in ('method', 'rosette', 'bed', 'dt'):
                    if col not in col_dict:
                        query += ', NULL'
                    elif np.isnan(number[i, col_dict[col]]):
                        query += ', NULL'
                    else:
                        query += ', %f' % number[i, col_dict[col]]
            query += ")"

        log_dict = dict()
        log_dict['SERVER_NAME'] = 'global' \
            if settings.SERVICE_CONFIGURATIONS['SERVER_TYPE'] == 'global' \
            else settings.SERVICE_CONFIGURATIONS['LOCAL_SERVER_NAME']
        log_dict['ACTION'] = 'LOAD_NUMBER'
        log_dict['TARGET_FILE_VITAL'] = self.record.file_basename
        log_dict['TARGET_FILE_DECOMPOSED'] = self.file_path
        log_dict['TARGET_DEVICE'] = self.device.displayed_name
        log_dict['NEW_CHANNEL'] = unknown_columns
        log_dict['DUPLICATED_CHANNEL'] = duplicated_columns
        log_dict['NUM_RECORDS_QUERY'] = len(npz['timestamp'])
        insert_start = datetime.datetime.now()

        try:
            cursor.execute(query)
            db.commit()

            db_upload_execution_time = datetime.datetime.now() - insert_start

            log_dict['NUM_RECORDS_AFFECTED'] = cursor.rowcount
            log_dict['DB_EXECUTION_TIME'] = str(db_upload_execution_time)

            fluent = FluentSender(settings.SERVICE_CONFIGURATIONS['LOG_SERVER_HOSTNAME'],
                                  settings.SERVICE_CONFIGURATIONS['LOG_SERVER_PORT'], 'sa')
            fluent.send(log_dict, 'sa.' + settings.SERVICE_CONFIGURATIONS['SERVER_TYPE'])

        except MySQLdb.Error as e:
            log_dict['ACTION'] = 'LOAD_NUMBER'
            log_dict['MESSAGE'] = 'An exception was raised during mysql query execution.'
            log_dict['EXCEPTION'] = str(e)
            fluent = FluentSender(settings.SERVICE_CONFIGURATIONS['LOG_SERVER_HOSTNAME'],
                                  settings.SERVICE_CONFIGURATIONS['LOG_SERVER_PORT'], 'sa')
            fluent.send(log_dict, 'sa.' + settings.SERVICE_CONFIGURATIONS['SERVER_TYPE'])

        db.close()
        return True

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


class ManualInputEventItem(models.Model):
    dt = models.DateTimeField(default=timezone.now)
    record = models.ForeignKey('ManualInputEvent', on_delete=models.CASCADE)
    category = models.CharField(max_length=255, blank=True, null=True, default='Manual')
    description = models.CharField(max_length=255, blank=True, null=True)


class ManualInputEvent(models.Model):
    dt_operation = models.DateField(default=timezone.now)
    bed = models.ForeignKey('Bed', on_delete=models.CASCADE)
