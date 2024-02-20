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

from __future__ import annotations

import logging

from django.contrib.contenttypes.models import ContentType
from django.db.transaction import atomic
from django.http import Http404
from django.shortcuts import get_list_or_404, get_object_or_404
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

# TODO: move them to creme_core ?
import creme.creme_config.forms.creme_property_type as ptype_forms

from ..auth import EntityCredentials
from ..core.paginator import FlowPaginator
from ..forms import creme_property as prop_forms
from ..gui.bricks import Brick, QuerysetBrick
from ..models import CremeEntity, CremeProperty, CremePropertyType
from ..utils import get_from_POST_or_404
from ..utils.content_type import entity_ctypes
from . import generic
from .bricks import BricksReloading
from .generic.base import EntityCTypeRelatedMixin

# TODO: Factorise with views in creme_config

logger = logging.getLogger(__name__)


# TODO: Factorise with add_relations_bulk and bulk_update?
class PropertiesBulkAdding(EntityCTypeRelatedMixin,
                           generic.CremeFormPopup):
    form_class = prop_forms.PropertiesBulkAddingForm
    title = _('Multiple adding of properties')
    submit_label = _('Add the properties')

    def filter_entities(self, entities):
        filtered = {True: [], False: []}
        has_perm = self.request.user.has_perm_to_change

        for entity in entities:
            filtered[has_perm(entity)].append(entity)

        return filtered

    def get_entities(self, model):
        request = self.request
        entities = get_list_or_404(
            model,
            pk__in=(
                request.POST.getlist('ids')
                if request.method == 'POST' else
                request.GET.getlist('ids')
            ),
        )

        CremeEntity.populate_real_entities(entities)

        return entities

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()

        model = self.get_ctype().model_class()
        kwargs['model'] = model

        filtered = self.filter_entities(self.get_entities(model=model))
        kwargs['entities'] = filtered[True]
        kwargs['forbidden_entities'] = filtered[False]

        return kwargs


class PropertiesAdding(generic.RelatedToEntityFormPopup):
    form_class = prop_forms.PropertiesAddingForm
    title = _('New properties for «{entity}»')
    submit_label = _('Add the properties')


class PropertyTypeCreation(generic.CremeModelCreation):
    model = CremePropertyType
    # form_class = ptype_forms.CremePropertyTypeCreationForm
    form_class = ptype_forms.CremePropertyForm
    permissions = 'creme_core.can_admin'


class PropertyTypeEdition(generic.CremeModelEdition):
    # model = CremePropertyType
    queryset = CremePropertyType.objects.filter(is_custom=True, enabled=True)
    # form_class = ptype_forms.CremePropertyTypeEditionForm
    form_class = ptype_forms.CremePropertyForm
    pk_url_kwarg = 'ptype_id'
    permissions = 'creme_core.can_admin'


class PropertyFromFieldsDeletion(generic.base.EntityRelatedMixin,
                                 generic.CremeModelDeletion):
    model = CremeProperty

    entity_id_arg = 'entity_id'
    ptype_id_arg = 'ptype_id'

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.property_type = None

    def get_query_kwargs(self):
        return {
            'type':            self.get_property_type(),
            'creme_entity_id': self.get_related_entity().id,
        }

    def get_related_entity_id(self):
        return get_from_POST_or_404(self.request.POST, self.entity_id_arg)

    def get_property_type(self):
        ptype = self.property_type

        if ptype is None:
            self.property_type = ptype = get_object_or_404(
                CremePropertyType, id=self.get_property_type_id(),
            )

        return ptype

    def get_property_type_id(self):
        return get_from_POST_or_404(self.request.POST, self.ptype_id_arg)

    def get_success_url(self):
        # TODO: callback_url?
        return self.get_property_type().get_absolute_url()


