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

from django.utils.translation import gettext_lazy as _

from creme.creme_core.gui.button_menu import Button
from creme.creme_core.models import Relation, RelationType

from . import constants


class CompleteGoalButton(Button):
    id = Button.generate_id('commercial', 'complete_goal')
    verbose_name = _('Completes a goal (Commercial action)')
    description = _(
        'This button links the current entity with a selected commercial action, '
        'using the relationship type «completes a goal of the commercial action».\n'
        'App: Commercial'
    )
    dependencies = (Relation,)
    relation_type_deps = (constants.REL_SUB_COMPLETE_GOAL,)
    template_name = 'commercial/buttons/complete-goal.html'
    permissions = 'commercial'

    def check_permissions(self, *, entity, request):
        super().check_permissions(entity=entity, request=request)
        request.user.has_perm_to_link_or_die(entity)

    def get_context(self, **kwargs):
        context = super().get_context(**kwargs)
        context['rtype'] = RelationType.objects.get(id=self.relation_type_deps[0])

        return context
