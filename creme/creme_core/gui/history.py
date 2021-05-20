# -*- coding: utf-8 -*-

################################################################################
#    Creme is a free/open-source Customer Relationship Management software
#    Copyright (C) 2021  Hybird
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

import logging
from typing import Iterable, Iterator, List, Sequence, Tuple, Type

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import FieldDoesNotExist
from django.core.validators import EMPTY_VALUES
from django.db import models
from django.db.models import Field
from django.template.loader import get_template
from django.utils.formats import date_format, number_format
from django.utils.html import escape, format_html
from django.utils.safestring import mark_safe
from django.utils.timezone import localtime
from django.utils.translation import gettext
from django.utils.translation import gettext_lazy as _

from creme.creme_core.models import (
    CremeEntity,
    CremePropertyType,
    HistoryLine,
    RelationType,
    history,
)
from creme.creme_core.templatetags.creme_widgets import widget_entity_hyperlink
from creme.creme_core.utils.collections import ClassKeyedMap
from creme.creme_core.utils.dates import date_from_ISO8601, dt_from_ISO8601

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------------------
class FieldChangeExplainer:
    """Render a string which explains a modification on a field stored in an
    history line (edition, related edition, auxiliary object's edition).

    The main method is 'render()' ; other methods are made to be overridden by
    child classes.
    """
    no_value_sentence = _('{field} set')
    new_value_sentence = _('{field} set to {value}')
    emptied_value_sentence = _('{field} emptied (it was {oldvalue})')
    two_values_sentence = _('{field} changed from {oldvalue} to {value}')

    field_decorator = _('“{field}”')
    old_value_decorator = new_value_decorator = _('“{value}”')

    def decorate_field(self, field: str) -> str:
        return self.field_decorator.format(field=field)

    def decorate_new_value(self, value: str) -> str:
        return self.new_value_decorator.format(value=value)

    def decorate_old_value(self, value: str) -> str:
        return self.old_value_decorator.format(value=value)

    @staticmethod
    def is_empty_value(value) -> bool:
        return value in EMPTY_VALUES

    def render_choice(self, *, field: models.Field, user, value):
        # NB: django way for '_get_FIELD_display()' methods
        #       => would a linear search be faster ?
        return dict(field.flatchoices).get(value, value)

    def render_value(self, *, field: models.Field, user, value) -> str:
        return str(value)

    def render(self, *, field: models.Field, user, values: Sequence) -> str:
        """Build a string explain a modification about an instance's field.
        @param field: The field the modification is about.
        @param user: Instance of auth.get_user_model() ; used for VIEW credentials.
        @param values: Sequence representing changes (generally stored in HistoryLine).
               0 element => the field changed.
               1 element => the field received a new value.
               2 elements => (old value, new value)
        @return: a description string.
        """
        decorated_field = self.decorate_field(field.verbose_name)
        length = len(values)

        if length == 0:
            sentence = self.no_value_sentence.format(field=decorated_field)
        elif length == 1:
            sentence = self.new_value_sentence.format(
                field=decorated_field,
                value=self.decorate_new_value(
                    self.render_value(field=field, user=user, value=values[0])
                ),
            )
        else:  # length == 2
            render_value = self.render_choice if field.choices else self.render_value
            new_value = values[1]
            old_rendered_value = self.decorate_old_value(
                render_value(field=field, user=user, value=values[0])
            )

            if self.is_empty_value(new_value):
                sentence = self.emptied_value_sentence.format(
                    field=decorated_field,
                    oldvalue=old_rendered_value,
                )
            else:
                sentence = self.two_values_sentence.format(
                    field=decorated_field,
                    oldvalue=old_rendered_value,
                    value=self.decorate_new_value(
                        render_value(field=field, user=user, value=new_value)
                    ),
                )

        return sentence


class HTMLFieldChangeExplainer(FieldChangeExplainer):
    """Specialization of FieldChangeExplainer which produce HTMl descriptions.
    Used by the History brick for example.
    """
    field_decorator = '<span class="field-change-field_name">{field}</span>'
    old_value_decorator = '<span class="field-change-old_value">{value}</span>'
    new_value_decorator = '<span class="field-change-new_value">{value}</span>'

    def render(self, *, field, user, values):
        return mark_safe(super().render(field=field, user=user, values=values))


class HTMLBooleanFieldChangeExplainer(HTMLFieldChangeExplainer):
    @staticmethod
    def is_empty_value(value):
        return False

    def render_value(self, *, field, user, value):
        return (
            gettext('Yes') if value else
            gettext('No') if value is False else
            gettext('N/A')
        )