class CTypePropertiesDeletion(generic.base.EntityCTypeRelatedMixin,
                              generic.CremeDeletion):
    ptype_id_arg = 'ptype_id'
    ctype_id_arg: str = 'ct_id'

    def get_ctype_id(self):
        return get_from_POST_or_404(self.request.POST, self.ctype_id_arg, cast=int)

    def get_ptype_id(self):
        # TODO: cast=int when CremePropertyType has been reworked
        return get_from_POST_or_404(self.request.POST, self.ptype_id_arg)

    def get_success_url(self):
        return reverse('creme_core__ptype', args=(self.get_ptype_id(),))

    def perform_deletion(self, request):
        ctype = self.get_ctype()
        ptype_id = self.get_ptype_id()

        key = 'cremeentity_ptr_id'
        # NB: CremeUser.has_perm_to_change() returns False for deleted entities,
        #     but EntityCredentials.filter(perm=EntityCredentials.CHANGE, ...)
        #     does not exclude them => is this a problem??
        qs = EntityCredentials.filter(
            user=self.request.user,
            queryset=ctype.model_class()
                          .objects
                          .order_by(key)
                          .filter(properties__type=ptype_id, is_deleted=False),
            perm=EntityCredentials.CHANGE,
        )
        for page in FlowPaginator(
            queryset=qs,
            key=key,
            per_page=256,
            count=qs.count(),
        ).pages():
            with atomic():
                CremeProperty.objects.filter(
                    type_id=ptype_id,
                    creme_entity_id__in=[e.id for e in page.object_list],
                ).delete()


class PropertyTypeDeletion(generic.CremeModelDeletion):
    model = CremePropertyType
    permissions = 'creme_core.can_admin'

    ptype_id_url_kwarg = 'ptype_id'

    def get_query_kwargs(self):
        return {
            'id': self.kwargs[self.ptype_id_url_kwarg],
            'is_custom': True,
        }

    def get_success_url(self):
        # TODO: callback_url?
        return self.object.get_lv_absolute_url()


class PropertyTypeInfoBrick(Brick):
    # id = Brick.generate_id('creme_core', 'property_type_info')
    id = 'property_type_info'
    dependencies = '*'
    read_only = True
    template_name = 'creme_core/bricks/ptype-info.html'

    def __init__(self, ptype, ctypes):
        super().__init__()
        self.ptype = ptype
        self.ctypes = ctypes

    def detailview_display(self, context):
        ptype = self.ptype

        return self._render(self.get_template_context(
            context,
            ctypes=self.ctypes,
            count_stat=CremeEntity.objects.filter(properties__type=ptype).count(),
        ))


class TaggedEntitiesBrick(QuerysetBrick):
    template_name = 'creme_core/bricks/tagged-entities.html'

    id_prefix = 'tagged'

    def __init__(self, ptype, ctype):
        super().__init__()
        self.ptype = ptype
        self.ctype = ctype
        # self.id = self.generate_id(
        #     'creme_core',
        #     f'tagged-{ctype.app_label}-{ctype.model}',
        # )
        self.id = f'{self.id_prefix}-{ctype.app_label}-{ctype.model}'
        self.dependencies = (ctype.model_class(),)

    # @staticmethod
    # def parse_brick_id(brick_id) -> ContentType | None:
    #     parts = brick_id.split('-')
    #     ctype = None
    #
    #     if len(parts) == 4:
    #         try:
    #             tmp_ctype = ContentType.objects.get_by_natural_key(parts[2], parts[3])
    #         except ContentType.DoesNotExist:
    #             pass
    #         else:
    #             if issubclass(tmp_ctype.model_class(), CremeEntity):
    #                 ctype = tmp_ctype
    #
    #     return ctype
    @classmethod
    def parse_brick_id(cls, brick_id) -> ContentType | None:
        """Extract info from brick ID.

        @param brick_id: e.g. "tagged-persons-contact".
        @return A ContentType instance if valid, else None.
        """
        parts = brick_id.split('-')

        if len(parts) != 3:
            logger.warning('parse_brick_id(): the brick ID "%s" has a bad length', brick_id)
            return None

        if parts[0] != cls.id_prefix:
            logger.warning('parse_brick_id(): the brick ID "%s" has a bad prefix', brick_id)
            return None

        try:
            ctype = ContentType.objects.get_by_natural_key(parts[1], parts[2])
        except ContentType.DoesNotExist:
            logger.warning(
                'parse_brick_id(): the brick ID "%s" has an invalid ContentType key',
                brick_id,
            )
            return None

        if not issubclass(ctype.model_class(), CremeEntity):
            logger.warning(
                'parse_brick_id(): the brick ID "%s" is not related to CremeEntity',
                brick_id,
            )
            return None

        return ctype

    def detailview_display(self, context):
        ctype = self.ctype
        ptype = self.ptype

        return self._render(self.get_template_context(
            context,
            ctype.get_all_objects_for_this_type(properties__type=ptype),
            ptype_id=ptype.id,
            ctype=ctype,  # If the model is inserted in the context,
                          #  the template call it and create an instance...
        ))


