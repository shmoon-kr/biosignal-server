from django.conf.urls import url, include
from django.urls import path
from sa_api import views

urlpatterns = [
    path('server/device_info', views.device_info_server),
    path('server/channel_info', views.channel_info_server),
    path('server/client_info', views.client_info),
    path('server/recording_info', views.recording_info),
    path('client/device_info', views.device_info_client),
    path('client/channel_info', views.channel_info_client),
    path('client/client_info', views.client_info),
    path('client/recording_info', views.recording_info),
    path('alive/<str:mac>/', views.alive),
    path('client_info/<str:mac>/', views.client_info),
    path('file_upload', views.file_upload),
#    path('test', views.test),
]
