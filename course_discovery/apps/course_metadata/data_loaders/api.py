import concurrent.futures
import logging
import math
import time
from decimal import Decimal
from io import BytesIO

import requests
from django.core.files import File
from opaque_keys.edx.keys import CourseKey

from course_discovery.apps.core.models import Currency
from course_discovery.apps.course_metadata.choices import CourseRunPacing, CourseRunStatus
from course_discovery.apps.course_metadata.data_loaders import AbstractDataLoader
from course_discovery.apps.course_metadata.models import (
    Course, CourseEntitlement, CourseRun, Chapter, Sequential, Organization, Program, ProgramType, Seat, SeatType, Video
)

logger = logging.getLogger(__name__)


class OrganizationsApiDataLoader(AbstractDataLoader):
    """ Loads organizations from the Organizations API. """

    def ingest(self):
        api_url = self.partner.organizations_api_url
        count = None
        page = 1

        logger.info('Refreshing Organizations from %s...', api_url)

        while page:
            response = self.api_client.organizations().get(page=page, page_size=self.PAGE_SIZE)
            count = response['count']
            results = response['results']
            logger.info('Retrieved %d organizations...', len(results))

            if response['next']:
                page += 1
            else:
                page = None
            for body in results:
                body = self.clean_strings(body)
                self.update_organization(body)

        logger.info('Retrieved %d organizations from %s.', count, api_url)

        self.delete_orphans()

    def update_organization(self, body):
        key = body['short_name']
        logo = body['logo']

        defaults = {
            'key': key,
            'partner': self.partner,
            'certificate_logo_image_url': logo,
        }

        if not self.partner.has_marketing_site:
            defaults.update({
                'name': body['name'],
                'description': body['description'],
                'logo_image_url': logo,
            })

        Organization.objects.update_or_create(key__iexact=key, partner=self.partner, defaults=defaults)
        logger.info('Processed organization "%s"', key)


