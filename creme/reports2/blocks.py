# -*- coding: utf-8 -*-

################################################################################
#    Creme is a free/open-source Customer Relationship Management software
#    Copyright (C) 2009-2010  Hybird
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

from django.utils.translation import ugettext_lazy as _

from creme_core.gui.block import Block
from creme_core.models.header_filter import HFI_FIELD, HFI_RELATION

#from reports2.models import report_template_dir, report_prefix_url
from reports2.models import Field, report_template_dir


class ReportFieldsBlock(Block):
    id_           = Block.generate_id('reports2', 'fields')
    dependencies  = (Field,)
    verbose_name  = _(u"Colonnes du rapport")
    template_name = '%s/templatetags/block_report_fields.html' % report_template_dir

    def detailview_display(self, context):
        object = context['object']
        return self._render(self.get_block_template_context(context,
                                                            #update_url='%s/%s/fields_block/reload/' % (report_prefix_url, object.id),
                                                            update_url='/creme_core/blocks/reload/%s/%s/' % (self.id_, object.pk),
                                                            HFI_FIELD=HFI_FIELD,
                                                            HFI_RELATION=HFI_RELATION)
                            )

report_fields_block = ReportFieldsBlock()
