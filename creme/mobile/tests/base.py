from datetime import timedelta
from random import randint

from django.urls import reverse
from django.utils.timezone import now

from creme.activities import get_activity_model
from creme.activities.constants import (
    ACTIVITYSUBTYPE_MEETING_NETWORK,
    ACTIVITYSUBTYPE_PHONECALL_OUTGOING,
    ACTIVITYTYPE_MEETING,
    ACTIVITYTYPE_PHONECALL,
    FLOATING,
    REL_SUB_PART_2_ACTIVITY,
)
from creme.creme_core.models import Relation
from creme.creme_core.tests.base import CremeTestCase
from creme.persons import get_contact_model, get_organisation_model

Contact = get_contact_model()
Organisation = get_organisation_model()
Activity = get_activity_model()


class MobileBaseTestCase(CremeTestCase):
    PORTAL_URL = reverse('mobile__portal')

    def login_as_mobile_user(self, *, allowed_apps=(), **kwargs):
        return super().login_as_standard(
            allowed_apps=['activities', 'persons', *allowed_apps],
            **kwargs
        )

    def _create_floating(self, user, title, participant, status_id=None):
        activity = Activity.objects.create(
            user=user, title=title,
            type_id=ACTIVITYTYPE_MEETING,
            sub_type_id=ACTIVITYSUBTYPE_MEETING_NETWORK,
            status_id=status_id,
            floating_type=FLOATING,
        )

        Relation.objects.create(
            subject_entity=participant, user=user,
            type_id=REL_SUB_PART_2_ACTIVITY,
            object_entity=activity,
        )

        return activity

    def _create_pcall(self, user, title, start=None, participant=None, status_id=None,
                      **kwargs):
        if start is None:
            start = self.create_datetime(year=2014, month=1, day=6, hour=8) \
                        .replace(month=randint(1, 12))

        activity = Activity.objects.create(
            user=user, title=title,
            type_id=ACTIVITYTYPE_PHONECALL,
            sub_type_id=ACTIVITYSUBTYPE_PHONECALL_OUTGOING,
            status_id=status_id,
            start=start,
            end=start + timedelta(hours=1),
            **kwargs
        )

        if participant is not None:
            Relation.objects.create(
                subject_entity=participant, user=user,
                type_id=REL_SUB_PART_2_ACTIVITY,
                object_entity=activity,
            )

        return activity

    def _create_meeting(self, user, title, start=None, end=None, participant=None, status_id=None,
                        **kwargs):
        if start is None:
            start = now()

        if end is None:
            end = start + timedelta(hours=1)

        activity = Activity.objects.create(
            user=user, title=title,
            type_id=ACTIVITYTYPE_MEETING,
            sub_type_id=ACTIVITYSUBTYPE_MEETING_NETWORK,
            status_id=status_id,
            start=start,
            end=end,
            **kwargs
        )

        if participant is not None:
            Relation.objects.create(
                subject_entity=participant, user=user,
                type_id=REL_SUB_PART_2_ACTIVITY,
                object_entity=activity,
            )

        return activity
