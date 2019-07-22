from django.conf.urls import url, include
from django.urls import path
from sa_api import views

urlpatterns = [
    path('dashboard', views.dashboard),
    path('summary_rosette', views.summary_rosette),
    path('summary_file', views.summary_file),
    path('upload_review', views.upload_review),
    path('review', views.review),
    path('get_wavedata', views.get_wavedata),
    path('download_vital_file', views.download_vital_file),
    path('download_csv_device', views.download_csv_device),
    path('server/device_info', views.device_info_server),
    path('server/channel_info', views.channel_info_server),
    path('server/client_info', views.client_info_server),
    path('server/device_list', views.device_list_server),
    path('server/channel_list', views.channel_list_server),
    path('server/recording_info', views.recording_info_server),
    path('client/device_info', views.device_info_client),
    path('client/channel_info', views.channel_info_client),
    path('client/client_info', views.client_info_client),
    path('client/recording_info', views.recording_info_client),
    path('client/report_status', views.report_status_client),
    path('client/device_list', views.device_list_client),
    path('client/channel_list', views.channel_list_client),
    path('migration/register_vital_file', views.register_vital_file),
]
