import datetime
import json
import logging
from urllib.parse import urljoin, urlparse
import os

import waffle
from bs4 import BeautifulSoup
from django.utils.text import slugify

from course_discovery.apps.course_metadata.choices import CourseRunStatus
from course_discovery.apps.course_metadata.exceptions import (
    AliasCreateError, AliasDeleteError, FormRetrievalError, NodeCreateError, NodeDeleteError, NodeEditError,
    NodeLookupError, PostLookupError, PostEditError #, MediaLookupError, MediaCreateError
)
from course_discovery.apps.course_metadata.utils import MarketingSiteWordpressAPIClient

logger = logging.getLogger(__name__)


class BaseMarketingSiteWordpressPublisher:
    """
    Utility for publishing data to a Wordpress marketing site.

    Arguments:
        partner (apps.core.models.Partner): Partner instance containing information
            about the marketing site to which to publish.
    """
    unique_field = None
    post_lookup_field = None
    post_lookup_meta_group = None
    post_base = None

    def __init__(self, partner):
        self.partner = partner

        self.client = MarketingSiteWordpressAPIClient(
            self.partner.marketing_site_api_username,
            self.partner.marketing_site_api_password,
            self.partner.marketing_site_api_url
        )

        logger.info('Retrieved bearer token [%s] for API calls to the marketing site (Wordpress) ...', self.client.bearer_token.token())

        self.rest_api_base = '{base}/wp/v2'.format(base=self.client.api_url) # urljoin(self.client.api_url, '/acf/v3/')
        self.media_api_base = '{base}/media'.format(base=self.rest_api_base)
        self.post_course_api_base = '{base}/course'.format(base=self.rest_api_base) #urljoin(self.rest_api_base, 'course')
        # self.node_api_base = urljoin(self.client.api_url, '/node.json')
        # self.alias_api_base = urljoin(self.client.api_url, '/admin/config/search/path')
        # self.alias_add_url = '{}/add'.format(self.alias_api_base)

        # Define the post_base based on publisher type
        switcher = {
            "CourseRunMarketingSiteWordpressPublisher" : self.post_course_api_base
        }
        self.post_base = switcher.get(self.__class__.__name__, None)

    def publish_obj(self, obj, previous_obj=None):
        """
        Update or create a Wordpress post corresponding to the given model instance.

        Arguments:
            obj (django.db.models.Model): Model instance to be published.

        Keyword Arguments:
            previous_obj (CourseRun): Model instance representing the previous
                state of the model being changed. Inspected to determine if publication
                is necessary. May not exist if the model instance is being saved
                for the first time.
        """
        raise NotImplementedError

    # def delete_obj(self, obj):
    #     """
    #     Delete a Wordpress post corresponding to the given model instance.
    #
    #     Arguments:
    #         obj (django.db.models.Model): Model instance to be deleted.
    #     """
    #     # node_id = self.node_id(obj)
    #     #
    #     # self.delete_node(node_id)
    #     pass
    #
    def serialize_obj(self, obj):
        """
        Serialize a model instance to a representation that can be written to Wordpress.

        Arguments:
            obj (django.db.models.Model): Model instance to be published.

        Returns:
            dict: Data to PUT to the Wordpress API.
        """
        return {
            "fields": {
                self.post_lookup_meta_group: {
                    self.post_lookup_field: str(getattr(obj, self.unique_field)),
                    'date_modified': str(datetime.datetime.utcnow()),
                    'modified_by': self.client.user_id,
                }
            }
        }

    # def create_node(self, node_data):
    #     """
    #     Create a Wordpress post.
    #
    #     Arguments:
    #         node_data (dict): Data to POST to Wordpress for post creation.
    #
    #     Returns:
    #         str: The ID of the created post.
    #
    #     Raises:
    #         NodeCreateError: If the POST to Wordpress fails.
    #     """
    #     # node_data = json.dumps(node_data)
    #     #
    #     # response = self.client.api_session.post(self.node_api_base, data=node_data)
    #     #
    #     # if response.status_code == 201:
    #     #     return response.json()['id']
    #     # else:
    #     #     raise NodeCreateError({'response_text': response.text, 'response_status': response.status_code})
    #     return None
    #

    def create_media(self, post_data):
        filename = post_data["filename"]
        headers = {
            "Content-Disposition": 'attachment; filename=\\"{filename}\\"'.format(filename=filename)
        }

        post_data = json.dumps(post_data)

        response = self.client.api_session.post(self.media_api_base, headers=headers, data=post_data)

        if response.status_code == 201:
            return response.json()['id']
        else:
            raise MediaCreateError({'filename': filename, 'response_text': response.text, 'response_status': response.status_code})


    # def media_id(self, obj):
    #     """
    #     Find the ID of the media that we want to publish if it exists in the Wordpress media library.
    #
    #     Arguments:
    #         filename (str): Identifier used to figure out media id.
    #
    #     Returns:
    #         str: The post ID.
    #
    #     Raises:
    #         MediaLookupError: If media lookup fails.
    #     """
    #
    #     # Check to see if the Wordpress media id already exists in the CourseRun and return it.
    #     if obj.wordpress_media_id:
    #         return obj.wordpress_media_id
    #
    #     # https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Content-Disposition
    #     headers = {
    #         "Content-Disposition": 'inline'
    #     }
    #
    #     response = self.client.api_session.get(self.media_api_base, headers=headers)
    #
    #     if response.status_code == 200:
    #         response_json = response.json()
    #         filename = os.path.basename(urlparse(obj.card_image_url).path).split('@')[-1]
    #
    #         # Loop through all media results and grab the latest updated one.
    #         for post in response_json:
    #
    #             if post["source_url"] and (filename == os.path.basename(urlparse(post["source_url"]).path)):
    #                 # Return the first found media with same name. We can override this in course_run.wordpress_media_id
    #                 obj.wordpress_media_id = post["id"]
    #                 obj.save()
    #
    #                 return obj.wordpress_media_id
    #
    #     raise MediaLookupError({'response_status': 'Could not locate Wordpress media id', 'filename': filename})


    def post_id(self, obj):
        """
        Find the ID of the post (Course) we want to publish to, if it exists.

        Arguments:
            obj (django.db.models.Model): Model instance to be published.

        Returns:
            str: The post ID.

        Raises:
            PostLookupError: If post lookup fails.
        """

        # params = {
        #     self.post_lookup_field: getattr(obj, self.unique_field),
        # }

        # Check to see if the Wordpress post id already exists in the CourseRun and return it.
        if obj.wordpress_post_id:
            return obj.wordpress_post_id

        # Otherwise perform a lookup in all course custom post types and find if the post_lookup_field matches and existing one.
        response = self.client.api_session.get(self.post_base) # , params=params
        if response.status_code == 200:
            response_json = response.json()

            # Loop through all post checking to see if the open_edx_meta field group contains the same course_id.
            for post in response_json:

                # Check to see if we have payload of course post types from ACF service.
                if post['acf'] and post['acf'][self.post_lookup_meta_group].get(self.post_lookup_field) == getattr(obj, self.unique_field):
                    obj.wordpress_post_id = post['id']
                    obj.save()

                    return obj.wordpress_post_id
        else:
            raise PostLookupError({'response_status': 'Could not locate Wordpress post id for course', 'course_id': getattr(obj, self.unique_field)})


    # def create_node(self, node_data):
    #     """
    #     Create a Wordpress post.
    #
    #     Arguments:
    #         node_data (dict): Data to POST to Wordpress for post creation.
    #
    #     Returns:
    #         str: The ID of the created post.
    #
    #     Raises:
    #         NodeCreateError: If the POST to Wordpress fails.
    #     """
    #     # node_data = json.dumps(node_data)
    #     #
    #     # response = self.client.api_session.post(self.node_api_base, data=node_data)
    #     #
    #     # if response.status_code == 201:
    #     #     return response.json()['id']
    #     # else:
    #     #     raise NodeCreateError({'response_text': response.text, 'response_status': response.status_code})
    #     return None
    #
    def edit_post(self, post_id, post_data, post_type=""):
        """
        Edit a Wordpress post.

        Arguments:
            post_id (str): ID of the post to edit.
            post_data (dict): Fields to overwrite on the post.
            post_type (tuple): Identifies custom field post type.

        Raises:
            NodeEditError: If the PUT to Wordpress fails.
        """

        post_url = '{base}/{post_id}'.format(base=self.post_base, post_id=post_id)
        post_data = json.dumps(post_data)

        response = self.client.api_session.put(post_url, data=post_data)

        if response.status_code != 200:
            raise PostEditError(
                {
                    'post_id': post_id,
                    'response_text': response.text,
                    'response_status': response.status_code
                }
            )


    # def delete_node(self, node_id):
    #     """
    #     Delete a Wordpress post.
    #
    #     Arguments:
    #         node_id (str): ID of the post to delete.
    #
    #     Raises:
    #         NodeDeleteError: If the DELETE to Wordpress fails.
    #     """
    #     # node_url = '{base}/{node_id}'.format(base=self.node_api_base, node_id=node_id)
    #     #
    #     # response = self.client.api_session.delete(node_url)
    #     #
    #     # if response.status_code != 200:
    #     #     raise NodeDeleteError(
    #     #         {
    #     #             'node_id': node_id,
    #     #             'response_text': response.text,
    #     #             'response_status': response.status_code
    #     #         }
    #     #     )
    #     pass

    # def get_marketing_slug(self, obj):
    #     return obj.marketing_slug
    #
    # def alias(self, obj):
    #     return '{type}/{slug}'.format(type=obj.type.slug, slug=obj.marketing_slug)
    #
    # def get_alias_list_url(self, slug):
    #     return '{base}/list/{slug}'.format(
    #         base=self.alias_api_base,
    #         slug=slug
    #     )
    #
    # def delete_alias(self, alias_delete_path):
    #     """
    #     Delete the url alias for provided path
    #     """
    #     headers = {
    #         'content-type': 'application/x-www-form-urlencoded'
    #     }
    #     alias_delete_url = '{base}/{path}'.format(
    #         base=self.client.api_url,
    #         path=alias_delete_path.strip('/')
    #     )
    #
    #     data = {
    #         **self.alias_form_inputs(alias_delete_url),
    #         'confirm': 1,
    #         'form_id': 'path_admin_delete_confirm',
    #         'op': 'Confirm'
    #     }
    #
    #     response = self.client.api_session.post(alias_delete_url, headers=headers, data=data)
    #
    #     if response.status_code != 200:
    #         raise AliasDeleteError
    #
    # def alias_form_inputs(self, url):
    #     """
    #     Scrape input values from the form used to modify Wordpress aliases.
    #
    #     Raises:
    #         FormRetrievalError: If there's a problem getting the form from Wordpress.
    #     """
    #     response = self.client.api_session.get(url)
    #
    #     if response.status_code != 200:
    #         raise FormRetrievalError
    #
    #     html = BeautifulSoup(response.text, 'html.parser')
    #
    #     return {
    #         field: html.find('input', {'name': field}).get('value')
    #         for field in ('form_build_id', 'form_token')
    #     }
    #
    # def alias_delete_path(self, url):
    #     """
    #     Scrape the path to which we need to POST to delete an alias from the form
    #     used to modify aliases.
    #
    #     Raises:
    #         FormRetrievalError: If there's a problem getting the form from Wordpress.
    #     """
    #     response = self.client.api_session.get(url)
    #
    #     if response.status_code != 200:
    #         raise FormRetrievalError
    #
    #     html = BeautifulSoup(response.text, 'html.parser')
    #     delete_element = html.select('.delete.last a')
    #
    #     return delete_element[0].get('href') if delete_element else None
    #
    # def get_and_delete_alias(self, slug):
    #     """
    #     Get the URL alias for the provided slug and delete it if exists.
    #
    #     Arguments:
    #         slug (str): slug for which URL alias has to be fetched.
    #     """
    #     alias_list_url = self.get_alias_list_url(slug)
    #     alias_delete_path = self.alias_delete_path(alias_list_url)
    #     if alias_delete_path:
    #         self.delete_alias(alias_delete_path)
    #
    # def update_node_alias(self, obj, node_id, previous_obj):
    #     """
    #     Update alias of the Wordpress post corresponding to the given object.
    #
    #     Arguments:
    #         obj (Program): Program instance to be published.
    #         node_id (str): The ID of the post corresponding to the object.
    #         previous_obj (Program): Previous state of the program. May be None.
    #
    #     Raises:
    #         AliasCreateError: If there's a problem creating a new alias.
    #         AliasDeleteError: If there's a problem deleting an old alias.
    #     """
    #     new_alias = self.alias(obj)
    #     previous_alias = self.alias(previous_obj) if previous_obj else None
    #     new_alias_delete_path = self.alias_delete_path(self.get_alias_list_url(self.get_marketing_slug(obj)))
    #
    #     if new_alias != previous_alias or not new_alias_delete_path:
    #         # Delete old alias before saving the new one.
    #         if previous_obj and self.get_marketing_slug(previous_obj) != self.get_marketing_slug(obj):
    #             self.get_and_delete_alias(self.get_marketing_slug(previous_obj))
    #
    #         headers = {
    #             'content-type': 'application/x-www-form-urlencoded'
    #         }
    #
    #         data = {
    #             **self.alias_form_inputs(self.alias_add_url),
    #             'alias': new_alias,
    #             'form_id': 'path_admin_form',
    #             'op': 'Save',
    #             'source': 'post/{}'.format(node_id),
    #         }
    #
    #         response = self.client.api_session.post(self.alias_add_url, headers=headers, data=data)
    #
    #         if response.status_code != 200:
    #             raise AliasCreateError


