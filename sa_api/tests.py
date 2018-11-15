import json
import datetime
from django.test import TestCase, override_settings
from django.test import Client as tClient
from django.conf import settings
import sa_api.views
from sa_api.models import Device, Client, Bed, Channel, Room, FileRecorded

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
        Device.objects.create(device_type='TestDevice', displayed_name='TestDevice')
        Channel.objects.create(name='TestChannelUnknown', abbreviation='TestChannelUnknown', device_type='TestDevice', unit='mmHg', is_unknown=True)
        Channel.objects.create(name='TestChannelKnown', abbreviation='TestChannelKnown', device_type='TestDevice', unit='mmHg', is_unknown=False)
        u_room = Room.objects.create(name='Uknown')
        u_bed = Bed.objects.create(name='Uknown', room=u_room)
        Client.objects.create(name='Unknown', mac='00:00:00:00:00:00', bed=u_bed)

    def test_configuration(self):
        self.assertTrue(settings.SERVICE_CONFIGURATIONS['SERVER_TYPE'] == 'global')

    def test_device_info(self):
        get_params = dict()

        get_params['device_type'] = 'TestDeviceNewServer'
        response = self.client.get('/server/device_info', get_params)
        r = json.loads(response.content)
        self.assertTrue(r['success'])
        self.assertEqual(r['message'], 'New device was added.')

        get_params['device_type'] = 'TestDevice'
        response = self.client.get('/server/device_info', get_params)
        r = json.loads(response.content)
        self.assertTrue(r['success'])
        self.assertEqual(r['message'], 'Device information was returned correctly.')

        get_params['device_type'] = 'TestDeviceNewClient'
        response = self.client.get('/client/device_info', get_params)
        r = json.loads(response.content)
        self.assertTrue(r['success'])
        self.assertEqual(r['message'], 'New device was added.')

        get_params['device_type'] = 'TestDevice'
        response = self.client.get('/client/device_info', get_params)
        r = json.loads(response.content)
        self.assertTrue(r['success'])
        self.assertEqual(r['message'], 'Device information was returned correctly.')

    def test_channel_info(self):
        get_params = dict()

        get_params['device_type'] = 'TestDevice'
        get_params['channel_name'] = 'TestChannelKnown'
        response = self.client.get('/server/channel_info', get_params)
        r = json.loads(response.content)
        self.assertTrue(r['success'])
        self.assertEqual(r['message'], 'Channel information was returned correctly.')

        get_params['channel_name'] = 'TestChannelUnknown'
        response = self.client.get('/server/channel_info', get_params)
        r = json.loads(response.content)
        self.assertTrue(r['success'])
        self.assertEqual(r['message'], 'Channel information was not configured by an admin.')

        get_params['channel_name'] = 'TestChannelNewServer'
        response = self.client.get('/server/channel_info', get_params)
        r = json.loads(response.content)
        self.assertTrue(r['success'])
        self.assertEqual(r['message'], 'A new channel was added.')

        get_params['channel_name'] = 'TestChannelKnown'
        response = self.client.get('/client/channel_info', get_params)
        r = json.loads(response.content)
        self.assertTrue(r['success'])
        self.assertEqual(r['message'], 'Channel information was returned correctly.')

        get_params['channel_name'] = 'TestChannelUnknown'
        response = self.client.get('/client/channel_info', get_params)
        r = json.loads(response.content)
        self.assertTrue(r['success'])
        self.assertEqual(r['message'], 'Channel information was not configured by an admin.')

        get_params['channel_name'] = 'TestChannelNewClient'
        response = self.client.get('/client/channel_info', get_params)
        r = json.loads(response.content)
        self.assertTrue(r['success'])
        self.assertEqual(r['message'], 'A new channel was added.')

    def test_client_info(self):
        get_params = dict()

        get_params['mac'] = '00:00:00:00:00:01'
        response = self.client.get('/client/client_info', get_params)
        r = json.loads(response.content)
        self.assertTrue(r['success'])
        self.assertEqual(r['message'], 'A new client was added.')

        response = self.client.get('/client/client_info', get_params)
        r = json.loads(response.content)
        self.assertTrue(r['success'])
        self.assertEqual(r['message'], 'Client information was returned correctly.')

        get_params['mac'] = '00:00:00:00:00:00'
        response = self.client.get('/client/client_info', get_params)
        r = json.loads(response.content)
        self.assertTrue(r['success'])
        self.assertEqual(r['message'], 'Client information was returned correctly.')

    def test_recording_info(self):
        get_params = dict()

        get_params['mac'] = '00:00:00:00:00:00'
        get_params['begin'] = (datetime.datetime.now() - datetime.timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
        get_params['end'] = (datetime.datetime.now() - datetime.timedelta(minutes=1)).strftime("%Y-%m-%d %H:%M:%S")
        response = self.client.get('/client/recording_info', get_params)
        r = json.loads(response.content)
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
    'LOCAL_SERVER_DATAPATH': '/home/shmoon/sig2_files',
    'STORAGE_SERVER': False,
    'STORAGE_SERVER_HOSTNAME': '192.168.134.156',
    'STORAGE_SERVER_USER': 'shmoon',
    'STORAGE_SERVER_PASSWORD': 'qwer1234!',
    'STORAGE_SERVER_PATH': '/CloudStation/CloudStation',
}

