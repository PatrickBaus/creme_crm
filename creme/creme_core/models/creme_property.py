################################################################################
#    Creme is a free/open-source Customer Relationship Management software
#    Copyright (C) 2009-2025  Hybird
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

from __future__ import annotations

import logging
import warnings
from typing import Iterable
from uuid import uuid4

from django.contrib.contenttypes.models import ContentType
from django.db import IntegrityError, models
from django.db.models.query_utils import Q
from django.db.transaction import atomic
from django.dispatch import receiver
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from .. import signals
from ..utils.content_type import as_ctype
from .base import CremeModel
from .entity import CremeEntity

logger = logging.getLogger(__name__)


class CremePropertyTypeManager(models.Manager):
    def compatible(self, ct_or_model: ContentType | type[CremeEntity]):
        return self.filter(
            Q(subject_ctypes=as_ctype(ct_or_model))
            | Q(subject_ctypes__isnull=True)
        )

    def smart_update_or_create(
        self, *,
        uuid: str = '',
        text: str,
        app_label: str = '',
        subject_ctypes: Iterable[ContentType | type[CremeEntity]] = (),
        is_custom: bool = False,
        is_copiable: bool = True,
    ) -> CremePropertyType:
        """Helps the creation of new CremePropertyType instance.
        @param uuid: Used to fill <CremePropertyType.uuid> ;
               if you pass an empty string, a UUID will be generated.
        @param text: Used to fill <CremePropertyType.text>.
        @param app_label: Used to fill <CremePropertyType.app_label>.
        @param subject_ctypes: Used to fill <CremePropertyType.subject_ctypes>.
        @param is_custom: Used to fill <CremePropertyType.is_custom>.
        @param is_copiable: Used to fill <CremePropertyType.is_copiable>.
        """
        warnings.warn(
            'CremePropertyTypeManager.smart_update_or_create() is deprecated; '
            'use create()/update_or_create() instead '
            '(& eventually CremePropertyType.set_subject_ctypes() too).'
        )

        if uuid:
            property_type = self.update_or_create(
                uuid=uuid,
                defaults={
                    'text': text,
                    'is_custom': is_custom,
                    'is_copiable': is_copiable,
                    'app_label': app_label,
                },
            )[0]
        else:
            property_type = self.create(
                text=text,
                is_custom=is_custom,
                is_copiable=is_copiable,
                app_label=app_label,
            )

        get_ct = ContentType.objects.get_for_model
        property_type.subject_ctypes.set([
            model if isinstance(model, ContentType) else get_ct(model)
            for model in subject_ctypes
        ])

        return property_type


# TODO: factorise with RelationManager ?
class CremePropertyManager(models.Manager):
    def safe_create(self, **kwargs) -> None:
        """Create a CremeProperty in DB by taking care of the UNIQUE constraint.
        Notice that, unlike 'create()' it always return None (to avoid a
        query in case of IntegrityError) ; use 'safe_get_or_create()' if
        you need the CremeProperty instance.
        @param kwargs: same as 'create()'.
        """
        try:
            with atomic():
                self.create(**kwargs)
        except IntegrityError:
            logger.exception('Avoid a CremeProperty duplicate: %s ?!', kwargs)

    def safe_get_or_create(self, **kwargs) -> CremeProperty:
        """Kind of safe version of 'get_or_create'.
        Safe means the UNIQUE constraint of Relation is respected, &
        this method will never raise an IntegrityError.

        Notice that the signature of this method is the same as 'create()'
        & not the same as 'get_or_create()' : the argument "defaults" does
        not exist & no boolean is returned.

        @param kwargs: same as 'create()'.
        return: A CremeProperty instance.
        """
        for _i in range(10):
            try:
                prop = self.get(**kwargs)
            except self.model.DoesNotExist:
                try:
                    with atomic():
                        prop = self.create(**kwargs)
                except IntegrityError:
                    logger.exception('Avoid a CremeProperty duplicate: %s ?!', kwargs)
                    continue

            break
        else:
            raise RuntimeError(
                f'It seems the CremeProperty <{kwargs}> keeps being created & deleted.'
            )

        return prop

    def safe_multi_save(self,
                        properties: Iterable[CremeProperty],
                        check_existing: bool = True,
                        ) -> int:
        """Save several instances of CremeProperty by taking care of the UNIQUE
        constraint on ('type', 'creme_entity').

        Notice that you should not rely on the instances which you gave ;
        they can be saved (so get a fresh ID), or not be saved because they are
        a duplicate (& so their ID remains 'None').

        Compared to use N x 'safe_get_or_create()', this method will only
        perform 1 query to retrieve the existing CremeProperties.

        @param properties: An iterable of CremeProperties (not save yet).
        @param check_existing: Perform a query to check existing CremeProperties.
               You can pass False for newly created instances in order to avoid a query.
        @return: Number of CremeProperties inserted in base.
        """
        count = 0
        unique_props = {
            (prop.type_id, prop.creme_entity_id): prop
            for prop in properties
        }

        if unique_props:
            if check_existing:
                existing_q = Q()
                for prop in unique_props.values():
                    existing_q |= Q(
                        type_id=prop.type_id,
                        creme_entity_id=prop.creme_entity_id,
                    )

                for prop_sig in self.filter(existing_q).values_list(
                    'type', 'creme_entity',
                ):
                    unique_props.pop(prop_sig, None)

            for prop in unique_props.values():
                try:
                    with atomic():
                        prop.save()
                except IntegrityError:
                    logger.exception('Avoid a CremeProperty duplicate: %s ?!', prop)
                else:
                    count += 1

        return count


