import random
import string

import requests
from django.utils.functional import cached_property
from stdimage.models import StdImageFieldFile
from stdimage.utils import UploadTo

from course_discovery.apps.course_metadata.exceptions import MarketingSiteAPIClientException

RESERVED_ELASTICSEARCH_QUERY_OPERATORS = ('AND', 'OR', 'NOT', 'TO',)


def clean_query(query):
    """ Prepares a raw query for search.

    Args:
        query (str): query to clean.

    Returns:
        str: cleaned query
    """
    # Ensure the query is lowercase, since that is how we index our data.
    query = query.lower()

    # Specifying a SearchQuerySet filter will append an explicit AND clause to the query, thus changing its semantics.
    # So we wrap parentheses around the original query in order to preserve the semantics.
    query = '({qs})'.format(qs=query)

    # Ensure all operators are uppercase
    for operator in RESERVED_ELASTICSEARCH_QUERY_OPERATORS:
        old = ' {0} '.format(operator.lower())
        new = ' {0} '.format(operator.upper())
        query = query.replace(old, new)

    return query


class UploadToFieldNamePath(UploadTo):
    """
    This is a utility to create file path for uploads based on instance field value
    """
    def __init__(self, populate_from, **kwargs):
        self.populate_from = populate_from
        super(UploadToFieldNamePath, self).__init__(populate_from, **kwargs)

    def __call__(self, instance, filename):
        field_value = getattr(instance, self.populate_from)
        self.kwargs.update({
            'name': field_value
        })
        return super(UploadToFieldNamePath, self).__call__(instance, filename)


def custom_render_variations(file_name, variations, storage, replace=True):
    """ Utility method used to override default behaviour of StdImageFieldFile by
    passing it replace=True.

    Args:
        file_name (str): name of the image file.
        variations (dict): dict containing variations of image
        storage (Storage): Storage class responsible for storing the image.

    Returns:
        False (bool): to prevent its default behaviour
    """

    for variation in variations.values():
        StdImageFieldFile.render_variation(file_name, variation, replace, storage)

    # to prevent default behaviour
    return False


class MarketingSiteAPIClient(object):
    """
    The marketing site API client we can use to communicate with the marketing site
    """
    username = None
    password = None
    api_url = None

    def __init__(self, marketing_site_api_username, marketing_site_api_password, api_url):
        if not (marketing_site_api_username and marketing_site_api_password):
            raise MarketingSiteAPIClientException('Marketing Site API credentials are not properly configured!')
        self.username = marketing_site_api_username
        self.password = marketing_site_api_password
        self.api_url = api_url.strip('/')

    @cached_property
    def init_session(self):
        # Login to set session cookies
        session = requests.Session()
        login_url = '{root}/user'.format(root=self.api_url)
        login_data = {
            'name': self.username,
            'pass': self.password,
            'form_id': 'user_login',
            'op': 'Log in',
        }
        response = session.post(login_url, data=login_data)
        admin_url = '{root}/admin'.format(root=self.api_url)
        # This is not a RESTful API so checking the status code is not enough
        # We also check that we were redirected to the admin page
        if not (response.status_code == 200 and response.url == admin_url):
            raise MarketingSiteAPIClientException(
                {
                    'message': 'Marketing Site Login failed!',
                    'status': response.status_code,
                    'url': response.url
                }
            )
        return session

    @property
    def api_session(self):
        self.init_session.headers.update(self.headers)
        return self.init_session

    @property
    def csrf_token(self):
        # We need to make sure we can bypass the Varnish cache.
        # So adding a random salt into the query string to cache bust
        random_qs = ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(10))
        token_url = '{root}/restws/session/token?cachebust={qs}'.format(root=self.api_url, qs=random_qs)
        response = self.init_session.get(token_url)
        if not response.status_code == 200:
            raise MarketingSiteAPIClientException({
                'message': 'Failed to retrieve Marketing Site CSRF token!',
                'status': response.status_code,
            })
        token = response.content.decode('utf8')
        return token

    @cached_property
    def user_id(self):
        # Get a user ID
        user_url = '{root}/user.json?name={username}'.format(root=self.api_url, username=self.username)
        response = self.init_session.get(user_url)
        if not response.status_code == 200:
            raise MarketingSiteAPIClientException('Failed to retrieve Marketing site user details!')
        user_id = response.json()['list'][0]['uid']
        return user_id

    @property
    def headers(self):
        return {
            'Content-Type': 'application/json',
            'X-CSRF-Token': self.csrf_token,
        }


# https://stackoverflow.com/questions/6760685/creating-a-singleton-in-python
class Singleton(type):
    _instances = {}
    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


