import logging

import waffle

from course_discovery.apps.course_metadata.models import Course, CourseRun as CourseRunMetaData
# from course_discovery.apps.publisher.models import CourseRun

logger = logging.getLogger(__name__)


def get_and_update_course_runs(): #start_id, end_id
    """ Execute query according to the range."""

    for course_run in CourseRun.objects.active().enrollable().marketable(): #CourseRunMetaData.objects.filter():  #id__range=(start_id, end_id)
        update_course_run(course_run)


def update_course_run(course_run_metadata):
    """ Update the publisher course."""
    try:
        if course_run_metadata.key:
            create_or_update_course(course_run_metadata)
            logger.info(
                'Update course-run import with id [%s], key [%s].',
                course_run_metadata.id, course_run_metadata.key
            )

    except:  # pylint: disable=bare-except
        logger.error('Exception appear in updating course-run-id [%s].', course_run_metadata.pk)


def create_or_update_course(course_run_metadata):
    """ Create or Update new Course content on the Wordpress frontend using ACF REST API"""

    # suppress_publication = kwargs.pop('suppress_publication', False)
    is_publishable = (
            course_run_metadata.partner.has_marketing_site and
            waffle.switch_is_active('publish_course_runs_to_marketing_site_wordpress')
            # Pop to clean the kwargs for the base class save call below
            #and not suppress_publication
    )

    if is_publishable:
        publisher = CourseRunMarketingSiteWordpressPublisher(course_run_metadata.partner)

        publisher.publish_obj(course_run_metadata)

        # previous_obj = CourseRun.objects.get(id=self.id) if self.id else None

        # with transaction.atomic():
        #     super(CourseRun, self).save(*args, **kwargs)
        #     publisher.publish_obj(self, previous_obj=previous_obj)
    # else:
    #     super(CourseRun, self).save(*args, **kwargs)

