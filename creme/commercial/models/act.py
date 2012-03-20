# -*- coding: utf-8 -*-

################################################################################
#    Creme is a free/open-source Customer Relationship Management software
#    Copyright (C) 2009-2012  Hybird
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
from functools import partial

from django.core.exceptions import ValidationError
from django.db.models import (CharField, TextField, PositiveIntegerField, DateField,
                              BooleanField, ForeignKey, PROTECT)
from django.db.models.signals import post_save
from django.utils.translation import ugettext_lazy as _, ugettext
from django.contrib.contenttypes.models import ContentType

from creme_core.models import CremeEntity, CremeModel, Relation

from opportunities.models import Opportunity

from activities.constants import REL_OBJ_ACTIVITY_SUBJECT

from commercial.models import MarketSegment
from commercial.constants import REL_SUB_COMPLETE_GOAL


_NAME_LENGTH = 100


class ActType(CremeModel):
    title     = CharField(_(u"Title"), max_length=75)
    is_custom = BooleanField(default=True) #used by creme_config

    class Meta:
        app_label = "commercial"
        verbose_name = _(u'Type of Commercial Action')
        verbose_name_plural = _(u'Types of Commercial Actions')

    def __unicode__(self):
        return self.title


class Act(CremeEntity):
    name           = CharField(_(u"Name of the commercial action"), max_length=100)
    expected_sales = PositiveIntegerField(_(u'Expected sales'))
    cost           = PositiveIntegerField(_(u"Cost of the commercial action"), blank=True, null=True)
    goal           = TextField(_(u"Goal of the action"), blank=True, null=True)
    start          = DateField(_(u'Start'))
    due_date       = DateField(_(u'Due date'))
    act_type       = ForeignKey(ActType, verbose_name=_(u'Type'), on_delete=PROTECT)
    segment        = ForeignKey(MarketSegment, verbose_name=_(u'Related segment'))

    _related_opportunities = None

    class Meta:
        app_label = "commercial"
        verbose_name = _(u'Commercial Action')
        verbose_name_plural = _(u'Commercial Actions')

    def __unicode__(self):
        return self.name

    def clean(self):
        if self.due_date < self.start:
            raise ValidationError(ugettext(u"Due date can't be before start."))

    def get_absolute_url(self):
        return "/commercial/act/%s" % self.id

    def get_edit_absolute_url(self):
        return "/commercial/act/edit/%s" % self.id

    @staticmethod
    def get_lv_absolute_url():
        return "/commercial/acts"

    def get_made_sales(self):
        return sum(o.made_sales for o in self.get_related_opportunities() if o.made_sales)

    def get_related_opportunities(self):
        relopps = self._related_opportunities

        if relopps is None:
            relopps = list(Opportunity.objects.filter(relations__type=REL_SUB_COMPLETE_GOAL,
                                                      relations__object_entity=self.id)
                          )
            self._related_opportunities = relopps

        return relopps

    def _post_save_clone(self, source):
        #TODO: use bulk_create() when django 1.4
        ActObjective_create = ActObjective.objects.create
        for act_objective in ActObjective.objects.filter(act=source):
            ActObjective_create(name=act_objective.name,
                                act=self,
                                counter=act_objective.counter,
                                counter_goal=act_objective.counter_goal,
                                ctype=act_objective.ctype)


class ActObjective(CremeModel):
    name         = CharField(_(u"Name"), max_length=_NAME_LENGTH)
    act          = ForeignKey(Act, related_name='objectives')
    counter      = PositiveIntegerField(_(u'Counter'), default=0)
    counter_goal = PositiveIntegerField(_(u'Value to reach'), default=1)
    ctype        = ForeignKey(ContentType, verbose_name=_(u'Counted type'), null=True, blank=True)

    _count_cache = None

    class Meta:
        app_label = "commercial"
        verbose_name = _(u'Commercial Objective')
        verbose_name_plural = _(u'Commercial Objectives')

    def __unicode__(self):
        return self.name

    def get_related_entity(self): #NB: see edit_related_to_entity()
        return self.act

    def get_count(self):
        if self._count_cache is None:
            self._count_cache =  self.counter if not self.ctype else \
                                 Relation.objects.filter(type=REL_SUB_COMPLETE_GOAL,
                                                         object_entity=self.act_id,
                                                         subject_entity__entity_type=self.ctype_id) \
                                                 .count()

        return self._count_cache

    @property
    def reached(self):
        return self.get_count() >= self.counter_goal


