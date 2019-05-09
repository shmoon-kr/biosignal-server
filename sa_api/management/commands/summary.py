import datetime
import argparse
import pytz
from django.conf import settings
from django.core.management.base import BaseCommand
from sa_api.models import FileRecorded
from sa_api.views import db_upload_summary
from django.utils import timezone

tz = pytz.timezone(settings.TIME_ZONE)

def valid_date_type(arg_date_str):
    """custom argparse *date* type for user dates values given from the command line"""
    try:
        return datetime.datetime.strptime(arg_date_str, "%Y-%m-%d").astimezone(tz)
    except ValueError:
        msg = "Given Date ({0}) not valid! Expected format, YYYY-MM-DD!".format(arg_date_str)
        raise argparse.ArgumentTypeError(msg)


class Command(BaseCommand):
    help = 'Summarize recorded files.'

    def add_arguments(self, parser):
        parser.add_argument('date', type=valid_date_type, help='Indicates the date which should be processed.')

    def handle(self, *args, **kwargs):
        dt_start = kwargs['date']
        dt_end = dt_start + datetime.timedelta(days=1)
        record_all = FileRecorded.objects.filter(begin_date__range=(dt_start, dt_end))

        for record in record_all:
            db_upload_summary(record)

        return