class CoursesApiDataLoader(AbstractDataLoader):
    """ Loads course runs from the Courses API. """

    BLOCK_COURSE = 'course'
    BLOCK_CHAPTER = 'chapter'
    BLOCK_SEQUENTIAL = 'sequential'

    def ingest(self):
        logger.info('Refreshing Courses, CourseRuns, Chapters, and Sequentials from %s...', self.partner.courses_api_url)

        initial_page = 1
        response = self._make_request_courses(initial_page)
        count = response['pagination']['count']
        pages = response['pagination']['num_pages']
        self._process_response_courses(response)

        pagerange = range(initial_page + 1, pages + 1)

        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:  # pragma: no cover
            if self.is_threadsafe:
                for page in pagerange:
                    # This time.sleep is to make it very likely that this method does not encounter a 429 status
                    # code by increasing the amount of time between each code. More details at LEARNER-5560
                    # The current crude estimation is for ~3000 courses with a PAGE_SIZE=50 which means this method
                    # will take ~30 minutes.
                    # TODO Ticket to gracefully handle 429 https://openedx.atlassian.net/browse/LEARNER-5565
                    time.sleep(30)
                    executor.submit(self._load_data_courses, page)
            else:
                for future in [executor.submit(self._make_request_courses, page) for page in pagerange]:
                    # This time.sleep is to make it very likely that this method does not encounter a 429 status
                    # code by increasing the amount of time between each code. More details at LEARNER-5560
                    # The current crude estimation is for ~3000 courses with a PAGE_SIZE=50 which means this method
                    # will take ~30 minutes.
                    # TODO Ticket to gracefully handle 429 https://openedx.atlassian.net/browse/LEARNER-5565
                    time.sleep(30)
                    response = future.result()
                    self._process_response_courses(response)

        logger.info('Retrieved %d course runs from %s.', count, self.partner.courses_api_url)

        self.delete_orphans()

    def _load_data_courses(self, page):  # pragma: no cover
        """Make a request for the given page and process the response."""
        response = self._make_request_courses(page)
        self._process_response_courses(response)

    def _make_request_courses(self, page):
        return self.api_client.courses().get(page=page, page_size=self.PAGE_SIZE, username=self.username)

    def _load_data_blocks(self, course_run_id, block_type):  # pragma: no cover
        """
        Make a request for the given course and process the block type (chapter, sequential) response.
        Need to pass in parent_block_type because the Block REST API won't show children field values.
        """
        block_type_filter_selector = {
            self.BLOCK_SEQUENTIAL: block_type,
            self.BLOCK_CHAPTER: block_type + ',' + self.BLOCK_SEQUENTIAL,
            self.BLOCK_COURSE: block_type + ',' + self.BLOCK_CHAPTER
        }

        response = self._make_request_blocks(
            course_id=course_run_id,
            depth='3',
            block_types_filter=block_type_filter_selector.get(block_type, ''),
            requested_fields='children,display_name,type,due,graded,special_exam_info,format'
        )
        self._process_response_blocks(response, block_type, course_run_id)

    def _make_request_blocks(self, course_id, depth, block_types_filter, requested_fields):
        return self.api_client.blocks().get(
            username=self.username, course_id=course_id, depth=depth, block_types_filter=block_types_filter,
            requested_fields=requested_fields
        )

    def _process_response_courses(self, response):
        """ Process Courses """
        results = response['results']
        logger.info('Retrieved %d course runs...', len(results))

        """
        Deleting old Courses from `course-discovery` store and/or marketing frontend that were 
        removed from the CMS before adding new ones. The LMS Course REST API can show a limited subset of the existing 
        courses should the `lms_catalog_service_user` account not have `Staff` enabled.
        """
        # Hide courses that are not in the response. This is an indicator that the course has been removed from the CMS.
        course_response_locations = []
        for body in results:
            course_response_locations.append(body['id'])

        for course in CourseRun.objects.all():

            if course.key not in course_response_locations:
                course.delete()

        """
        Add changes for new Courses or update exist ones to `course-discovery` store and/or publish to 
        marketing frontend.
        """
        for body in results:
            course_run_id = body['id']

            """
            Continue to next course should the existing course be hidden (e.g. `none`, `about`) from the catalog using 
            the `Course Visibility In Catalog` advanced setting for that configuration. At this point we'd like to
            skip the hidden course(s) from storing data within the `course-discovery` store or publishing them on
            marketing frontend (Wordpress). Should the `lms_catalog_service_user` used for connecting with the
            LMS Course/Block REST API have access to Staff mode it would allow them to retrieve a payload of all
            courses information regardless of this advanced setting being set to show on the catalog (eg. `both`).
            """
            if body['hidden']:
                continue

            try:
                body = self.clean_strings(body)
                course_run = self.get_course_run(body)
                if course_run:
                    self.update_course_run(course_run, body)
                    course = getattr(course_run, 'canonical_for_course', False)
                    if course and not self.partner.has_marketing_site:
                        # If the partner have marketing site,
                        # we should only update the course information from the marketing site.
                        # Therefore, we don't need to do the statements below
                        course = self.update_course(course, body)
                        logger.info('Processed course with key [%s].', course.key)
                else:
                    course, created = self.get_or_create_course(body)
                    course_run = self.create_course_run(course, body)
                    if created:
                        course.canonical_course_run = course_run
                        course.save()
            except:  # pylint: disable=bare-except
                msg = 'An error occurred while updating {course_run} from {api_url}'.format(
                    course_run=course_run_id,
                    api_url=self.partner.courses_api_url
                )
                logger.exception(msg)
                continue

            # Load sequential block data for the course run; load this first since chapters depend on it.
            self._load_data_blocks(course_run_id, self.BLOCK_SEQUENTIAL)

            # Load chapter block data for the course run
            self._load_data_blocks(course_run_id, self.BLOCK_CHAPTER)

            # Load chapter block data to find children (chapters) and update the order.
            self._load_data_blocks(course_run_id, self.BLOCK_COURSE)

    def _process_response_blocks(self, response, block_type_update, course_id):
        """ Process Course Run Block Type (chapters, sequentials) """

        blocks = response['blocks']
        logger.info('Retrieved %d blocks for %s update ...', len(blocks), block_type_update)


        """
        Remove any old Sequentials and Chapters from `course-discovery` store and/or marketing frontend that were 
        removed from the course before adding new ones.
        """

        if block_type_update == self.BLOCK_SEQUENTIAL:
            # Delete blocks that are not in the response. This is an indicator that the blocks have been removed from the course.
            block_response_locations = []
            for block_key, block_body in blocks.items():
                block_response_locations.append(block_body['id'])

            for sequential in Sequential.objects.select_related().filter(course_run__key=course_id):

                if sequential.location not in block_response_locations:
                    sequential.delete()

        if block_type_update == self.BLOCK_CHAPTER:
            # Delete blocks that are not in the response. This is an indicator that the blocks have been removed from the course.
            block_response_locations = []
            for block_key, block_body in blocks.items():
                block_response_locations.append(block_body['id'])

            for chapter in Chapter.objects.select_related().filter(course_run__key=course_id):

                if chapter.location not in block_response_locations:
                    chapter.delete()

        """
        Add changes for new Sequentials and Chapters or update exist ones to `course-discovery` store and/or publish to 
        marketing frontend.
        """
        for block_key, block_body in blocks.items():
            block_location_id = block_body['id']

            try:
                block_body = self.clean_strings(block_body)
                block_type = block_body['type']

                # Verify that the Block REST API returns the correct type before parsing and updating the model.
                if block_type == block_type_update and (
                        block_type == self.BLOCK_SEQUENTIAL or
                        block_type == self.BLOCK_CHAPTER or
                        block_type == self.BLOCK_COURSE):

                    if block_type == self.BLOCK_COURSE:
                        block_type_model = self.get_block_location(course_id, block_body['type'])
                    else:
                        block_type_model = self.get_block_location(block_body['id'], block_body['type'])

                    if block_type_model:
                        logger.info('Found existing %s', block_key)

                        if block_type == self.BLOCK_SEQUENTIAL:
                            self.update_sequential(block_type_model, block_body, course_id)

                        if block_type == self.BLOCK_CHAPTER:
                            self.update_chapter(block_type_model, block_body, course_id)

                        # We're only updating the courses children (Chapters) relationship on update assuming the
                        # course has already been created here.
                        if block_type == self.BLOCK_COURSE:
                            if 'children' in block_body:
                                self.update_course_chapters(block_type_model, block_body)

                    else:
                        logger.info('Could not find an existing %s', block_key)

                        if block_type == self.BLOCK_SEQUENTIAL:
                            self.create_sequential(block_body, course_id)

                        if block_type == self.BLOCK_CHAPTER:
                            self.create_chapter(block_body, course_id)

                else:
                    logger.info("Not able to process a %s block response for %s", block_type, block_key)

            except:  # pylint: disable=bare-except
                msg = 'An error occurred while updating {block_location} from {api_url}'.format(
                    block_location=block_location_id,
                    api_url=self.partner.courses_api_url
                )
                logger.exception(msg)
                continue


    def get_block_location(self, block_location, block_type):
        try:
            if block_type == self.BLOCK_SEQUENTIAL:
                return Sequential.objects.get(location__iexact=block_location)

            elif block_type == self.BLOCK_CHAPTER:
                return Chapter.objects.get(location__iexact=block_location)

            elif block_type == self.BLOCK_COURSE:
                # Since the CourseRun doesn't include a block location identifier we have to use the key field
                # to compare that against what the block_location sends from the Block REST API.
                # course_key = "course-v1:"
                # key_parts = block_location.split(':')[-1].split('+')[:3]
                # for parts in key_parts:
                #     course_key += parts + "+"
                #
                # return CourseRun.objects.get(key__iexact=course_key[:-1])
                return CourseRun.objects.get(key__iexact=block_location)

        except (Sequential.DoesNotExist, Chapter.DoesNotExist) as error:
            return None

    def update_sequential(self, sequential, block_body, course_id):
        validated_data = self.format_sequential_data(block_body, course_id)
        self._update_instance(sequential, validated_data) # , suppress_publication=True

        logger.info('Processed sequential with UUID [%s].', sequential.uuid)

    def create_sequential(self, block_body, course_id):
        defaults = self.format_sequential_data(block_body, course_id)

        sequential = Sequential.objects.create(**defaults)

        if sequential:
            sequential.save()

    def format_sequential_data(self, block_body, course_id):
        defaults = {
            'course_run': self.get_course_run(body={"id": course_id}),
            'location': block_body['id'],
            'lms_web_url': block_body['lms_web_url'],
            'title': self.get_title_name(block_body['display_name']),
            'slug': self.get_slug_name(block_body['display_name'], course_id, block_body['block_id']),
            'hidden': False
        }

        return defaults

    def _update_chapter_sequentials(self, chapter, block_body):
        sequentials = []
        chapter_order = 0

        for child in block_body['children']:
            sequentional_block_model = self.get_block_location(child, self.BLOCK_SEQUENTIAL)
            if sequentional_block_model:
                # Assign an order presented by the Block REST API to be used as identifier for order on marketing
                # front end. The SortedManyToManyField has `sort_value` but I couldn't figure how to get this to work.
                setattr(sequentional_block_model, 'chapter_order', chapter_order)
                sequentional_block_model.save(suppress_publication=True)
                chapter_order += 1

                sequentials.append(sequentional_block_model)

        # Assign the Sequentials from Block REST API to the Chapter model instance.
        if sequentials:
            setattr(chapter, 'sequentials', sequentials)
            chapter.save(suppress_publication=True)

    def update_chapter(self, chapter, block_body, course_id):
        validated_data = self.format_chapter_data(block_body, course_id)

        if 'children' in block_body:
            self._update_chapter_sequentials(chapter, block_body)

        self._update_instance(chapter, validated_data) # , suppress_publication=True

        logger.info('Processed chapter with UUID [%s].', chapter.uuid)

    def create_chapter(self, block_body, course_id):
        defaults = self.format_chapter_data(block_body, course_id)

        chapter = Chapter.objects.create(**defaults)

        if chapter:
            self._update_chapter_sequentials(chapter, block_body)
            chapter.save()

    def format_chapter_data(self, block_body, course_id):
        defaults = {
            'course_run': self.get_course_run(body={"id": course_id}),
            'location': block_body['id'],
            'lms_web_url': block_body['lms_web_url'],
            'title': self.get_title_name(block_body['display_name']),
            'slug': self.get_slug_name(block_body['display_name'], course_id, block_body['block_id']),
            'hidden': False
        }

        return defaults

    def get_course_run(self, body):
        course_run_key = body['id']
        try:
            return CourseRun.objects.get(key__iexact=course_run_key)
        except CourseRun.DoesNotExist:
            return None

    def update_course_chapters(self, course_run, block_body):
        chapters = []
        course_order = 0

        for child in block_body['children']:
            chapter_block_model = self.get_block_location(child, self.BLOCK_CHAPTER)
            if chapter_block_model:
                # Assign an order presented by the Block REST API to be used as identifier for order on marketing
                # front end. The SortedManyToManyField has `sort_value` but I couldn't figure how to get this to work.
                setattr(chapter_block_model, 'course_order', course_order)
                chapter_block_model.save(suppress_publication=True)
                course_order += 1

                chapters.append(chapter_block_model)

        # Assign the Chapters from Block REST API to the Course Run model instance.
        if chapters:
            setattr(course_run, 'chapters', chapters)
            course_run.save()  # suppress_publication=True

    def update_course_run(self, course_run, body):
        validated_data = self.format_course_run_data(body)
        self._update_instance(course_run, validated_data, suppress_publication=True)

        logger.info('Processed course run with UUID [%s].', course_run.uuid)

    def create_course_run(self, course, body):
        defaults = self.format_course_run_data(body, course=course)

        return CourseRun.objects.create(**defaults)

    def get_or_create_course(self, body):
        course_run_key = CourseKey.from_string(body['id'])
        course_key = self.get_course_key_from_course_run_key(course_run_key)
        defaults = self.format_course_data(body)
        # We need to add the key to the defaults because django ignores kwargs with __
        # separators when constructing the create request
        defaults['key'] = course_key
        defaults['partner'] = self.partner

        course, created = Course.objects.get_or_create(key__iexact=course_key, partner=self.partner, defaults=defaults)

        if created:
            # NOTE (CCB): Use the data from the CourseKey since the Course API exposes display names for org and number,
            # which may not be unique for an organization.
            key = course_run_key.org
            defaults = {'key': key}
            organization, __ = Organization.objects.get_or_create(key__iexact=key, partner=self.partner,
                                                                  defaults=defaults)

            course.authoring_organizations.add(organization)

        return (course, created)

    def update_course(self, course, body):
        validated_data = self.format_course_data(body)
        self._update_instance(course, validated_data)

        logger.info('Processed course with key [%s].', course.key)

        return course

    def _update_instance(self, instance, validated_data, **kwargs):
        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.save(**kwargs)

    def format_course_run_data(self, body, course=None):
        defaults = {
            'key': body['id'],
            'end': self.parse_date(body['end']),
            'enrollment_start': self.parse_date(body['enrollment_start']),
            'enrollment_end': self.parse_date(body['enrollment_end']),
            'slug': self.get_slug_name(body['name'], body["id"], 'course'),
            'hidden': body.get('hidden', False),
        }

        # NOTE: The license field is non-nullable.
        defaults['license'] = body.get('license') or ''

        # When using a marketing site, only dates (excluding start) should come from the Course API.
        # if not self.partner.has_marketing_site:
        defaults.update({
            'start': self.parse_date(body['start']),
            'card_image_url': body['media'].get('image', {}).get('raw'),
            'title_override': body['name'],
            'short_description_override': body['short_description'],
            'full_description_override': self.api_client.courses(body['id']).get(username=self.username)["overview"],
            'video': self.get_courserun_video(body),
            'status': CourseRunStatus.Published,
            'pacing_type': self.get_pacing_type(body),
            'mobile_available': body.get('mobile_available') or False,
        })

        if course:
            defaults['course'] = course

        return defaults

    def format_course_data(self, body):
        defaults = {
            'title': body['name'],
        }

        return defaults

    def get_pacing_type(self, body):
        pacing = body.get('pacing')

        if pacing:
            pacing = pacing.lower()

        if pacing == 'instructor':
            return CourseRunPacing.Instructor
        elif pacing == 'self':
            return CourseRunPacing.Self
        else:
            return None

    def get_courserun_video(self, body):
        video = None
        video_url = body['media'].get('course_video', {}).get('uri')

        if video_url:
            video, __ = Video.objects.get_or_create(src=video_url)

        return video


