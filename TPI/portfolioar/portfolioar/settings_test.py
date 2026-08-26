import os

os.environ['USE_SQLITE'] = 'True'

from portfolioar.settings import *  # noqa: F401, F403, E402

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}

INSTALLED_APPS = [app for app in INSTALLED_APPS if app != 'mssql']

USE_TZ = False