# @singleton
class BearerToken():
    """ Singleton Class that creates a bearer token"""
    __metaclass__ = Singleton

    _token = None

    def __init__(self, api_url, username, password):
        # Login using the marketing credentials to access the JWT bearer token for future API calls.
        session = requests.Session()
        login_url = '{root}/jwt-auth/v1/token'.format(root=api_url)
        login_data = {
            'username': username,
            'password': password,
        }
        login_headers = {
            # 'Host': 'ew-localhost.com',
            'Content-Type': 'application/x-www-form-urlencoded; charset=utf-8'
        }

        # session.headers.update(token_headers)
        response = session.post(login_url, headers=login_headers, data=login_data)

        # response = requests.post(
        #     login_url,
        #     data=login_data,
        #     headers=login_header
        # )
        if not (response.status_code == 200):  # and response.url == admin_url
            raise MarketingSiteAPIClientException(
                {
                    'message': 'Marketing Site (Wordpress) Login failed when retrieving the BearerToken!',
                    'status': response.status_code,
                    'url': response.url
                }
            )

        data = response.json()

        try:
            self._token = data['token']
        except KeyError:
            raise requests.RequestException(response=response)

    def token(self):
        return self._token


# def get_bearer_token(api_url, username, password):
#     # Login using the marketing credentials to access the JWT bearer token for future API calls.
#     session = requests.Session()
#     login_url = '{root}/jwt-auth/v1/token'.format(root=api_url)
#     login_data = {
#         'username': username,
#         'password': password,
#     }
#     login_headers = {
#         # 'Host': 'ew-localhost.com',
#         'Content-Type': 'application/x-www-form-urlencoded; charset=utf-8'
#     }
#
#     # session.headers.update(token_headers)
#     response = session.post(login_url, headers=login_headers, data=login_data)
#
#     # response = requests.post(
#     #     login_url,
#     #     data=login_data,
#     #     headers=login_header
#     # )
#     if not (response.status_code == 200):  # and response.url == admin_url
#         raise MarketingSiteAPIClientException(
#             {
#                 'message': 'Marketing Site (Wordpress) Login failed!',
#                 'status': response.status_code,
#                 'url': response.url
#             }
#         )
#
#     data = response.json()
#
#     try:
#         return data['token']
#     except KeyError:
#         raise requests.RequestException(response=response)
#
#     return None

class MarketingSiteWordpressAPIClient(object):
    """
    The marketing site API client we can use to communicate with the marketing site (Wordpress)
    """
    user_id = None
    username = None
    password = None
    api_url = None
    bearer_token = None

    def __init__(self, marketing_site_api_username, marketing_site_api_password, marketing_site_api_url):
        if not (marketing_site_api_username and marketing_site_api_password):
            raise MarketingSiteAPIClientException('Marketing Site API credentials are not properly configured!')
        self.username = marketing_site_api_username
        self.password = marketing_site_api_password
        self.api_url = marketing_site_api_url.strip('/')
        self.bearer_token = BearerToken(self.api_url, self.username, self.password) # get_bearer_token(self._api_url, self._username, self._password)

        # Set the user_id for this account based on the username. Need to call Wordpress directly.
        # Need to make sure to also set https://github.com/WP-API/WP-API/issues/2300#issuecomment-299202391
        response = self.api_session.get('{root}/wp/v2/users/'.format(root=self.api_url))
        if response.status_code == 200:
            response_json = response.json()

            for user in response_json:
                if user["name"] == self.username:
                    self.user_id = user["id"]

            if not self.user_id:
                raise MarketingSiteAPIClientException(
                {
                    'message': 'Could not find Wordpress user "{user}" for authentication.'.format(user=self.username),
                    'status': response.status_code,
                    'url': response.url
                }
                )

    @cached_property
    def init_session(self):
        # Login to set session cookies
        session = requests.Session()
        # token_headers = {
        #     "Content-Type": "application/x-www-form-urlencoded; charset=utf-8"
        # }
        # session.headers.update(token_headers)

        login_url = '{root}/jwt-auth/v1/token/validate'.format(root=self.api_url)
        token_headers = self.headers

        response = session.post(login_url, headers=token_headers)
        # admin_url = '{root}/admin'.format(root=self.api_url)
        # This is not a RESTful API so checking the status code is not enough
        # We also check that we were redirected to the admin page
        if not (response.status_code == 200):  # and response.url == admin_url
            raise MarketingSiteAPIClientException(
                {
                    'message': 'Marketing Site (Wordpress) init_session - Validating Token!',
                    'status': response.status_code,
                    'url': response.url
                }
                )

        return session

    @property
    def api_session(self):
        self.init_session.headers.update(self.headers)
        return self.init_session

    @property
    def headers(self):
        return {
            'Content-Type': 'application/json',
            'Authorization': 'Bearer ' + self.bearer_token.token(),
        }