@override_settings(SERVICE_CONFIGURATIONS=SERVICE_CONFIGURATIONS_LOCAL)
class UnitTestLocalServerAPI(TestCase):
    def setUp(self):
        self.client = tClient()
        Device.objects.create(device_type='LocalTestDevice', displayed_name='LocalTestDevice')
        Channel.objects.create(name='LocalTestChannelUnknown', abbreviation='LocalTestChannelUnknown', device_type='LocalTestDevice', unit='mmHg', is_unknown=True)
        Channel.objects.create(name='LocalTestChannelKnown', abbreviation='LocalTestChannelKnown', device_type='LocalTestDevice', unit='mmHg', is_unknown=False)
        u_room = Room.objects.create(name='LocalUknown')
        u_bed = Bed.objects.create(name='LocalUknown', room=u_room)
        Client.objects.create(name='LocalUnknown', mac='00:00:00:00:00:00', bed=u_bed)

    def test_configuration(self):
        self.assertTrue(settings.SERVICE_CONFIGURATIONS['SERVER_TYPE'] == 'local')

    def test_device_info(self):
        get_params = dict()

        # When a new device was requested.
        get_params['device_type'] = 'TestDeviceNewClient'
        response = self.client.get('/client/device_info', get_params)
        r = json.loads(response.content)
        self.assertTrue(r['success'])
        self.assertEqual(r['message'], 'Device information was acquired from a global server.')

        get_params['device_type'] = 'LocalTestDevice'
        response = self.client.get('/client/device_info', get_params)
        r = json.loads(response.content)
        self.assertTrue(r['success'])
        self.assertEqual(r['message'], 'Device information was returned correctly.')

    def test_channel_info(self):
        get_params = dict()

        get_params['device_type'] = 'TestDevice'
        get_params['channel_name'] = 'TestChannelKnown'
        response = self.client.get('/server/channel_info', get_params)
        r = json.loads(response.content)
        self.assertTrue(not r['success'])
        self.assertEqual(r['message'], 'A local server received a server API request.')

        get_params['channel_name'] = 'LocalTestChannelKnown'
        response = self.client.get('/client/channel_info', get_params)
        r = json.loads(response.content)
        print(r)
        self.assertTrue(r['success'])
        self.assertEqual(r['message'], 'Channel information was returned correctly.')

        get_params['channel_name'] = 'LocalTestChannelUnknown'
        response = self.client.get('/client/channel_info', get_params)
        r = json.loads(response.content)
        self.assertTrue(r['success'])
        self.assertEqual(r['message'], 'Channel information was not configured by an admin.')

        get_params['channel_name'] = 'TestChannelNewClient'
        response = self.client.get('/client/channel_info', get_params)
        r = json.loads(response.content)
        self.assertTrue(r['success'])
        self.assertEqual(r['message'], 'Channel information was acquired from a global server.')

    def test_recording_info(self):
        get_params = dict()

        get_params['mac'] = '00:00:00:00:00:00'
        get_params['begin'] = (datetime.datetime.now() - datetime.timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
        get_params['end'] = (datetime.datetime.now() - datetime.timedelta(minutes=1)).strftime("%Y-%m-%d %H:%M:%S")
        response = self.client.get('/server/recording_info', get_params)
        r = json.loads(response.content)
        self.assertTrue(not r['success'])
        self.assertEqual(r['message'], 'Recording info API cannot be called from a local server.')

        response = self.client.get('/client/recording_info', get_params)
        r = json.loads(response.content)
        self.assertTrue(r['success'])
        self.assertEqual(r['message'], 'Recording info was added correctly.')