class HTMLDateFieldChangeExplainer(HTMLFieldChangeExplainer):
    def render_value(self, *, field, user, value):
        return date_format(date_from_ISO8601(value), 'DATE_FORMAT')


class HTMLDateTimeFieldChangeExplainer(HTMLFieldChangeExplainer):
    def render_value(self, *, field, user, value):
        return date_format(localtime(dt_from_ISO8601(value)), 'DATETIME_FORMAT')


class HTMLNumberFieldChangeExplainer(HTMLFieldChangeExplainer):
    def render_value(self, *, field, user, value):
        # TODO: remove 'use_l10n' when settings.USE_L10N == True
        return number_format(value, use_l10n=True, force_grouping=True)


class HTMLTextFieldChangeExplainer(HTMLFieldChangeExplainer):
    emptied_value_sentence = _('{field} emptied {details_link}')
    changed_value_sentence = _('{field} set {details_link}')

    def render(self, *, field, user, values):
        decorated_field = self.decorate_field(field.verbose_name)
        length = len(values)

        if not length:  # NB: old HistoryLine
            sentence = self.no_value_sentence.format(field=decorated_field)
        else:
            if length == 1:
                old_value = ''
                new_value = values[0]
            else:  # length == 2
                old_value = values[0]
                new_value = values[1]

            sentence_format = (
                self.emptied_value_sentence
                if self.is_empty_value(new_value)
                else self.changed_value_sentence
            )
            sentence = sentence_format.format(
                field=decorated_field,
                details_link=format_html(
                    '<a class="field-change-text_details" data-action="popover">'
                    ' {label}'
                    ' <summary>{summary}</summary>'
                    ' <details>'
                    '  <div class="history-line-field-change-text-old_value">'
                    '   <h4>{old_title}</h4><p>{old}</p>'
                    '  </div>'
                    '  <div class="history-line-field-change-text-new_value">'
                    '   <h4>{new_title}</h4><p>{new}</p>'
                    '  </div>'
                    ' </details>'
                    '</a>',
                    label=gettext('(see details)'),
                    summary=gettext('Details of modifications'),

                    old_title=gettext('Old value'),
                    old=old_value,

                    new_title=gettext('New value'),
                    new=new_value,
                ),
            )

        return mark_safe(sentence)


class ForeignKeyExplainerMixin:
    deleted_value = _('{pk} (deleted)')

    def render_instance(self, instance, user):
        if isinstance(instance, CremeEntity):
            return instance.allowed_str(user)  # TODO: test

        return str(instance)

    def render_fk(self, *, field, user, value):
        model = field.remote_field.model

        try:
            instance = model.objects.get(pk=value)
        except model.DoesNotExist as e:
            logger.info(str(e))

            return self.deleted_value.format(pk=value)

        return self.render_instance(instance=instance, user=user)


class HTMLForeignKeyFieldChangeExplainer(ForeignKeyExplainerMixin,
                                         HTMLFieldChangeExplainer):
    def render_instance(self, instance, user):
        if isinstance(instance, CremeEntity):
            return widget_entity_hyperlink(entity=instance, user=user)

        return escape(instance)

    def render_value(self, *, field, user, value):
        return self.render_fk(field=field, user=user, value=value)

    def render(self, *, field, user, values):
        return mark_safe(super().render(field=field, user=user, values=values))


# ------------------------------------------------------------------------------
class HistoryLineExplainer:
    """Render a string which explains an history line.
    Used by the history brick to render all the lines of the current page.

    The main method is 'render()' ; other methods are made to be overridden by
    child classes.
    """
    type_id: str = ''  # Used in CSS class for example
    template_name: str = 'OVERRIDE_ME'

    def __init__(self, *, hline: HistoryLine, user, field_explainers: ClassKeyedMap):
        self.hline = hline
        self.user = user
        self._field_explainers = field_explainers

    def get_context(self) -> dict:
        """Builds the context of the template."""
        return {
            'type_id': self.type_id,
            'hline': self.hline,
            'user': self.user,
        }

    def _modifications_for_fields(self,
                                  model_class: Type[models.Model],
                                  modifications: List[tuple],
                                  user) -> Iterator[str]:
        get_field = model_class._meta.get_field

        field_explainers = self._field_explainers

        for modif in modifications:
            field_name = modif[0]
            try:
                field: Field = get_field(field_name)
            except FieldDoesNotExist:
                vmodif = gettext('“{field}” set').format(field=field_name)
            else:
                try:
                    vmodif = field_explainers[type(field)]().render(
                        field=field, user=user, values=modif[1:],
                    )
                except Exception:
                    logger.exception('Error when render history for field')
                    vmodif = '??'

            yield vmodif

    def render(self) -> str:
        return get_template(self.template_name).render(self.get_context())


