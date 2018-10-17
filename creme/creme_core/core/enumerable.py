# -*- coding: utf-8 -*-

################################################################################
#    Creme is a free/open-source Customer Relationship Management software
#    Copyright (C) 2018  Hybird
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

from creme.creme_core.models import CremeEntity
from creme.creme_core.utils.collections import ClassKeyedMap


class Enumerator:
    """Class which can enumerate some choices (think <select> in HTML)."""

    def __init__(self, field):
        """Constructor.

        @param field: Instance of model field (eg: MyModel._meta.get_field('my_field')).
        """
        self.field = field

    def choices(self, user):
        """Return the list of choices (see below) available for the given user.
        Abstract method.

        Each choice must be a dictionary, wit the keys:
            value: Value of the choice (wich will be POSTed). Mandatory.
            label: Label of the choice, displayed to the user. Mandatory.
            help:  Small additional description for the label. Optional.
            group: Group of the choice (think <optgroup> in HTML). Optional.

        @param user: Instance of User.
        @return: List of choice-dictionaries.
        """
        raise NotImplementedError

    @classmethod
    def instance_as_dict(cls, instance):
        return {
            'value': instance.pk,
            'label': str(instance),
        }

    @staticmethod
    def convert_choices(choices):
        """Generators which converts Django-style choices into
        Enumerator-style choices.

        Django's style:
         - No-group: [(1, 'Foo'), (2, 'Bar'), (3, 'Baz')]
         - Group:    [('A',
                       [(1, 'Apple'), (2, 'Animal')]
                      ),
                      ('B',
                       [(3, 'Banana'), (4, 'Balloon')]
                      )
                    ]

         Enumerator's style: see choices().
        """
        for k0, v0 in choices:
            if isinstance(v0, (list, tuple)):
                for value, label in v0:
                    yield {'value': value, 'label': label, 'group': k0}
            else:
                yield {'value': k0, 'label': v0}


class QSEnumerator(Enumerator):
    """Specialisation of Enumerator to enumerate elements of a QuerySet."""
    def _queryset(self):
        field = self.field
        qs = field.remote_field.model.objects.all()
        limit_choices_to = field.get_limit_choices_to()

        return qs.complex_filter(limit_choices_to) if limit_choices_to else qs

    def choices(self, user):
        return list(map(self.instance_as_dict, self._queryset()))