class CremePropertyType(CremeModel):
    uuid = models.UUIDField(unique=True, editable=False, default=uuid4)
    # The label is used by the command "creme_uninstall".
    # Empty string means <type created by a user>.
    app_label = models.CharField(
        _('Created by the app'), max_length=40, default='', editable=False,
    )

    text = models.CharField(
        _('Text'), max_length=200, unique=True,
        help_text=_("For example: 'is pretty'"),
    )
    description = models.TextField(_('Description'), blank=True)

    subject_ctypes = models.ManyToManyField(
        ContentType, blank=True,
        verbose_name=_('Related to types of entities'),
        # TODO: harmonise with RelationType ("relationtype_subjects_set")
        related_name='subject_ctypes_creme_property_set',
        help_text=_('No selected type means that all types are accepted'),
    )
    is_custom = models.BooleanField(default=False, editable=False)

    is_copiable = models.BooleanField(
        _('Is copiable'), default=True,
        help_text=_(
            'Are the properties with this type copied when an entity is cloned?'
        ),
    )

    # A disabled type should not be proposed for adding (and a property with
    # this type should be visually marked as disabled in the UI).
    enabled = models.BooleanField(_('Enabled?'), default=True, editable=False)

    objects = CremePropertyTypeManager()

    creation_label = _('Create a type of property')
    save_label     = _('Save the type of property')

    class Meta:
        app_label = 'creme_core'
        verbose_name = _('Type of property')
        verbose_name_plural = _('Types of property')
        ordering = ('text',)

    def __str__(self):
        return self.text

    def get_absolute_url(self):
        return reverse('creme_core__ptype', args=(self.id,))

    @staticmethod
    def get_create_absolute_url():
        return reverse('creme_core__create_ptype')

    def get_delete_absolute_url(self):
        return reverse('creme_core__delete_ptype', args=(self.id,))

    def get_edit_absolute_url(self):
        return reverse('creme_core__edit_ptype', args=(self.id,))

    @staticmethod
    def get_lv_absolute_url():
        return reverse('creme_config__ptypes')

    @property
    def subject_models(self):
        for ctype in self.subject_ctypes.all():
            yield ctype.model_class()

    def set_subject_ctypes(self,
                           *ctypes_or_models: Iterable[ContentType | type[CremeEntity]],
                           ) -> CremePropertyType:
        get_ct = ContentType.objects.get_for_model
        self.subject_ctypes.set([
            ct_or_model if isinstance(ct_or_model, ContentType) else get_ct(ct_or_model)
            for ct_or_model in ctypes_or_models
        ])

        return self


class CremeProperty(CremeModel):
    type = models.ForeignKey(
        CremePropertyType,
        verbose_name=_('Type of property'),
        on_delete=models.CASCADE,
    )
    creme_entity = models.ForeignKey(
        CremeEntity,
        verbose_name=_('Entity'),
        related_name='properties', on_delete=models.CASCADE,
    )

    objects = CremePropertyManager()

    class Meta:
        app_label = 'creme_core'
        verbose_name = _('Property')
        verbose_name_plural = _('Properties')
        unique_together = ('type', 'creme_entity')

    def __str__(self):
        return str(self.type)

    def get_related_entity(self):  # For generic views
        return self.creme_entity


@receiver(signals.pre_merge_related, dispatch_uid='creme_core-manage_properties_merge')
def _handle_merge(sender, other_entity, **kwargs):
    """Delete 'Duplicated' CremeProperties (i.e. exist in the removed entity &
    the remaining entity).
    """
    from ..core.history import toggle_history

    ptype_ids = sender.properties.values_list('type', flat=True)

    # Duplicates' deletion would be confusing to the user (the
    # property type is still related to the remaining entity). So we
    # disable the history for it.
    with toggle_history(enabled=False):
        for prop in other_entity.properties.filter(type__in=ptype_ids):
            prop.delete()


@receiver(
    signals.pre_replace_related,
    sender=CremePropertyType, dispatch_uid='creme_core-manage_type_replacement',
)
def _handle_replacement(sender, old_instance, new_instance, **kwargs):
    """Delete 'Duplicated' CremeProperties (i.e. one entity has 2 properties
    with the old & the new types).
    """
    from django.db.models import Count

    from ..core.history import toggle_history

    # IDs of entities with duplicates
    e_ids = CremeEntity.objects.filter(
        properties__type__in=[old_instance, new_instance],
    ).annotate(
        prop_count=Count('properties'),
    ).filter(
        prop_count__gte=2,
    ).values_list('id', flat=True)

    with toggle_history(enabled=False):  # See _handle_merge()
        for prop in CremeProperty.objects.filter(creme_entity__in=e_ids, type=old_instance):
            prop.delete()