class HTMLCreationExplainer(HistoryLineExplainer):
    type_id = 'creation'
    template_name = 'creme_core/history/html/creation.html'


class HTMLEditionExplainer(HistoryLineExplainer):
    type_id = 'edition'
    template_name = 'creme_core/history/html/edition.html'

    def get_context(self):
        context = super().get_context()

        hline = self.hline
        context['modifications'] = [
            *self._modifications_for_fields(
                model_class=hline.entity_ctype.model_class(),
                modifications=hline.modifications,
                user=self.user,
            )
        ]

        return context


class HTMLDeletionExplainer(HistoryLineExplainer):
    type_id = 'deletion'
    template_name = 'creme_core/history/html/deletion.html'


class HTMLRelatedEditionExplainer(HistoryLineExplainer):
    type_id = 'related_edition'
    template_name = 'creme_core/history/html/related-edition.html'

    def get_context(self):
        context = super().get_context()

        # TODO: render related line in template ?
        related_line = self.hline.related_line
        context['modifications'] = [
            *self._modifications_for_fields(
                model_class=related_line.entity_ctype.model_class(),
                modifications=related_line.modifications,
                user=self.user,
            )
        ]

        return context


class _PropertyExplainer(HistoryLineExplainer):
    def get_context(self):
        context = super().get_context()
        ptype_id = self.hline.modifications[0]

        try:
            # TODO: use cache ?
            ptype_text = CremePropertyType.objects.get(pk=ptype_id).text
        except CremePropertyType.DoesNotExist:
            ptype_text = ptype_id

        context['property_text'] = ptype_text

        return context


class HTMLPropertyAdditionExplainer(_PropertyExplainer):
    type_id = 'property_addition'
    template_name = 'creme_core/history/html/property-addition.html'


class HTMLPropertyDeletionExplainer(_PropertyExplainer):
    type_id = 'property_deletion'
    template_name = 'creme_core/history/html/property-deletion.html'


class _RelationExplainer(HistoryLineExplainer):
    def get_context(self):
        context = super().get_context()

        rtype_id = self.hline.modifications[0]

        try:
            # TODO: use a cache ?
            predicate = RelationType.objects.get(pk=rtype_id).predicate
        except RelationType.DoesNotExist:
            predicate = rtype_id

        context['predicate'] = predicate

        return context


class HTMLRelationAdditionExplainer(_RelationExplainer):
    type_id = 'relationship_addition'
    template_name = 'creme_core/history/html/relation-addition.html'


class HTMLRelationDeletionExplainer(_RelationExplainer):
    type_id = 'relationship_deletion'
    template_name = 'creme_core/history/html/relation-deletion.html'


class HTMLAuxCreationExplainer(HistoryLineExplainer):
    type_id = 'auxiliary_creation'
    template_name = 'creme_core/history/html/auxiliary-creation.html'

    def get_context(self):
        context = super().get_context()

        # TODO: use aux_id to display an up-to-date value ??
        ct_id, aux_id, str_obj = self.hline.modifications
        context['auxiliary_ctype'] = ContentType.objects.get_for_id(ct_id)
        context['auxiliary_value'] = str_obj

        return context


class HTMLAuxiliaryEditionExplainer(HistoryLineExplainer):
    type_id = 'auxiliary_edition'
    template_name = 'creme_core/history/html/auxiliary-edition.html'

    def get_context(self):
        context = super().get_context()

        modifications = self.hline.modifications

        # TODO: use aux_id to display an up-to-date value ??
        ct_id, aux_id, str_obj = modifications[0]
        ctype = ContentType.objects.get_for_id(ct_id)

        context['auxiliary_ctype'] = ctype
        context['auxiliary_value'] = str_obj

        context['modifications'] = [
            *self._modifications_for_fields(
                model_class=ctype.model_class(),
                modifications=modifications[1:],
                user=self.user,
            )
        ]

        return context


class HTMLAuxDeletionExplainer(HistoryLineExplainer):
    type_id = 'auxiliary_deletion'
    template_name = 'creme_core/history/html/auxiliary-deletion.html'

    def get_context(self):
        context = super().get_context()

        ct_id, str_obj = self.hline.modifications
        context['auxiliary_ctype'] = ContentType.objects.get_for_id(ct_id)
        context['auxiliary_value'] = str_obj

        return context


class HTMLTrashExplainer(HistoryLineExplainer):
    type_id = 'trash'
    template_name = 'creme_core/history/html/trash.html'