class ActObjectivePattern(CremeEntity):
    name          = CharField(_(u"Name"), max_length=100)
    average_sales = PositiveIntegerField(_(u'Average sales'))
    segment       = ForeignKey(MarketSegment, verbose_name=_(u'Related segment'))

    _components_cache = None

    class Meta:
        app_label = "commercial"
        verbose_name = _(u'Commercial objective pattern')
        verbose_name_plural = _(u'Commercial objective patterns')

    def __unicode__(self):
        return self.name

    def get_absolute_url(self):
        return "/commercial/objective_pattern/%s" % self.id

    def get_edit_absolute_url(self):
        return "/commercial/objective_pattern/edit/%s" % self.id

    @staticmethod
    def get_lv_absolute_url():
        return "/commercial/objective_patterns"

    def get_components_tree(self):
        """Get (and cache) the ActObjectivePatternComponent objects tree related
        to this pattern, with only one query.
        @see ActObjectivePatternComponent.get_children
        """
        root_components = self._components_cache

        if root_components is None:
            components = dict((comp.id, comp) for comp  in self.components.all())
            root_components = []

            for comp in components.itervalues():
                comp._children_cache = []

            for comp in components.itervalues():
                children = components[comp.parent_id]._children_cache if comp.parent_id else root_components
                children.append(comp)

            self._components_cache = root_components

        return root_components

    def _post_save_clone(self, source):
        for pattern_component in source.get_components_tree():
            pattern_component.clone(self)


class ActObjectivePatternComponent(CremeModel):
    pattern      = ForeignKey(ActObjectivePattern, related_name='components')
    parent       = ForeignKey('self', null=True, related_name='children')
    name         = CharField(_(u"Name"), max_length=_NAME_LENGTH)
    ctype        = ForeignKey(ContentType, verbose_name=_(u'Counted type'), null=True, blank=True)
    success_rate = PositiveIntegerField(_(u'Success rate')) #smallinteger ??

    _children_cache = None

    class Meta:
        app_label = "commercial"

    def __unicode__(self):
        return self.name

    #TODO: delete this code with new ForeignKey in Django1.3 ?? (maybe it causes more queries)
    def delete(self):
        def find_node(nodes, pk):
            for node in nodes:
                if node.id == pk:
                    return node

                found = find_node(node.get_children(), pk)

                if found: return found

        def flatten_node_ids(node, node_list):
            node_list.append(node.id)

            for child in node.get_children():
                flatten_node_ids(child, node_list)

        children2del = []

        #TODO: tree may inherit from a smart tree strucrure with right method like found()/flatten() etc...
        flatten_node_ids(find_node(self.pattern.get_components_tree(), self.id), children2del)
        ActObjectivePatternComponent.objects.filter(pk__in=children2del).delete()
        #NB super(ActObjectivePatternComponent, self).delete() is not called

    def get_children(self):
        children = self._children_cache

        if children is None:
            self._children_cache = children = list(self.children.all())

        return children

    def get_related_entity(self): #NB: see delete_related_to_entity()
        return self.pattern

    def clone(self, pattern, parent=None):
        """Clone the entire hierarchy of the node wherever is it"""
        own_parent = None
        if self.parent and not parent:
            own_parent = self.parent.clone(pattern)

        me = ActObjectivePatternComponent.objects.create(pattern=pattern,
                                                   parent=own_parent or parent,
                                                   name=self.name,
                                                   ctype=self.ctype,
                                                   success_rate=self.success_rate)

        for sub_aopc in self.children.all():
            sub_aopc.clone(pattern, me)


#Catching the save of the relation between an activity and an opportunity as a subject
def post_save_relation_opp_subject_activity(sender, instance, **kwargs):
    if instance.type_id == REL_OBJ_ACTIVITY_SUBJECT:
        object_entity = instance.object_entity
        if object_entity.entity_type == ContentType.objects.get_for_model(Opportunity):
            relations = Relation.objects.filter(subject_entity=object_entity,
                                                type=REL_SUB_COMPLETE_GOAL,
                                                object_entity__entity_type=ContentType.objects.get_for_model(Act))

            create_relation = partial(Relation.objects.create, subject_entity=instance.subject_entity,
                                                               type_id=REL_SUB_COMPLETE_GOAL,
                                                               user=instance.user
                                     )
            for relation in relations:
                create_relation(object_entity=relation.object_entity)

post_save.connect(post_save_relation_opp_subject_activity, sender=Relation)