class TaggedMiscEntitiesBrick(QuerysetBrick):
    # id = QuerysetBrick.generate_id('creme_core', 'misc_tagged_entities')
    id = 'misc_tagged_entities'
    dependencies = (CremeEntity,)
    template_name = 'creme_core/bricks/tagged-entities.html'

    def __init__(self, ptype, excluded_ctypes):
        super().__init__()
        self.ptype = ptype
        self.excluded_ctypes = excluded_ctypes

    def detailview_display(self, context):
        ptype = self.ptype
        btc = self.get_template_context(
            context,
            CremeEntity.objects.filter(properties__type=ptype)
                               .exclude(entity_type__in=self.excluded_ctypes),
            ptype_id=ptype.id,
            ctype=None,
        )

        CremeEntity.populate_real_entities(btc['page'].object_list)

        return self._render(btc)


class PropertyTypeDetail(generic.CremeModelDetail):
    model = CremePropertyType
    # template_name = 'creme_core/view_property_type.html'
    template_name = 'creme_core/detail/property-type.html'
    pk_url_kwarg = 'ptype_id'
    bricks_reload_url_name = 'creme_core__reload_ptype_bricks'

    # def get_context_data(self, **kwargs):
    #     context = super().get_context_data(**kwargs)
    #     context['bricks'] = self.get_bricks()
    #     context['bricks_reload_url'] = self.get_bricks_reload_url()
    #
    #     return context

    def get_bricks(self):
        ptype = self.object
        ctypes = ptype.subject_ctypes.all()

        bricks = [
            PropertyTypeInfoBrick(ptype, ctypes),
            *(
                TaggedEntitiesBrick(ptype, ctype)
                for ctype in (ctypes or entity_ctypes())
            ),
        ]

        if ctypes:
            bricks.append(TaggedMiscEntitiesBrick(ptype, excluded_ctypes=ctypes))

        return bricks

    def get_bricks_reload_url(self):
        return reverse(self.bricks_reload_url_name, args=(self.object.id,))


class PropertyTypeBricksReloading(BricksReloading):
    # check_bricks_permission = False
    ptype_id_url_kwarg = 'ptype_id'

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.ptype = None

    def get_bricks(self):
        ptype = self.get_property_type()
        bricks = []
        ctypes = ptype.subject_ctypes.all()

        for brick_id in self.get_brick_ids():
            if brick_id == PropertyTypeInfoBrick.id:
                brick = PropertyTypeInfoBrick(ptype, ctypes)
            elif brick_id == TaggedMiscEntitiesBrick.id:
                brick = TaggedMiscEntitiesBrick(ptype, ctypes)
            else:
                ctype = TaggedEntitiesBrick.parse_brick_id(brick_id)
                if ctype is None:
                    raise Http404(f'Invalid brick id "{brick_id}"')

                brick = TaggedEntitiesBrick(ptype, ctype)

            bricks.append(brick)

        return bricks

    def get_bricks_context(self):
        context = super().get_bricks_context()
        context['object'] = self.get_property_type()

        return context

    def get_property_type(self):
        ptype = self.ptype

        if ptype is None:
            self.ptype = ptype = get_object_or_404(
                CremePropertyType,
                id=self.kwargs[self.ptype_id_url_kwarg],
            )

        return ptype