class EcommerceApiDataLoader(AbstractDataLoader):
    """ Loads course seats, entitlements, and enrollment codes from the E-Commerce API. """

    def __init__(self, partner, api_url, access_token=None, token_type=None, max_workers=None,
                 is_threadsafe=False, **kwargs):
        super(EcommerceApiDataLoader, self).__init__(
            partner, api_url, access_token, token_type, max_workers, is_threadsafe, **kwargs
        )
        self.initial_page = 1
        self.enrollment_skus = []
        self.entitlement_skus = []

    def ingest(self):
        logger.info('Refreshing course seats from %s...', self.partner.ecommerce_api_url)
        course_runs = self._request_course_runs(self.initial_page)
        entitlements = self._request_entitlments(self.initial_page)
        enrollment_codes = self._request_enrollment_codes(self.initial_page)
        self.entitlement_skus = []
        self.enrollment_skus = []
        self._process_course_runs(course_runs)
        self._process_entitlements(entitlements)
        self._process_enrollment_codes(enrollment_codes)

        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:  # pragma: no cover
            # Create pageranges to iterate over all existing pages for each product type
            pageranges = {
                'course_runs': self._pagerange(course_runs['count']),
                'entitlements': self._pagerange(entitlements['count']),
                'enrollment_codes': self._pagerange(enrollment_codes['count'])
            }

            if self.is_threadsafe:
                for page in pageranges['course_runs']:
                    executor.submit(self._load_course_runs_data, page)
                for page in pageranges['entitlements']:
                    executor.submit(self._load_entitlements_data, page)
                for page in pageranges['enrollment_codes']:
                    executor.submit(self._load_enrollment_codes_data, page)
            else:
                pagerange = pageranges['course_runs']
                for future in [executor.submit(self._request_course_runs, page) for page in pagerange]:
                    response = future.result()
                    self._process_course_runs(response)

                pagerange = pageranges['entitlements']
                for future in [executor.submit(self._request_entitlments, page) for page in pagerange]:
                    response = future.result()
                    self._process_entitlements(response)

                pagerange = pageranges['enrollment_codes']
                for future in [executor.submit(self._request_enrollment_codes, page) for page in pagerange]:
                    response = future.result()
                    self._process_enrollment_codes(response)

        logger.info('Retrieved %d course seats, %d course entitlements, and %d course enrollment codes from %s.',
                    course_runs['count'], entitlements['count'],
                    enrollment_codes['count'], self.partner.ecommerce_api_url)

        self.delete_orphans()
        self._delete_entitlements()

    def _pagerange(self, count):
        pages = math.ceil(count / self.PAGE_SIZE)
        return range(self.initial_page + 1, pages + 1)

    def _load_course_runs_data(self, page):  # pragma: no cover
        """Make a request for the given page and process the response."""
        course_runs = self._request_course_runs(page)
        self._process_course_runs(course_runs)

    def _load_entitlements_data(self, page):  # pragma: no cover
        """Make a request for the given page and process the response."""
        entitlements = self._request_entitlments(page)
        self._process_entitlements(entitlements)

    def _load_enrollment_codes_data(self, page):  # pragma: no cover
        """Make a request for the given page and process the response."""
        enrollment_codes = self._request_enrollment_codes(page)
        self._process_enrollment_codes(enrollment_codes)

    def _request_course_runs(self, page):
        return self.api_client.courses().get(page=page, page_size=self.PAGE_SIZE, include_products=True)

    def _request_entitlments(self, page):
        return self.api_client.products().get(page=page, page_size=self.PAGE_SIZE, product_class='Course Entitlement')

    def _request_enrollment_codes(self, page):
        return self.api_client.products().get(page=page, page_size=self.PAGE_SIZE, product_class='Enrollment Code')

    def _process_course_runs(self, response):
        results = response['results']
        logger.info('Retrieved %d course seats...', len(results))

        for body in results:
            body = self.clean_strings(body)
            self.update_seats(body)

    def _process_entitlements(self, response):
        results = response['results']
        logger.info('Retrieved %d course entitlements...', len(results))

        for body in results:
            body = self.clean_strings(body)
            self.entitlement_skus.append(self.update_entitlement(body))

    def _process_enrollment_codes(self, response):
        results = response['results']
        logger.info('Retrieved %d course enrollment codes...', len(results))

        for body in results:
            body = self.clean_strings(body)
            self.enrollment_skus.append(self.update_enrollment_code(body))

    def _delete_entitlements(self):
        entitlements_to_delete = CourseEntitlement.objects.filter(
            partner=self.partner
        ).exclude(sku__in=self.entitlement_skus)

        for entitlement in entitlements_to_delete:
            msg = 'Deleting entitlement for course {course_title} with sku {sku} for partner {partner}'.format(
                course_title=entitlement.course.title, sku=entitlement.sku, partner=entitlement.partner
            )
            logger.info(msg)
        entitlements_to_delete.delete()

    def update_seats(self, body):
        course_run_key = body['id']
        try:
            course_run = CourseRun.objects.get(key__iexact=course_run_key)
        except CourseRun.DoesNotExist:
            logger.warning('Could not find course run [%s]', course_run_key)
            return None

        for product_body in body['products']:
            if product_body['structure'] != 'child':
                continue
            product_body = self.clean_strings(product_body)
            self.update_seat(course_run, product_body)

        # Remove seats which no longer exist for that course run
        certificate_types = [self.get_certificate_type(product) for product in body['products']
                             if product['structure'] == 'child']
        course_run.seats.exclude(type__in=certificate_types).delete()

    def update_seat(self, course_run, product_body):
        stock_record = product_body['stockrecords'][0]
        currency_code = stock_record['price_currency']
        price = Decimal(stock_record['price_excl_tax'])
        sku = stock_record['partner_sku']

        try:
            currency = Currency.objects.get(code=currency_code)
        except Currency.DoesNotExist:
            logger.warning("Could not find currency [%s]", currency_code)
            return None

        attributes = {attribute['name']: attribute['value'] for attribute in product_body['attribute_values']}

        seat_type = attributes.get('certificate_type', Seat.AUDIT)
        credit_provider = attributes.get('credit_provider')

        credit_hours = attributes.get('credit_hours')
        if credit_hours:
            credit_hours = int(credit_hours)

        defaults = {
            'price': price,
            'sku': sku,
            'upgrade_deadline': self.parse_date(product_body.get('expires')),
            'credit_hours': credit_hours,
        }

        course_run.seats.update_or_create(
            type=seat_type,
            credit_provider=credit_provider,
            currency=currency,
            defaults=defaults
        )

    def validate_stockrecord(self, stockrecords, title, product_class):
        """
        Argument:
            body (dict): product data from ecommerce, either entitlement or enrollment code
        Returns:
            product sku if no exceptions, else None
        """
        # Map product_class keys with how they should be displayed in the exception messages.
        product_classes = {
            'entitlement': {
                'name': 'entitlement',
                'value': 'entitlement',
            },
            'enrollment_code': {
                'name': 'enrollment_code',
                'value': 'enrollment code'
            }
        }

        try:
            product_class = product_classes[product_class]
        except (KeyError, ValueError):
            msg = 'Invalid product class of {product}. Must be entitlement or enrollment_code'.format(
                product=product_class['name']
            )
            logger.warning(msg)
            return None

        if stockrecords:
            stock_record = stockrecords[0]
        else:
            msg = '{product} product {title} has no stockrecords'.format(
                product=product_class['value'].capitalize(),
                title=title
            )
            logger.warning(msg)
            return None

        try:
            currency_code = stock_record['price_currency']
            Decimal(stock_record['price_excl_tax'])
            sku = stock_record['partner_sku']
        except (KeyError, ValueError):
            msg = 'A necessary stockrecord field is missing or incorrectly set for {product} {title}'.format(
                product=product_class['value'],
                title=title
            )
            logger.warning(msg)
            return None

        try:
            Currency.objects.get(code=currency_code)
        except Currency.DoesNotExist:
            msg = 'Could not find currency {code} while loading {product} {title} with sku {sku}'.format(
                product=product_class['value'], code=currency_code, title=title, sku=sku
            )
            logger.warning(msg)
            return None

        # All validation checks passed!
        return True

    def update_entitlement(self, body):
        """
        Argument:
            body (dict): entitlement product data from ecommerce
        Returns:
            entitlement product sku if no exceptions, else None
        """
        attributes = {attribute['name']: attribute['value'] for attribute in body['attribute_values']}
        course_uuid = attributes.get('UUID')
        title = body['title']
        stockrecords = body['stockrecords']

        if not self.validate_stockrecord(stockrecords, title, 'entitlement'):
            return None

        stock_record = stockrecords[0]
        currency_code = stock_record['price_currency']
        price = Decimal(stock_record['price_excl_tax'])
        sku = stock_record['partner_sku']

        try:
            course = Course.objects.get(uuid=course_uuid)
        except Course.DoesNotExist:
            msg = 'Could not find course {uuid} while loading entitlement {title} with sku {sku}'.format(
                uuid=course_uuid, title=title, sku=sku
            )
            logger.warning(msg)
            return None

        try:
            currency = Currency.objects.get(code=currency_code)
        except Currency.DoesNotExist:
            msg = 'Could not find currency {code} while loading entitlement {title} with sku {sku}'.format(
                code=currency_code, title=title, sku=sku
            )
            logger.warning(msg)
            return None

        mode_name = attributes.get('certificate_type')
        try:
            mode = SeatType.objects.get(slug=mode_name)
        except SeatType.DoesNotExist:
            msg = 'Could not find mode {mode} while loading entitlement {title} with sku {sku}'.format(
                mode=mode_name, title=title, sku=sku
            )
            logger.warning(msg)
            return None

        defaults = {
            'partner': self.partner,
            'price': price,
            'currency': currency,
            'sku': sku,
            'expires': self.parse_date(body['expires'])
        }
        msg = 'Creating entitlement {title} with sku {sku} for partner {partner}'.format(
            title=title, sku=sku, partner=self.partner
        )
        logger.info(msg)
        course.entitlements.update_or_create(mode=mode, defaults=defaults)
        return sku

    def update_enrollment_code(self, body):
        """
        Argument:
            body (dict): enrollment code product data from ecommerce
        Returns:
            enrollment code product sku if no exceptions, else None
        """
        attributes = {attribute['code']: attribute['value'] for attribute in body['attribute_values']}
        course_key = attributes.get('course_key')
        title = body['title']
        stockrecords = body['stockrecords']

        if not self.validate_stockrecord(stockrecords, title, "enrollment_code"):
            return None

        stock_record = stockrecords[0]
        sku = stock_record['partner_sku']

        try:
            course_run = CourseRun.objects.get(key=course_key)
        except CourseRun.DoesNotExist:
            msg = 'Could not find course run {key} while loading enrollment code {title} with sku {sku}'.format(
                key=course_key, title=title, sku=sku
            )
            logger.warning(msg)
            return None

        seat_type = attributes.get('seat_type')
        try:
            Seat.objects.get(course_run=course_run, type=seat_type)
        except Seat.DoesNotExist:
            msg = 'Could not find seat type {type} while loading enrollment code {title} with sku {sku}'.format(
                type=seat_type, title=title, sku=sku
            )
            logger.warning(msg)
            return None

        defaults = {
            'bulk_sku': sku
        }
        msg = 'Creating enrollment code {title} with sku {sku} for partner {partner}'.format(
            title=title, sku=sku, partner=self.partner
        )
        logger.info(msg)
        course_run.seats.update_or_create(type=seat_type, defaults=defaults)
        return sku

    def get_certificate_type(self, product):
        return next(
            (att['value'] for att in product['attribute_values'] if att['name'] == 'certificate_type'),
            Seat.AUDIT
        )


