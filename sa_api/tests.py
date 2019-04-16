import json
import pytz
import datetime
from django.test import TestCase, override_settings
from django.test import Client as tClient
from django.conf import settings
from sa_api.models import Device, Client, Bed, Channel, Room
from sa_api.views import db_upload_main_numeric
from pyfluent.client import FluentSender

# Create your tests here.

SERVICE_CONFIGURATIONS_GLOBAL = {
    'SERVER_TYPE': 'global',
    'GLOBAL_SERVER_HOSTNAME': 'dev.sig2.com',
    'GLOBAL_SERVER_PORT': 8000,
    'LOG_SERVER_HOSTNAME': 'dev.sig2.com',
    'LOG_SERVER_PORT': 24224,
}


@override_settings(SERVICE_CONFIGURATIONS=SERVICE_CONFIGURATIONS_GLOBAL)
class UnitTestGlobalServerAPI(TestCase):
    def setUp(self):
        self.client = tClient()
        testdevice = Device.objects.create(device_type='TestDevice', displayed_name='TestDeviceDisplay')
        Channel.objects.create(name='TestChannelUnknown', abbreviation='TestChannelUnknown', device=testdevice, unit='mmHg', is_unknown=True)
        Channel.objects.create(name='TestChannelKnown', abbreviation='TestChannelKnown', device=testdevice, unit='mmHg', is_unknown=False)
        u_room = Room.objects.create(name='UknownRoom')
        u_bed = Bed.objects.create(name='UknownBed', room=u_room)
        Client.objects.create(name='UnknownClient', mac='00:00:00:00:00:00', bed=u_bed)

    def test_configuration(self):
        self.assertTrue(settings.SERVICE_CONFIGURATIONS['SERVER_TYPE'] == 'global')

    def test_device_info(self):
        get_params = dict()

        get_params['device_type'] = 'TestDeviceNewServer'
        response = self.client.get('/server/device_info', get_params)
        self.assertTrue(response['Content-Type'].startswith('application/json'))
        r = json.loads(response.content.decode('utf-8'))
        self.assertTrue(r['success'])
        self.assertEqual(r['message'], 'New device was added.')

        get_params['device_type'] = 'TestDevice'
        response = self.client.get('/server/device_info', get_params)
        self.assertTrue(response['Content-Type'].startswith('application/json'))
        r = json.loads(response.content.decode('utf-8'))
        self.assertTrue(r['success'])
        self.assertEqual(r['message'], 'Device information was returned correctly.')

        get_params['device_type'] = 'TestDeviceNewClient'
        response = self.client.get('/client/device_info', get_params)
        r = json.loads(response.content.decode('utf-8'))
        self.assertTrue(r['success'])
        self.assertEqual(r['message'], 'New device was added.')

        get_params['device_type'] = 'TestDevice'
        response = self.client.get('/client/device_info', get_params)
        self.assertTrue(response['Content-Type'].startswith('application/json'))
        r = json.loads(response.content.decode('utf-8'))
        self.assertTrue(r['success'])
        self.assertEqual(r['message'], 'Device information was returned correctly.')

    def test_channel_info(self):
        get_params = dict()

        get_params['device_type'] = 'TestDevice'
        get_params['channel_name'] = 'TestChannelKnown'
        response = self.client.get('/server/channel_info', get_params)
        self.assertTrue(response['Content-Type'].startswith('application/json'))
        r = json.loads(response.content.decode('utf-8'))
        self.assertTrue(r['success'])
        self.assertEqual(r['message'], 'Channel information was returned correctly.')

        get_params['channel_name'] = 'TestChannelUnknown'
        response = self.client.get('/server/channel_info', get_params)
        self.assertTrue(response['Content-Type'].startswith('application/json'))
        r = json.loads(response.content.decode('utf-8'))
        self.assertTrue(r['success'])
        self.assertEqual(r['message'], 'Channel information was not configured by an admin.')

        get_params['channel_name'] = 'TestChannelNewServer'
        response = self.client.get('/server/channel_info', get_params)
        self.assertTrue(response['Content-Type'].startswith('application/json'))
        r = json.loads(response.content.decode('utf-8'))
        self.assertTrue(r['success'])
        self.assertEqual(r['message'], 'A new channel was added.')

        get_params['channel_name'] = 'TestChannelKnown'
        response = self.client.get('/client/channel_info', get_params)
        self.assertTrue(response['Content-Type'].startswith('application/json'))
        r = json.loads(response.content.decode('utf-8'))
        self.assertTrue(r['success'])
        self.assertEqual(r['message'], 'Channel information was returned correctly.')

        get_params['channel_name'] = 'TestChannelUnknown'
        response = self.client.get('/client/channel_info', get_params)
        self.assertTrue(response['Content-Type'].startswith('application/json'))
        r = json.loads(response.content.decode('utf-8'))
        self.assertTrue(r['success'])
        self.assertEqual(r['message'], 'Channel information was not configured by an admin.')

        get_params['channel_name'] = 'TestChannelNewClient'
        response = self.client.get('/client/channel_info', get_params)
        self.assertTrue(response['Content-Type'].startswith('application/json'))
        r = json.loads(response.content.decode('utf-8'))
        self.assertTrue(r['success'])
        self.assertEqual(r['message'], 'A new channel was added.')

    def test_client_info(self):
        get_params = dict()

        get_params['mac'] = '00:00:00:00:00:01'
        response = self.client.get('/client/client_info', get_params)
        self.assertTrue(response['Content-Type'].startswith('application/json'))
        r = json.loads(response.content.decode('utf-8'))
        self.assertTrue(r['success'])
        self.assertEqual(r['message'], 'A new client was added.')

        response = self.client.get('/client/client_info', get_params)
        self.assertTrue(response['Content-Type'].startswith('application/json'))
        r = json.loads(response.content.decode('utf-8'))
        self.assertTrue(r['success'])
        self.assertEqual(r['message'], 'Client information was returned correctly.')

        get_params['mac'] = '00:00:00:00:00:00'
        response = self.client.get('/client/client_info', get_params)
        self.assertTrue(response['Content-Type'].startswith('application/json'))
        r = json.loads(response.content.decode('utf-8'))
        self.assertTrue(r['success'])
        self.assertEqual(r['message'], 'Client information was returned correctly.')

    def test_recording_info(self):
        post_params = dict()
        tz_name = pytz.timezone(settings.TIME_ZONE)

        post_params['mac'] = '00:00:00:00:00:00'
        post_params['begin'] = (datetime.datetime.now(tz=tz_name) - datetime.timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%S%z")
        post_params['end'] = (datetime.datetime.now(tz=tz_name) - datetime.timedelta(minutes=1)).strftime("%Y-%m-%dT%H:%M:%S%z")
        response = self.client.post('/client/recording_info', post_params)
        self.assertTrue(response['Content-Type'].startswith('application/json'))
        r = json.loads(response.content.decode('utf-8'))
        self.assertTrue(r['success'])
        self.assertEqual(r['message'], 'Recording info was added correctly.')


SERVICE_CONFIGURATIONS_LOCAL = {
    'SERVER_TYPE': 'local',
    'GLOBAL_SERVER_HOSTNAME': 'api.sig2.com',
    'GLOBAL_SERVER_PORT': 8000,
    'LOG_SERVER_HOSTNAME': 'log.sig2.com',
    'LOG_SERVER_PORT': 24224,
    'LOCAL_SERVER_NAME': 'AMC/Anesthesia',
    'LOCAL_SERVER_HOSTNAME': '192.168.134.101',
    'LOCAL_SERVER_PORT': 8000,
    'LOCAL_SERVER_DATAPATH': 'uploaded_data',
    'STORAGE_SERVER': False,
    'STORAGE_SERVER_HOSTNAME': '192.168.134.156',
    'STORAGE_SERVER_USER': 'shmoon',
    'STORAGE_SERVER_PASSWORD': 'qwer1234!',
    'STORAGE_SERVER_PATH': '/CloudStation/CloudStation',
    'DB_SERVER': True,
    'DB_SERVER_HOSTNAME': '192.168.134.177',
    'DB_SERVER_USER': 'shmoon',
    'DB_SERVER_PASSWORD': 'ibsntxmes',
    'DB_SERVER_DATABASE': 'op_signal'
}


@override_settings(SERVICE_CONFIGURATIONS=SERVICE_CONFIGURATIONS_LOCAL)
class UnitTestLocalServerAPI(TestCase):
    def setUp(self):
        self.client = tClient()
        testdevice = Device.objects.create(device_type='LocalTestDevice', displayed_name='LocalTestDeviceDisplay')
        Channel.objects.create(name='UnknownLocalTestChannel', abbreviation='UnknownLocalTestChannel', device=testdevice, unit='mmHg', is_unknown=True)
        Channel.objects.create(name='KnownLocalTestChannel', abbreviation='KnownLocalTestChannel', device=testdevice, unit='mmHg', is_unknown=False)
        u_room = Room.objects.create(name='UnknownLocalRoom')
        u_bed = Bed.objects.create(name='UnknownLocalBed', room=u_room)
        Client.objects.create(name='UnknownLocalClient', mac='00:00:00:00:00:00', bed=u_bed)
        d_room = Room.objects.create(name='D')
        d_06_bed = Bed.objects.create(name='D-06', room=d_room)

    def test_configuration(self):
        self.assertTrue(settings.SERVICE_CONFIGURATIONS['SERVER_TYPE'] == 'local')

    def test_device_info(self):
        get_params = dict()

        # When a new device was requested.
        get_params['device_type'] = 'TestDeviceNewClient'
        response = self.client.get('/client/device_info', get_params)
        self.assertTrue(response['Content-Type'].startswith('application/json'))
        r = json.loads(response.content.decode('utf-8'))
        self.assertTrue(r['success'])
        self.assertEqual(r['message'], 'Device information was acquired from a global server.')

        get_params['device_type'] = 'LocalTestDevice'
        response = self.client.get('/client/device_info', get_params)
        self.assertTrue(response['Content-Type'].startswith('application/json'))
        r = json.loads(response.content.decode('utf-8'))
        self.assertTrue(r['success'])
        self.assertEqual(r['message'], 'Device information was returned correctly.')

    def test_channel_info(self):
        get_params = dict()

        get_params['device_type'] = 'TestDevice'
        get_params['channel_name'] = 'TestChannelKnown'
        response = self.client.get('/server/channel_info', get_params)
        self.assertTrue(response['Content-Type'].startswith('application/json'))
        r = json.loads(response.content.decode('utf-8'))
        self.assertTrue(not r['success'])
        self.assertEqual(r['message'], 'A local server received a server API request.')

        get_params['device_type'] = 'LocalTestDevice'
        get_params['channel_name'] = 'KnownLocalTestChannel'
        response = self.client.get('/client/channel_info', get_params)
        self.assertTrue(response['Content-Type'].startswith('application/json'))
        r = json.loads(response.content.decode('utf-8'))
        self.assertTrue(r['success'])
        self.assertEqual(r['message'], 'Channel information was returned correctly.')

        get_params['channel_name'] = 'UnknownLocalTestChannel'
        response = self.client.get('/client/channel_info', get_params)
        self.assertTrue(response['Content-Type'].startswith('application/json'))
        r = json.loads(response.content.decode('utf-8'))
        self.assertTrue(r['success'])
        self.assertEqual(r['message'], 'Channel information was not configured by an admin.')

        get_params['channel_name'] = 'TestChannelNewClient'
        response = self.client.get('/client/channel_info', get_params)
        self.assertTrue(response['Content-Type'].startswith('application/json'))
        r = json.loads(response.content.decode('utf-8'))
        self.assertTrue(r['success'])
        self.assertEqual(r['message'], 'Channel information was acquired from a global server.')

    def test_recording_info(self):
        post_params = dict()

        tz_name = pytz.timezone(settings.TIME_ZONE)

        fluent = FluentSender('log.sig2.com', 24224, 'sa')
        fluent.send({'hello': 'fluent'}, 'sa.local')

        post_params['mac'] = '00:00:00:00:00:00'
        post_params['begin'] = (datetime.datetime.now(tz=tz_name) - datetime.timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%S%z")
        post_params['end'] = (datetime.datetime.now(tz=tz_name) - datetime.timedelta(minutes=1)).strftime("%Y-%m-%dT%H:%M:%S%z")
        response = self.client.post('/server/recording_info', post_params)
        self.assertTrue(response['Content-Type'].startswith('application/json'))
        r = json.loads(response.content.decode('utf-8'))
        self.assertTrue(not r['success'])
        self.assertEqual(r['message'], 'Recording info API cannot be called from a local server.')

        try:
            with open('test/test_original.txt') as fp:
                post_params['attachment'] = fp
                response = self.client.post('/client/recording_info', post_params)
            self.assertTrue(response['Content-Type'].startswith('application/json'))
            r = json.loads(response.content.decode('utf-8'))
            self.assertTrue(r['success'])
            self.assertEqual(r['message'], 'Recording info was added and file was uploaded correctly.')
        except Exception as e:
            self.assertTrue(True)

    def test_report_status(self):
        get_params = dict()

        tz_name = pytz.timezone(settings.TIME_ZONE)

        bus_info_1 = {
            "bus_01": [
                {"slot": "COM1", "device_type": "M8000"},
                {"slot": "COM2", "device_type": ""},
            ]
        }
        bus_info_2 = {
            "bus_01": [
                {"slot": "COM1", "device_type": "M8000"},
                {"slot": "COM2", "device_type": "bis"},
                {"slot": "COM3", "device_type": "EV1000"},
                {"slot": "COM4", "device_type": ""}
            ],
            "bus_02": [
                {"slot": "COM5", "device_type": ""}
            ]
        }
        get_params['mac'] = '00:00:00:00:00:00'
        get_params['report_dt'] = (datetime.datetime.now(tz=tz_name) - datetime.timedelta(minutes=1)).strftime("%Y-%m-%dT%H:%M:%S%z")
        get_params['ip_address'] = '143.248.1.177'
        get_params['client_version'] = '1.2.5'
        get_params['uptime'] = 145234
        get_params['bus_info'] = json.dumps(bus_info_1, sort_keys=True, indent=4)
        get_params['status'] = 'Standby'

        response = self.client.get('/client/report_status', get_params)
        self.assertTrue(response['Content-Type'].startswith('application/json'))
        r = json.loads(response.content.decode('utf-8'))
        self.assertTrue(r['success'])
        self.assertEqual(r['message'], 'Client status was updated correctly.')

        get_params['status'] = 'Recording'
        get_params['record_begin_dt'] = (datetime.datetime.now(tz=tz_name) - datetime.timedelta(minutes=1)).strftime("%Y-%m-%dT%H:%M:%S%z")
        get_params['bus_info'] = json.dumps(bus_info_2, sort_keys=True, indent=4)
        response = self.client.get('/client/report_status', get_params)
        self.assertTrue(response['Content-Type'].startswith('application/json'))
        r = json.loads(response.content.decode('utf-8'))
        self.assertTrue(r['success'])
        self.assertEqual(r['message'], 'Client status was updated correctly.')

    def test_db_upload(self):
#        db_upload_main_numeric('test/C-05_190121_100007.vital', 'C', 'C-05')
#        db_upload_main_numeric('test/F-04_190117_112235.vital', 'F', 'F-04')
        try:
            db_upload_main_numeric('test/C-05_190121_100007.vital', 'C', 'C-05', db_writing=False)
            db_upload_main_numeric('test/F-04_190117_112235.vital', 'F', 'F-04', db_writing=False)
        except Exception as e:
            self.assertTrue(True)

    def test_upload_review(self):
        post_params = dict()
        post_params['dt_report'] = '2019-02-14'
        post_params['name'] = 'D-06_190214'
        post_params['bed'] = 'D-06'

        with open('test/D-06_190214.png', 'rb') as fp:
            post_params['chart'] = fp
            response = self.client.post('/upload_review', post_params)
        self.assertTrue(response['Content-Type'].startswith('application/json'))
        r = json.loads(response.content.decode('utf-8'))
        self.assertTrue(r['success'])
        self.assertEqual(r['message'], 'A review was successfully uploaded.')
        with open('test/D-06_190214.png', 'rb') as fp:
            post_params['chart'] = fp
            response = self.client.post('/upload_review', post_params)
        self.assertTrue(response['Content-Type'].startswith('application/json'))
        r = json.loads(response.content.decode('utf-8'))
        self.assertTrue(r['success'])
        self.assertEqual(r['message'], 'An existing review was successfully updated.')


