import datetime
import argparse
import pytz
from django.conf import settings
from django.core.management.base import BaseCommand
from sa_api.models import FileRecorded
from sa_api.views import search_vital_files
from pathos.multiprocessing import ProcessingPool as Pool


tz = pytz.timezone(settings.TIME_ZONE)
beds_migration = (
    'B-01', 'B-02', 'B-03', 'B-04', 'C-01', 'C-02', 'C-03', 'C-04', 'C-06',
    'E-01', 'E-02', 'E-03', 'E-04', 'E-05', 'E-06', 'E-07', 'E-08', 'E-09', 'E-10',
    'F-01', 'F-02', 'F-03', 'F-05', 'F-06', 'F-07', 'F-08', 'F-09', 'F-10',
    'G-01', 'G-02', 'G-03', 'G-04', 'G-05', 'G-06', 'H-02', 'H-04', 'H-05', 'H-07'
    'I-01', 'I-02', 'I-03', 'I-04', 'J-03', 'K-01', 'K-02', 'K-03', 'K-04', 'K-05', 'K-06'
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

    def handle(self, *args, **kwargs):

        with Pool(4) as p:
            p.map(FileRecorded.migrate_vital, search_vital_files(beds_migration))

        return
