# chat/consumers.py
from asgiref.sync import async_to_sync
from channels.generic.websocket import WebsocketConsumer, JsonWebsocketConsumer
import json


class StreamConsumer(JsonWebsocketConsumer):
    def connect(self):
        self.listen = set()
        self.accept()

    def disconnect(self, close_code):
        # Leave room group
        for client in self.listen:
            async_to_sync(self.channel_layer.group_discard)(
                str(client),
                self.channel_name
            )
        self.listen = set()

    # Receive message from WebSocket
    def receive_json(self, content):
        if content['command'] == 'start_listen' if 'command' in content else False:
            if content['client_id'] not in self.listen:
                self.listen.add(content['client_id'])
                async_to_sync(self.channel_layer.group_add)(
                    str(content['client_id']),
                    self.channel_name
                )
        elif content['command'] == 'stop_listen' if 'command' in content else False:
            if content['client_id'] in self.listen:
                self.listen.remove(content['client_id'])
                async_to_sync(self.channel_layer.group_discard)(
                    str(content['client_id']),
                    self.channel_name
                )
        else:
            # Send message to room group
            async_to_sync(self.channel_layer.group_send)(
                str(content['client_id']),
                {
                    'type': 'chat_message',
                    'client_id': content['client_id'],
                    'channel_id': content['channel_id'],
                    'packet': content['packet'],
                    'message': content['message']
                }
            )

    # Receive message from room group
    def chat_message(self, event):
        # Send message to WebSocket
        self.send_json({
            'client_id': event['client_id'],
            'channel_id': event['channel_id'],
            'packet': event['packet'],
            'message': event['message']
        })


class ChatConsumer(WebsocketConsumer):
    def connect(self):
        self.room_name = self.scope['url_route']['kwargs']['room_name']
        self.room_group_name = 'chat_%s' % self.room_name

        # Join room group
        async_to_sync(self.channel_layer.group_add)(
            self.room_group_name,
            self.channel_name
        )

        self.accept()

    def disconnect(self, close_code):
        # Leave room group
        async_to_sync(self.channel_layer.group_discard)(
            self.room_group_name,
            self.channel_name
        )

    # Receive message from WebSocket
    def receive(self, text_data):
        text_data_json = json.loads(text_data)
        message = text_data_json['message']

        # Send message to room group
        async_to_sync(self.channel_layer.group_send)(
            self.room_group_name,
            {
                'type': 'chat_message',
                'message': message
            }
        )

    # Receive message from room group
    def chat_message(self, event):
        message = event['message']

        # Send message to WebSocket
        self.send(text_data=json.dumps({
            'message': message
        }))