class CourseRunMarketingSiteWordpressPublisher(BaseMarketingSiteWordpressPublisher):
    """
    Utility for publishing course run data to a Wordpress marketing site.
    """
    unique_field = 'key'
    post_lookup_field = 'data_locator'
    post_lookup_meta_group = 'open_edx_meta'

    def publish_obj(self, obj, previous_obj=None):
        """
        Publish a CourseRun to the marketing site.

        Publication only occurs if the CourseRun's status has changed.

        Arguments:
            obj (CourseRun): CourseRun instance to be published.

        Keyword Arguments:
            previous_obj (CourseRun): Previous state of the course run. Inspected to
                determine if publication is necessary. May not exist if the course run
                is being saved for the first time.
        """
        logger.info('Publishing course run [%s] to marketing site (Wordpress) ...', obj.key)

        # if previous_obj and obj.status != previous_obj.status:
        post_id = self.post_id(obj)

        post_data = self.serialize_obj(obj)

        self.edit_post(post_id, post_data)


    #
    #     # let's check if it exists on the marketing site
    #     node_id = self.node_id(obj)
    #
    #     if node_id:
    #         # The post exists on marketing site
    #         if previous_obj and obj.status == previous_obj.status:
    #             logger.info(
    #                 'The status of course run [%s] has not changed. It will NOT be published to the marketing site.',
    #                 obj.key)
    #         else:
    #             node_data = self.serialize_obj(obj)
    #             self.edit_node(node_id, node_data)
    #     elif waffle.switch_is_active('auto_course_about_page_creation'):
    #         node_data = self.serialize_obj(obj)
    #         # We also want to push the course uuid during creation so the post is sourcing
    #         # course about data from discovery
    #         node_data.update({'field_course_uuid': str(obj.uuid)})
    #         node_id = self.create_node(node_data)
    #         logger.info('Created new marketing site post [%s] for course run [%s].', node_id, obj.key)
    #         self.update_node_alias(obj, node_id, previous_obj)
    #

    # def serialize_media(self, obj):
    #     """
    #     Serialized the CourseRun instance to be published to Wordpress as media.
    #
    #     # https://developer.wordpress.org/rest-api/reference/media/#create-a-media-item
    #
    #     Arguments:
    #         obj (CourseRun): CourseRun instance to be published.
    #
    #     Returns:
    #         dict: Data to PUT to the Wordpress API (/media)
    #     """
    #     filename = os.path.basename(urlparse(obj.card_image_url).path).split('@')[-1]
    #     data = {}
    #     data['filename'] = filename
    #     data['slug'] = filename.split('.')[0]
    #     data['status'] = 'publish'
    #     data['title'] = filename.split('.')[0]
    #     data['author'] = self.client.user_id
    #     data['comment_status'] = 'open'
    #     data['ping_status'] = 'closed'
    #     data['alt_text'] = ''.join('{word} '.format(word=word.capitalize()) for word in filename.split('.')[0].replace("-", " ").split()).rstrip()
    #     data['caption'] = data['alt_text']
    #     data['description'] = 'Course Card Image for {course}'.format(course=obj.key)
    #
    #     return {
    #         **data,
    #     }

    def serialize_obj(self, obj):
        """
        Serialize the CourseRun instance to be published to Wordpress as custom post type 'course'.

        Arguments:
            obj (CourseRun): CourseRun instance to be published.

        Returns:
            dict: Data to PUT to the Wordpress API (/course)
        """
        data = super().serialize_obj(obj)
        data['title'] = obj.title

        # try:
        #     data['fields']['hero'] = self.media_id(obj)
        # except MediaLookupError:
        #     # logger.warning('Could not find course run [%s]', course_run_key)
        #
        #     # Create media content on Wordpress if it doesn't exist.
        #     obj.wordpress_media_id = data['fields']['hero'] = self.create_media(self.serialize_media(obj))
        #     obj.save()


        data['fields']['short_description'] = obj.short_description
        data['fields']['content_overview'] = obj.full_description

        #Todo: Need to include 'course_modules', 'average_length', 'effort'

        data['fields'][self.post_lookup_meta_group].update(
            {
                'registration_url': "{base}/register?course_id={course_id}&enrollment_action=enroll".format(base=self.partner.lms_url, course_id=str(getattr(obj, self.unique_field))),
                'card_image': obj.card_image_url
            })


        return {
            **data,
            # 'status': 1 if obj.status == CourseRunStatus.Published else 0,
            # 'title': obj.title,
            # 'field_course_id': obj.key,
            # 'type': 'course',
        }
    #
    # def get_marketing_slug(self, obj):
    #     return obj.slug
    #
    # def alias(self, obj):
    #     return 'course/{slug}'.format(slug=self.get_marketing_slug(obj))


