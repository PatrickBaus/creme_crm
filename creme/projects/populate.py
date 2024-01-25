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

import logging

from django.apps import apps
from django.utils.translation import gettext as _

import creme.creme_core.bricks as core_bricks
from creme.activities import get_activity_model
from creme.creme_core.core.entity_cell import EntityCellRegularField
from creme.creme_core.gui.menu import ContainerEntry
from creme.creme_core.management.commands.creme_populate import BasePopulator
from creme.creme_core.models import (
    BrickDetailviewLocation,
    CustomFormConfigItem,
    HeaderFilter,
    MenuConfigItem,
    RelationType,
    SearchConfigItem,
)
from creme.creme_core.utils import create_if_needed
from creme.persons import get_contact_model

from . import (
    bricks,
    constants,
    custom_forms,
    get_project_model,
    get_task_model,
)
from .menu import ProjectsEntry
from .models import ProjectStatus, TaskStatus

logger = logging.getLogger(__name__)


class Populator(BasePopulator):
    dependencies = ['creme_core', 'persons', 'activities']

    SEARCH = {
        'PROJECT': ['name', 'description', 'status__name'],
        'TASK': ['linked_project__name', 'duration', 'tstatus__name'],
    }
    PROJECT_STATUSES = [
        # (name, description)
        (
            _('Invitation to tender'),
            _('Response to an invitation to tender'),
        ), (
            _('Initialization'),
            _('The project is starting'),
        ), (
            _('Preliminary phase'),
            _('The project is in the process of analysis and design'),
        ), (
            _('Achievement'),
            _('The project is being implemented'),
        ), (
            _('Tests'),
            _('The project is in the testing process (unit / integration / functional)'),
        ), (
            _('User acceptance tests'),
            _('The project is in the user acceptance testing process'),
        ), (
            _('Finished'),
            _('The project is finished')
        ),
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.Contact  = get_contact_model()
        self.Activity = get_activity_model()

        self.Project     = get_project_model()
        self.ProjectTask = get_task_model()

    def _already_populated(self):
        return RelationType.objects.filter(
            pk=constants.REL_SUB_PROJECT_MANAGER,
        ).exists()

    def _populate(self):
        super()._populate()
        self._populate_task_statuses()

    def _first_populate(self):
        super()._first_populate()
        self._populate_project_statuses()

    def _populate_task_statuses(self):
        for pk, statusdesc in constants.TASK_STATUS.items():
            create_if_needed(
                TaskStatus, {'pk': pk}, name=str(statusdesc.name), order=pk,
                description=str(statusdesc.verbose_name), is_custom=False,
            )

    def _populate_project_statuses(self):
        for pk, (name, description) in enumerate(self.PROJECT_STATUSES, start=1):
            create_if_needed(
                ProjectStatus, {'pk': pk},
                name=name, order=pk, description=description,
            )

    def _populate_relation_types(self):
        create_rtype = RelationType.objects.smart_update_or_create
        create_rtype(
            (
                constants.REL_SUB_PROJECT_MANAGER,
                _('is one of the leaders of this project'),
                [self.Contact],
            ), (
                constants.REL_OBJ_PROJECT_MANAGER,
                _('has as leader'),
                [self.Project],
            ),
        )
        create_rtype(
            (
                constants.REL_SUB_LINKED_2_PTASK,
                _('is related to the task of project'),
                [self.Activity],
            ), (
                constants.REL_OBJ_LINKED_2_PTASK,
                _('includes the activity'),
                [self.ProjectTask],
            ),
            is_internal=True,
            minimal_display=(False, True),
        )
        create_rtype(
            (constants.REL_SUB_PART_AS_RESOURCE, _('is a resource of'),  [self.Contact]),
            (constants.REL_OBJ_PART_AS_RESOURCE, _('has as a resource'), [self.Activity]),
            is_internal=True,
        )

    def _populate_header_filters(self):
        create_hf = HeaderFilter.objects.create_if_needed
        create_hf(
            pk=constants.DEFAULT_HFILTER_PROJECT,
            model=self.Project,
            name=_('Project view'),
            cells_desc=[
                (EntityCellRegularField, {'name': 'name'}),
                (EntityCellRegularField, {'name': 'start_date'}),
                (EntityCellRegularField, {'name': 'end_date'}),
                (EntityCellRegularField, {'name': 'status'}),
                (EntityCellRegularField, {'name': 'description'}),
            ],
        )

        # Used in form
        create_hf(
            pk='projects-hf_task', name=_('Task view'), model=self.ProjectTask,
            cells_desc=[
                (EntityCellRegularField, {'name': 'title'}),
                (EntityCellRegularField, {'name': 'description'}),
            ],
        )

    def _populate_custom_forms(self):
        create_cfci = CustomFormConfigItem.objects.create_if_needed
        create_cfci(descriptor=custom_forms.PROJECT_CREATION_CFORM)
        create_cfci(descriptor=custom_forms.PROJECT_EDITION_CFORM)
        create_cfci(descriptor=custom_forms.TASK_CREATION_CFORM)
        create_cfci(descriptor=custom_forms.TASK_EDITION_CFORM)

    def _populate_search_config(self):
        create_sci = SearchConfigItem.objects.create_if_needed
        create_sci(model=self.Project,     fields=self.SEARCH['PROJECT'])
        create_sci(model=self.ProjectTask, fields=self.SEARCH['TASK'])

    def _populate_menu_config(self):
        menu_container = MenuConfigItem.objects.get_or_create(
            entry_id=ContainerEntry.id,
            entry_data={'label': _('Tools')},
            defaults={'order': 100},
        )[0]

        MenuConfigItem.objects.create(
            entry_id=ProjectsEntry.id, parent=menu_container, order=50,
        )

    def _populate_bricks_config(self):
        TOP = BrickDetailviewLocation.TOP
        LEFT = BrickDetailviewLocation.LEFT
        RIGHT = BrickDetailviewLocation.RIGHT

        BrickDetailviewLocation.objects.multi_create(
            defaults={'model': self.Project, 'zone': LEFT},
            data=[
                {'brick': bricks.ProjectTasksBrick, 'order': 2, 'zone': TOP},

                {'order': 5},
                {'brick': bricks.ProjectExtraInfoBrick,  'order':  30},
                {'brick': core_bricks.CustomFieldsBrick, 'order':  40},
                {'brick': core_bricks.PropertiesBrick,   'order': 450},
                {'brick': core_bricks.RelationsBrick,    'order': 500},

                {'brick': core_bricks.HistoryBrick, 'order': 20, 'zone': RIGHT},
            ],
        )
        BrickDetailviewLocation.objects.multi_create(
            defaults={'model': self.ProjectTask, 'zone': LEFT},
            data=[
                {'brick': bricks.TaskResourcesBrick,  'order': 2, 'zone': TOP},
                {'brick': bricks.TaskActivitiesBrick, 'order': 4, 'zone': TOP},

                {'order': 5},
                {'brick': bricks.TaskExtraInfoBrick,     'order':  30},
                {'brick': core_bricks.CustomFieldsBrick, 'order':  40},
                {'brick': bricks.ParentTasksBrick,       'order':  50},
                {'brick': core_bricks.PropertiesBrick,   'order': 450},
                {'brick': core_bricks.RelationsBrick,    'order': 500},

                {'brick': core_bricks.HistoryBrick, 'order': 20, 'zone': RIGHT},
            ],
        )

        if apps.is_installed('creme.assistants'):
            logger.info(
                'Assistants app is installed'
                ' => we use the assistants blocks on detail views'
            )

            import creme.assistants.bricks as a_bricks

            for model in (self.Project, self.ProjectTask):
                BrickDetailviewLocation.objects.multi_create(
                    defaults={'model': model, 'zone': RIGHT},
                    data=[
                        {'brick': a_bricks.TodosBrick, 'order':        100},
                        {'brick': a_bricks.MemosBrick, 'order':        200},
                        {'brick': a_bricks.AlertsBrick, 'order':       300},
                        {'brick': a_bricks.UserMessagesBrick, 'order': 400},
                    ],
                )

        if apps.is_installed('creme.documents'):
            # logger.info('Documents app is installed
            # => we use the documents block on detail views')

            from creme.documents.bricks import LinkedDocsBrick

            BrickDetailviewLocation.objects.multi_create(
                defaults={'brick': LinkedDocsBrick, 'order': 600, 'zone': RIGHT},
                data=[{'model': model} for model in (self.Project, self.ProjectTask)],
            )
