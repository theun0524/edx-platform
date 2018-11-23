""" Command line script to change credit course eligibility deadline. """

import logging
from datetime import datetime, timedelta

from django.core.management.base import BaseCommand, CommandError
from opaque_keys import InvalidKeyError
from opaque_keys.edx.keys import CourseKey
from student.models import CourseEnrollment, User

from openedx.core.djangoapps.credit.models import CreditEligibility

logger = logging.getLogger(__name__)  # pylint: disable=invalid-name

DEFAULT_DAYS = 30


class IncorrectDeadline(Exception):
    """
    Exception raised explicitly to use default date when date given by user is prior to today.
    """
    pass


class Command(BaseCommand):

    help = """
    
    Changes the credit course eligibility deadline for a student 
    in a particular course.
    
    """

    def add_arguments(self, parser):
        parser.add_argument('-u', '--username',
                            metavar='USERNAME',
                            required=True,
                            help='username of the student')
        parser.add_argument('-d', '--date',
                            dest='deadline',
                            metavar='DEADLINE',
                            help='Desired eligibility deadline for credit course')
        parser.add_argument('-c', '--course',
                            metavar='COURSE_ID',
                            dest='course_id',
                            required=True,
                            help='Course ID')

    def handle(self, *args, **options):
        username = options['username']
        course_id = options['course_id']

        try:
            user_id = int(User.objects.get(username=username).pk)
        except User.DoesNotExist:
            raise CommandError('Invalid or non-existent username {}'.format(username))

        try:
            course_key = CourseKey.from_string(course_id)
            CourseEnrollment.objects.filter(user_id=user_id, course_id=course_key, mode='credit')
        except InvalidKeyError:
            raise CommandError('Invalid or non-existent course id {}'.format(course_id))
        except CourseEnrollment.DoesNotExist:
            raise CommandError('No record found in database for {username} in course {course_id}'
                               .format(username=username, course_id=course_id))

        try:
            expected_date = datetime.strptime(options['deadline'], '%Y-%m-%d')
            current_date = datetime.now()
            if expected_date < current_date:
                raise IncorrectDeadline('Incorrect Deadline')

        except (ValueError, InvalidKeyError):
            CommandError('Invalid format or date not provided. Setting deadline to one month from now')
            expected_date = datetime.now() + timedelta(days=DEFAULT_DAYS)
        except IncorrectDeadline:
            CommandError('Deadline cannot be prior to today. Setting deadline to one month from now')
            expected_date = datetime.now() + timedelta(days=DEFAULT_DAYS)

        self.update_deadline(user_id, course_key, expected_date)
        logger.info("Successfully updated credit eligibility deadline for {}".format(username))

    def update_deadline(self, user_id, course_key, deadline):
        try:
            eligibility_record = CreditEligibility.objects.get(user_id=user_id, course_id=course_key)
            eligibility_record.deadline = deadline
            eligibility_record.save()
        except CreditEligibility.DoesNotExist:
            raise CommandError('User is not credit eligible')
