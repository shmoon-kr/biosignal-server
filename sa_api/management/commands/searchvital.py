import datetime
import argparse
import pytz
import re
from os import listdir, rename
from os.path import isdir, isfile, join, basename
from django.conf import settings
from django.core.management.base import BaseCommand
from sa_api.models import FileRecorded, Client, Bed
from sa_api.views import search_vital_files
from pathos.multiprocessing import ProcessingPool as Pool

tz = pytz.timezone(settings.TIME_ZONE)

beds_migration = (
    'B-01', 'B-02', 'B-03', 'B-04', 'C-01', 'C-02', 'C-03', 'C-04', 'C-05', 'C-06',
    'D-01', 'D-02', 'D-03', 'D-04', 'D-05', 'D-06', 'Y-01', 'OB-01', 'OB-02',
    'E-01', 'E-02', 'E-03', 'E-04', 'E-05', 'E-06', 'E-07', 'E-08', 'E-09', 'E-10',
    'F-01', 'F-02', 'F-03', 'F-04', 'F-05', 'F-06', 'F-07', 'F-08', 'F-09', 'F-10',
    'G-01', 'G-02', 'G-03', 'G-04', 'G-05', 'G-06',
    'H-01', 'H-02', 'H-03', 'H-04', 'H-05', 'H-06', 'H-07', 'H-08', 'H-09',
    'I-01', 'I-02', 'I-03', 'I-04', 'J-01', 'J-02', 'J-03', 'J-04', 'J-05', 'J-06',
    'K-01', 'K-02', 'K-03', 'K-04', 'K-05', 'K-06', 'IPACU-01', 'IPACU-02',
    'PICU1-01', 'PICU1-02', 'PICU1-03', 'PICU1-04', 'PICU1-05', 'PICU1-06',
    'PICU1-07', 'PICU1-08', 'PICU1-09', 'PICU1-10', 'PICU1-11',
    'WREC-01', 'WREC-02', 'WREC-03', 'WREC-04', 'WREC-05', 'WREC-06', 'WREC-07', 'WREC-08', 'WREC-09', 'WREC-10',
    'WREC-11', 'WREC-12', 'WREC-13', 'WREC-14', 'WREC-15', 'EREC-01', 'EREC-02', 'EREC-03', 'EREC-04', 'EREC-05',
    'EREC-06', 'EREC-07', 'EREC-08', 'EREC-09', 'EREC-10', 'EREC-11', 'EREC-12', 'EREC-13', 'EREC-14', 'EREC-15',
    'EREC-16', 'EREC-17', 'EREC-18', 'EREC-19', 'NREC-01', 'NREC-02', 'NREC-03', 'NREC-04', 'NREC-05', 'NREC-06',
    'NREC-07', 'NREC-08', 'NREC-09', 'NREC-10', 'NREC-11', 'NREC-12', 'NREC-13', 'NREC-14', 'NREC-15', 'NREC-16'
)


def valid_date_type(arg_date_str):
    """custom argparse *date* type for user dates values given from the command line"""
    try:
        return datetime.datetime.strptime(arg_date_str, "%Y-%m-%d").astimezone(tz)
    except ValueError:
        msg = "Given Date ({0}) not valid! Expected format, YYYY-MM-DD!".format(arg_date_str)
        raise argparse.ArgumentTypeError(msg)


class Command(BaseCommand):
    help = 'Search vital files.'

    def add_arguments(self, parser):
        # Named (optional) arguments
        parser.add_argument(
            '--reload',
            action='store_true',
            help='Reload existing data.',
        )
        parser.add_argument(
            '--thread',
            action='store',
            help='Number of threads used in searching.',
        )

    def handle(self, *args, **options):

        client = Client.objects.get(name='Vital Recorder')
        records = FileRecorded.objects.all()
        d_records = dict()

        for record in records:
            d_records[record.file_basename] = record

        data_root = settings.SERVICE_CONFIGURATIONS['LOCAL_SERVER_DATAPATH']
        targets = list()

        dt_re = re.compile('[0-9]{6}')

        for bed_name in beds_migration:
            bed = Bed.objects.get(name=bed_name)
            if isdir(join(data_root, bed_name)):
                for dt in listdir(join(data_root, bed_name)):
                    if dt_re.match(dt) and isdir(join(data_root, bed_name, dt)):
                        file_re = re.compile(bed_name + '_' + dt + '_[0-9]{6}.vital')
                        for file in listdir(join(data_root, bed_name, dt)):
                            if isfile(join(data_root, bed_name, dt, file)):
                                if file_re.match(file):
                                    if file not in d_records.keys():
                                        record = FileRecorded.objects.create(
                                            file_basename=file, client=client, bed=bed,
                                            begin_date=datetime.datetime.strptime(file[-19:], '%y%m%d_%H%M%S.vital').astimezone(tz),
                                            end_date=None, file_path=join(data_root, bed_name, dt, file), method=1)
                                        targets.append(record)
                                    elif options['reload']:
                                        targets.append(d_records[file])

        with Pool(1 if options['thread'] is None else int(options['thread'])) as p:
            p.map(FileRecorded.migrate_vital, targets)

        return
