from course_discovery.settings.production import *

DEBUG = True

# Docker does not support the syslog socket at /dev/log. Rely on the console.
LOGGING['handlers']['local'] = {
    'class': 'logging.NullHandler',
}

# Determine which requests should render Django Debug Toolbar
INTERNAL_IPS = ('courses.localhost',)  # 127.0.0.1

HAYSTACK_CONNECTIONS['default']['URL'] = 'http://edx.devstack.elasticsearch:9200/'

SOCIAL_AUTH_REDIRECT_IS_HTTPS = False

DEFAULT_PARTNER_ID = 1

# Allow live changes to JS and CSS
COMPRESS_OFFLINE = False
COMPRESS_ENABLED = False

#####################################################################
# Lastly, see if the developer has any local overrides.
if os.path.isfile(join(dirname(abspath(__file__)), 'private.py')):
    from .private import *  # pylint: disable=import-error

JWT_AUTH.update({
    'JWT_SECRET_KEY': SOCIAL_AUTH_EDX_OIDC_SECRET,
    'JWT_ISSUER': 'http://courses.localhost:8000/oauth2',
    'JWT_AUDIENCE': SOCIAL_AUTH_EDX_OIDC_KEY,
    'JWT_VERIFY_AUDIENCE': False,
})