class ProgramsApiDataLoader(AbstractDataLoader):
    """ Loads programs from the Programs API. """
    image_width = 1440
    image_height = 480
    XSERIES = None

    def __init__(self, partner, api_url, access_token=None, token_type=None, max_workers=None,
                 is_threadsafe=False, **kwargs):
        super(ProgramsApiDataLoader, self).__init__(
            partner, api_url, access_token, token_type, max_workers, is_threadsafe, **kwargs
        )
        self.XSERIES = ProgramType.objects.get(name='XSeries')

    def ingest(self):
        api_url = self.partner.programs_api_url
        count = None
        page = 1

        logger.info('Refreshing programs from %s...', api_url)

        while page:
            response = self.api_client.programs.get(page=page, page_size=self.PAGE_SIZE)
            count = response['count']
            results = response['results']
            logger.info('Retrieved %d programs...', len(results))

            if response['next']:
                page += 1
            else:
                page = None

            for program in results:
                program = self.clean_strings(program)
                self.update_program(program)

        logger.info('Retrieved %d programs from %s.', count, api_url)

    def _get_uuid(self, body):
        return body['uuid']

    def update_program(self, body):
        uuid = self._get_uuid(body)

        try:
            defaults = {
                'uuid': uuid,
                'title': body['name'],
                'subtitle': body['subtitle'],
                'type': self.XSERIES,
                'status': body['status'],
                'banner_image_url': self._get_banner_image_url(body),
            }

            program, __ = Program.objects.update_or_create(
                marketing_slug=body['marketing_slug'],
                partner=self.partner,
                defaults=defaults
            )
            self._update_program_organizations(body, program)
            self._update_program_courses_and_runs(body, program)
            self._update_program_banner_image(body, program)
            program.save()
        except Exception:  # pylint: disable=broad-except
            logger.exception('Failed to load program %s', uuid)

    def _update_program_courses_and_runs(self, body, program):
        course_run_keys = set()
        for course_code in body.get('course_codes', []):
            course_run_keys.update([course_run['course_key'] for course_run in course_code['run_modes']])

        # The course_code key field is technically useless, so we must build the course list from the
        # associated course runs.
        courses = Course.objects.filter(course_runs__key__in=course_run_keys).distinct()
        program.courses.clear()
        program.courses.add(*courses)

        # Do a diff of all the course runs and the explicitly-associated course runs to determine
        # which course runs should be explicitly excluded.
        excluded_course_runs = CourseRun.objects.filter(course__in=courses).exclude(key__in=course_run_keys)
        program.excluded_course_runs.clear()
        program.excluded_course_runs.add(*excluded_course_runs)

    def _update_program_organizations(self, body, program):
        uuid = self._get_uuid(body)
        org_keys = [org['key'] for org in body['organizations']]
        organizations = Organization.objects.filter(key__in=org_keys, partner=self.partner)

        if len(org_keys) != organizations.count():
            logger.error('Organizations for program [%s] are invalid!', uuid)

        program.authoring_organizations.clear()
        program.authoring_organizations.add(*organizations)

    def _get_banner_image_url(self, body):
        image_key = 'w{width}h{height}'.format(width=self.image_width, height=self.image_height)
        image_url = body.get('banner_image_urls', {}).get(image_key)
        return image_url

    def _update_program_banner_image(self, body, program):
        image_url = self._get_banner_image_url(body)
        if not image_url:
            logger.warning('There are no banner image url for program %s', program.title)
            return

        r = requests.get(image_url)
        if r.status_code == 200:
            banner_downloaded = File(BytesIO(r.content))
            program.banner_image.save(
                'banner.jpg',
                banner_downloaded
            )
            program.save()
        else:
            logger.exception('Loading the banner image %s for program %s failed', image_url, program.title)
