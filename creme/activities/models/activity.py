################################################################################
#    Creme is a free/open-source Customer Relationship Management software
#    Copyright (C) 2009-2024  Hybird
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
################################################################################

import warnings

from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.utils.translation import pgettext_lazy

from creme.creme_core.models import CREME_REPLACE_NULL, CremeEntity
from creme.creme_core.models.manager import CremeEntityManager

# from ..constants import NARROW
from ..constants import (
    CREATION_LABELS,
    REL_OBJ_ACTIVITY_SUBJECT,
    REL_OBJ_LINKED_2_ACTIVITY,
    REL_OBJ_PART_2_ACTIVITY,
)
from . import other_models
from .calendar import Calendar


class ActivityManager(CremeEntityManager):
    linked_rtype_ids = (
        REL_OBJ_PART_2_ACTIVITY,
        REL_OBJ_ACTIVITY_SUBJECT,
        REL_OBJ_LINKED_2_ACTIVITY,
    )

    def _linked(self, entity):
        return self.filter(
            is_deleted=False,
            relations__object_entity=entity,
            relations__type__in=self.linked_rtype_ids,
        ).distinct()

    def _linked_to_organisation(self, orga):
        return self.filter(
            is_deleted=False,
            relations__object_entity__in=[
                orga,
                *orga.get_managers().values_list('id', flat=True),
                *orga.get_employees().values_list('id', flat=True),
            ],
            relations__type__in=self.linked_rtype_ids,
        ).distinct()

    def future_linked(self, entity, today):
        # TODO: end greater than today or floating type equal to floating
        return self._linked(entity).filter(end__gt=today).order_by('start')

    def past_linked(self, entity, today):
        return self._linked(entity).filter(end__lte=today)

    def future_linked_to_organisation(self, orga, today):
        return self._linked_to_organisation(orga).filter(end__gt=today).order_by('start')

    def past_linked_to_organisation(self, orga, today):
        return self._linked_to_organisation(orga).filter(end__lte=today)


class AbstractActivity(CremeEntity):
    """Activity: task, meeting, phone call, unavailability..."""
    class FloatingType(models.IntegerChoices):
        NARROW        = 1, pgettext_lazy('activities-activity', 'Fixed')
        FLOATING_TIME = 2, _('Floating time')
        FLOATING      = 3, pgettext_lazy('activities-activity', 'Floating')

    title = models.CharField(_('Title'), max_length=100)
    start = models.DateTimeField(_('Start'), blank=True, null=True)
    end = models.DateTimeField(_('End'), blank=True, null=True)

    minutes = models.TextField(_('Minutes'), blank=True)
    place = models.CharField(
        _('Activity place'), max_length=500, blank=True
    ).set_tags(optional=True)
    duration = models.PositiveIntegerField(
        verbose_name=_('Duration (in hour)'),
        blank=True, null=True,
        help_text=_('It is only informative and is not used to compute the end time.'),
    )

    type = models.ForeignKey(
        other_models.ActivityType, verbose_name=_('Activity type'), on_delete=models.PROTECT,
    )
    sub_type = models.ForeignKey(
        other_models.ActivitySubType, verbose_name=_('Activity sub-type'),
        on_delete=models.PROTECT,
    )

    status = models.ForeignKey(
        other_models.Status, verbose_name=_('Status'),
        blank=True, null=True, on_delete=CREME_REPLACE_NULL,
    )

    calendars = models.ManyToManyField(Calendar, verbose_name=_('Calendars'), editable=False)

    is_all_day = models.BooleanField(_('All day?'), default=False)
    busy = models.BooleanField(_('Busy?'), default=False)
    # floating_type = models.PositiveIntegerField(
    #     _('Floating type'), default=NARROW, editable=False,
    # ).set_tags(viewable=False)
    floating_type = models.PositiveSmallIntegerField(
        _('Fixed or floating?'),
        choices=FloatingType, default=FloatingType.NARROW,
        editable=False,
    )

    objects = ActivityManager()

    _DELETABLE_INTERNAL_RTYPE_IDS = (REL_OBJ_PART_2_ACTIVITY, REL_OBJ_ACTIVITY_SUBJECT)

    creation_label = _('Create an activity')
    save_label = _('Save the activity')

    class Meta:
        abstract = True
        app_label = 'activities'
        verbose_name = _('Activity')
        verbose_name_plural = _('Activities')
        ordering = ('-start',)

    @classmethod
    def get_creation_title(cls, type_id):
        return CREATION_LABELS.get(type_id, cls.creation_label)

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse('activities__view_activity', args=(self.id,))

    @staticmethod
    def get_create_absolute_url():
        return reverse('activities__create_activity')

    def get_edit_absolute_url(self):
        return reverse('activities__edit_activity', args=(self.id,))

    @staticmethod
    def get_lv_absolute_url():
        return reverse('activities__list_activities')

    def get_participant_relations(self):
        return self.get_relations(REL_OBJ_PART_2_ACTIVITY, real_obj_entities=True)

    def get_subject_relations(self, real_entities=True):
        """Get the list of models.Relation instances which link the Activity
        with its subjects.
        @param real_entities: Retrieve (efficiently) the real entities which are related.
        """
        return self.get_relations(REL_OBJ_ACTIVITY_SUBJECT, real_obj_entities=real_entities)

    def get_linkedto_relations(self):
        return self.get_relations(REL_OBJ_LINKED_2_ACTIVITY, real_obj_entities=True)

    def handle_all_day(self):
        if self.is_all_day:
            self.start = self.start.replace(hour=0, minute=0)
            self.end   = self.end.replace(hour=23, minute=59)

    def _pre_save_clone(self, source):
        warnings.warn(
            'The method CremeEntity._pre_save_clone() is deprecated.',
            DeprecationWarning,
        )
        if source.busy:
            self.busy = False

    def _copy_relations(self, source, allowed_internal=()):
        warnings.warn(
            'The method Activity._copy_relations() is deprecated.',
            DeprecationWarning,
        )

        super()._copy_relations(
            source,
            allowed_internal=[*allowed_internal, REL_OBJ_PART_2_ACTIVITY],
        )


class Activity(AbstractActivity):
    class Meta(AbstractActivity.Meta):
        swappable = 'ACTIVITIES_ACTIVITY_MODEL'