class HTMLMassExportExplainer(HistoryLineExplainer):
    type_id = 'mass_export'
    template_name = 'creme_core/history/html/mass-export.html'


# ------------------------------------------------------------------------------
class HistoryRegistry:
    """Registry for HistoryLineExplainers & FieldChangeExplainers.
    Each registry should be dedicated to one format (eg: HTML for the brick).
    """
    def __init__(self, default_field_explainer_class=FieldChangeExplainer):
        self._line_explainer_classes = {}
        self._field_explainer_classes = ClassKeyedMap(default=default_field_explainer_class)

    def register_line_explainer(self,
                                htype: int,
                                explainer_class: Type[HistoryLineExplainer],
                                ) -> 'HistoryRegistry':
        self._line_explainer_classes[htype] = explainer_class

        return self

    # TODO: unit test
    def register_field_explainers(
        self,
        *explainer_classes: Tuple[Type[models.Field], Type[FieldChangeExplainer]],
    ):
        existing_classes = self._field_explainer_classes
        for field_cls, explainer_cls in explainer_classes:
            existing_classes[field_cls] = explainer_cls

        return self

    # def field_change_explainer(self, field):
    #     return self._field_explainer_classes[type(field)]

    def line_explainers(self,
                        hlines: Iterable[HistoryLine],
                        user,
                        ) -> List[HistoryLineExplainer]:
        """Get the explainers corresponding to a sequence of HistoryLines
        Notice that the order is kept (ie: you can zip()).
        """
        class EmptyExplainer(HistoryLineExplainer):
            def render(this):
                return '??'

        get_cls = self._line_explainer_classes.get
        field_explainers = self._field_explainer_classes

        return [
            get_cls(hline.type, EmptyExplainer)(
                hline=hline, user=user, field_explainers=field_explainers,
            ) for hline in hlines
        ]


html_history_registry = HistoryRegistry(
    default_field_explainer_class=HTMLFieldChangeExplainer,
).register_field_explainers(
    (models.BooleanField, HTMLBooleanFieldChangeExplainer),

    (models.ForeignKey, HTMLForeignKeyFieldChangeExplainer),

    (models.DateField,     HTMLDateFieldChangeExplainer),
    (models.DateTimeField, HTMLDateTimeFieldChangeExplainer),

    (models.IntegerField, HTMLNumberFieldChangeExplainer),
    (models.DecimalField, HTMLNumberFieldChangeExplainer),
    (models.FloatField,   HTMLNumberFieldChangeExplainer),  # TODO: test

    (models.TextField, HTMLTextFieldChangeExplainer),
).register_line_explainer(
    htype=history.TYPE_CREATION,
    explainer_class=HTMLCreationExplainer,
).register_line_explainer(
    htype=history.TYPE_EDITION,
    explainer_class=HTMLEditionExplainer,
).register_line_explainer(
    htype=history.TYPE_DELETION,
    explainer_class=HTMLDeletionExplainer,
).register_line_explainer(
    htype=history.TYPE_RELATED,
    explainer_class=HTMLRelatedEditionExplainer,
).register_line_explainer(
    htype=history.TYPE_PROP_ADD,
    explainer_class=HTMLPropertyAdditionExplainer,
).register_line_explainer(
    htype=history.TYPE_PROP_DEL,
    explainer_class=HTMLPropertyDeletionExplainer,
).register_line_explainer(
    htype=history.TYPE_RELATION,
    explainer_class=HTMLRelationAdditionExplainer,
).register_line_explainer(
    htype=history.TYPE_SYM_RELATION,
    explainer_class=HTMLRelationAdditionExplainer,
).register_line_explainer(
    htype=history.TYPE_RELATION_DEL,
    explainer_class=HTMLRelationDeletionExplainer,
).register_line_explainer(
    htype=history.TYPE_SYM_REL_DEL,
    explainer_class=HTMLRelationDeletionExplainer,
).register_line_explainer(
    htype=history.TYPE_AUX_CREATION,
    explainer_class=HTMLAuxCreationExplainer,
).register_line_explainer(
    htype=history.TYPE_AUX_EDITION,
    explainer_class=HTMLAuxiliaryEditionExplainer,
).register_line_explainer(
    htype=history.TYPE_AUX_DELETION,
    explainer_class=HTMLAuxDeletionExplainer,
).register_line_explainer(
    htype=history.TYPE_TRASH,
    explainer_class=HTMLTrashExplainer,
).register_line_explainer(
    htype=history.TYPE_EXPORT,
    explainer_class=HTMLMassExportExplainer,
)
