from os.path import dirname, abspath

DEBUG = True
TEMPLATE_DEBUG = DEBUG

# base
BASE_DIR = dirname( abspath(__file__)).replace( 'lib/ptolemy/ipam', '')

ADMINS = (
    ('Yee-Ting Li', 'ytl@slac.stanford.edu'),
)
MANAGERS = ADMINS


DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.oracle',
        'NAME': 'SLAC_TCP',
        'USER': 'cando_anyuser',
        'PASSWORD': 'file:///afs/slac.stanford.edu/g/scs/net/netmon/lanmon/etc/cando.read'
    },
}


TIME_ZONE = 'America/Los_Angeles'
LANGUAGE_CODE = 'en-us'

SITE_ID = 1
USE_I18N = True
USE_L10N = True

MEDIA_ROOT = ''
MEDIA_URL = ''
STATIC_URL = '/media/'

# Make this unique, and don't share it with anybody.
SECRET_KEY = 'igns&69ef628l#cr-dsoph_9tjn(9!9w0wc*kl=xsiiyqhjatw'

# List of callables that know how to import templates from various sources.
TEMPLATE_LOADERS = (
    'django.template.loaders.filesystem.Loader',
    'django.template.loaders.app_directories.Loader',
#     'django.template.loaders.eggs.Loader',
)
MIDDLEWARE_CLASSES = (
    'django.middleware.common.CommonMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    # 'django.middleware.csrf.CsrfViewMiddleware',
    # 'django.contrib.auth.middleware.AuthenticationMiddleware',
    # 'django.contrib.auth.middleware.RemoteUserMiddleware',
    # 'django.contrib.messages.middleware.MessageMiddleware',
)
ROOT_URLCONF = 'ptolemy.urls'
AUTHENTICATION_BACKENDS = (
    'django.contrib.auth.backends.RemoteUserBackend',
)
INSTALLED_APPS = [
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.sites',
    'django.contrib.messages',
    # Uncomment the next line to enable the admin:
    # 'django.contrib.admin',
    # Uncomment the next line to enable admin documentation:
    # 'django.contrib.admindocs',
]

# read passwords from files for extra security
for db in DATABASES:
    if 'PASSWORD' in DATABASES[db] and DATABASES[db]['PASSWORD'].startswith('file://'):
        fp = DATABASES[db]['PASSWORD'].replace( 'file://', '' )
        f = open(fp, 'r')
        p = []
        for i in f.readlines():
            p.append( i.rstrip() )
        f.close()
        DATABASES[db]['PASSWORD'] = p.pop()