class ProgramMarketingSiteWordpressPublisher(BaseMarketingSiteWordpressPublisher):
    """
    Utility for publishing program data to a Wordpress marketing site.
    """

    pass

#     unique_field = 'uuid'
#     node_lookup_field = 'field_uuid'
#
#     def publish_obj(self, obj, previous_obj=None):
#         """
#         Publish a Program to the marketing site.
#
#         Arguments:
#             obj (Program): Program instance to be published.
#
#         Keyword Arguments:
#             previous_obj (Program): Previous state of the program. Inspected to
#                 determine if publication is necessary. May not exist if the program
#                 is being saved for the first time.
#         """
#         types_to_publish = {
#             'XSeries',
#             'MicroMasters',
#             'Professional Certificate',
#             'Masters',
#         }
#
#         if obj.type.name in types_to_publish:
#             node_data = self.serialize_obj(obj)
#
#             node_id = None
#             if not previous_obj:
#                 node_id = self.create_node(node_data)
#             else:
#                 trigger_fields = (
#                     'marketing_slug',
#                     'status',
#                     'title',
#                     'type',
#                 )
#
#                 if any(getattr(obj, field) != getattr(previous_obj, field) for field in trigger_fields):
#                     node_id = self.node_id(obj)
#                     # Wordpress does not allow modification of the UUID field.
#                     node_data.pop('uuid', None)
#
#                     self.edit_node(node_id, node_data)
#
#             if node_id:
#                 self.get_and_delete_alias(slugify(obj.title))
#                 self.update_node_alias(obj, node_id, previous_obj)
#
#     def serialize_obj(self, obj):
#         """
#         Serialize the Program instance to be published.
#
#         Arguments:
#             obj (Program): Program instance to be published.
#
#         Returns:
#             dict: Data to PUT to the Wordpress API.
#         """
#         data = super().serialize_obj(obj)
#
#         return {
#             **data,
#             'status': 1 if obj.is_active else 0,
#             'title': obj.title,
#             'type': str(obj.type).lower().replace(' ', '_'),
#             'uuid': str(obj.uuid),
#         }
