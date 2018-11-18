from django.conf.urls import url, include
from django.urls import path
from sa_api import views

urlpatterns = [
    path('server/device_info', views.device_info_server),
    path('server/channel_info', views.channel_info_server),
    path('server/client_info', views.client_info_server),
    path('server/recording_info', views.recording_info_server),
    path('client/device_info', views.device_info_client),
    path('client/channel_info', views.channel_info_client),
    path('client/client_info', views.client_info_client),
    path('client/recording_info', views.recording_info_client),
]
