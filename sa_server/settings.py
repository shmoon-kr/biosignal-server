"""
Django settings for sa_server project.

Generated by 'django-admin startproject' using Django 2.1.2.

For more information on this file, see
https://docs.djangoproject.com/en/2.1/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/2.1/ref/settings/
"""

import os
from .local_settings import *

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/2.1/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
#SECRET_KEY = 'secket_key'

# SECURITY WARNING: don't run with debug turned on in production!
#DEBUG = True

ALLOWED_HOSTS = ['*']


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'sa_api',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'sa_server.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'sa_server.wsgi.application'


# Database
# https://docs.djangoproject.com/en/2.1/ref/settings/#databases
# This part should be moved to local_settings.py file

'''
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'dev_sa_server',
        'USER': 'sa_server',
        'PASSWORD': 'qwer1234!',
        'HOST': 'localhost',
        'PORT': '3306',
    },
    'TEST': {
        'NAME': 'test_sa_server'
    }
}
'''

# Password validation
# https://docs.djangoproject.com/en/2.1/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/2.1/topics/i18n/

LANGUAGE_CODE = 'ko-kr'

TIME_ZONE = 'Asia/Seoul'

USE_I18N = True

USE_L10N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/2.1/howto/static-files/

STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'static/')

MEDIA_URL = '/media/'
MEDIA_ROOT = 'media/'

# Service configurations
# This part should be moved to local_settings.py file

'''
SERVICE_CONFIGURATIONS = {
    'SERVER_TYPE': 'global',
    'GLOBAL_SERVER_HOSTNAME': 'dev.sig2.com',
    'GLOBAL_SERVER_PORT': 8000,
    'LOG_SERVER_HOSTNAME': 'dev.sig2.com',
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
'''
