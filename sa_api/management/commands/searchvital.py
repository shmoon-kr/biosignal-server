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
    'B-01', 'B-02', 'B-03', 'B-04', 'C-01', 'C-02', 'C-03', 'C-04', 'C-06'
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

        for record in search_vital_files(beds_migration):
            record.decompose()

        return