class _EnumerableRegistry:
    """Registry which manages the choices available for (enumerable) model fields.

    Eg: will be used to propose available choices for filter-conditions
        related to a ForeignKey.

    The registry has a default behaviour for enumerable fields (it gets all the
    instances of the related instances -- using the attribute
    "limit_choices_too").
    The behaviour can be overridden for:
      - The model related to the ForeignKey/ManyToManyField (see register_related_model()).
      - The type (class) of the model-field which we want to enumerate (see register_field_type()).
      - The model-field which we want to enumerate (see register_field()).
    """
    class RegistrationError(Exception):
        pass

    def __init__(self):
        self._enums_4_fields = {}
        self._enums_4_field_types = ClassKeyedMap()
        self._enums_4_models = {}

    def __str__(self):
        res = '_EnumerableRegistry:'

        if self._enums_4_fields:
            res += '\n  * Specific fields:'
            for field, enumerator_cls in self._enums_4_fields.items():
                res += '\n    - {field} -> {e_module}.{e_type}'.format(
                            field=field,
                            e_module=enumerator_cls.__module__,
                            e_type=enumerator_cls.__qualname__,
                )

        if self._enums_4_field_types:
            res += '\n  * Field types:'
            for field_type, enumerator_cls in self._enums_4_field_types.items():
                res += '\n    - {f_module}.{f_type} -> {e_module}.{e_type}'.format(
                            f_module=field_type.__module__,
                            f_type=field_type.__name__,
                            e_module=enumerator_cls.__module__,
                            e_type=enumerator_cls.__qualname__,
                )

        if self._enums_4_models:
            res += '\n  * Related models:'
            for model, enumerator_cls in self._enums_4_models.items():
                res += '\n    - {app}.{model} -> {e_module}.{e_type}'.format(
                            app=model._meta.app_label,
                            model=model.__name__,
                            e_module=enumerator_cls.__module__,
                            e_type=enumerator_cls.__qualname__,
                )

        return res

    @staticmethod
    def _check_model(model):
        # TODO: and registered as an entity ??
        if not issubclass(model, CremeEntity):
            raise ValueError('This model is not a CremeEntity: {}.{}'.format(
                                    model.__module__, model.__name__,
                                )
                            )

    @staticmethod
    def _check_field(field):
        if not field.get_tag('viewable'):  # TODO: unit test (needs new field)
            raise ValueError('This field is not viewable: {}'.format(field))

        # TODO: we probably should manage fields with is_relation==False but with
        #       a 'choices' attribute. Wait to add the feature in EntityFilterForm too.

        if not field.get_tag('enumerable'):
            raise ValueError('This field is not enumerable: {}'.format(field))

    def _get_field(self, model, field_name):
        field = model._meta.get_field(field_name)  # Can raise FieldDoesNotExist
        self._check_field(field)

        return field

    def _enumerator(self, field):
        enumerator_cls = self._enums_4_fields.get(field) or \
                         self._enums_4_field_types[field.__class__] or \
                         self._enums_4_models.get(field.remote_field.model, QSEnumerator)

        return enumerator_cls(field)

    def enumerator_by_field(self, field):
        """Get an Enumerator instance corresponding to a model field.

        @param field: Model field instance.
        @return: Instance of Enumerator.
        @raises: ValueError if the model or the field are invalid.
        """
        self._check_model(field.model)
        self._check_field(field)

        return self._enumerator(field)

    def enumerator_by_fieldname(self, model, field_name):
        """Get an Enumerator instance corresponding to a model field.

        @param class: Model inheriting CremeEntity.
        @param field_name: Name of a field (string).
        @return: Instance of Enumerator.
        @raises: ValueError if the model or the field are invalid.
        @raises: FieldDoesNotExist.
        """
        self._check_model(model)

        return self._enumerator(self._get_field(model, field_name))

    def register_field(self, model, field_name, enumerator_class):
        """Customise the class of the enumerator returned by the methods
        enumerator_by_field[name] for a specific field.

        @param model: Model inheriting 'CremeEntity'.
        @param field_name: Name of a field of <model>.
        @param enumerator_class: Class inheriting 'Enumerator'.
        @raises: ValueError if the model or the field are invalid.
        @raises: FieldDoesNotExist.
        """
        assert issubclass(enumerator_class, Enumerator)

        field = self._get_field(model, field_name)

        if self._enums_4_fields.setdefault(field, enumerator_class) is not enumerator_class:
            raise self.RegistrationError(
                '_EnumerableRegistry: this field is already registered: {model}.{field}'.format(
                    model=model.__name__, field=field_name,
                )
            )

    def register_field_type(self, field_class, enumerator_class):
        """Customise the class of the enumerator returned by the methods
        enumerator_by_field[name] for a specific field class.

        @param field_class: Class inheriting 'django.db.models.Field'.
        @param enumerator_class: Class inheriting 'Enumerator'.
        """
        assert issubclass(enumerator_class, Enumerator)

        self._enums_4_field_types[field_class] = enumerator_class

    def register_related_model(self, model, enumerator_class):
        """Customise the class of the enumerator returned by the methods
        enumerator_by_field[name] for ForeignKeys/ManyToManyFields
        which reference a specific model.

        @param model: Model (class inheriting 'django.db.models.Model').
        @param enumerator_class: Class inheriting 'Enumerator'.
        """
        assert issubclass(enumerator_class, Enumerator)

        if self._enums_4_models.setdefault(model, enumerator_class) is not enumerator_class:
            raise self.RegistrationError(
                '_EnumerableRegistry: this model is already registered: {}'.format(model)
            )


enumerable_registry = _EnumerableRegistry()