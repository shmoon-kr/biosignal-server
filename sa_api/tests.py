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
        response = self.client.get('/server/client_info', get_params)
        r = json.loads(response.content)
        self.assertTrue(r['success'])
        self.assertEqual(r['message'], 'A new client was added.')

        response = self.client.get('/server/client_info', get_params)
        r = json.loads(response.content)
        self.assertTrue(r['success'])
        self.assertEqual(r['message'], 'Client information was returned correctly.')

        get_params['mac'] = '00:00:00:00:00:00'
        response = self.client.get('/server/client_info', get_params)
        r = json.loads(response.content)
        self.assertTrue(r['success'])
        self.assertEqual(r['message'], 'Client information was returned correctly.')

    def test_recording_info(self):
        get_params = dict()

        get_params['mac'] = '00:00:00:00:00:00'
        get_params['begin'] = (datetime.datetime.now() - datetime.timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
        get_params['end'] = (datetime.datetime.now() - datetime.timedelta(minutes=1)).strftime("%Y-%m-%d %H:%M:%S")
        response = self.client.get('/server/recording_info', get_params)
        r = json.loads(response.content)
        self.assertTrue(r['success'])
        self.assertEqual(r['message'], 'Recording info was added correctly.')
