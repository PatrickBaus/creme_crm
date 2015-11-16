# -*- coding: utf-8 -*-

try:
    from functools import partial

    from django.contrib.contenttypes.models import ContentType

    from creme.creme_core.tests.base import CremeTestCase
    from creme.creme_core.constants import PROP_IS_MANAGED_BY_CREME
    from creme.creme_core.models import (RelationType, CremeProperty, Vat,
            SettingValue, BlockDetailviewLocation)

    from creme.persons import get_contact_model, get_organisation_model
    from creme.persons.models import Organisation
    from creme.persons.tests.base import skipIfCustomOrganisation

    from creme.products import get_product_model, get_service_model

    from .. import (get_invoice_model, get_quote_model, get_sales_order_model,
            get_credit_note_model, get_template_base_model,
            get_product_line_model, get_service_line_model)
    from ..blocks import persons_statistics_block
    from ..constants import *
    from ..models import (InvoiceStatus, SalesOrderStatus, CreditNoteStatus,
            ConfigBillingAlgo, SimpleBillingAlgo)
    from .base import _BillingTestCase
except Exception as e:
    print('Error in <%s>: %s' % (__name__, e))


class AppTestCase(_BillingTestCase, CremeTestCase):
    def test_populate(self):
        Organisation = get_organisation_model()
        Contact = get_contact_model()
        Product = get_product_model()
        Service = get_service_model()

        Invoice    = get_invoice_model()
        Quote      = get_quote_model()
        SalesOrder = get_sales_order_model()

#        billing_classes = [Invoice, Quote, SalesOrder, CreditNote, TemplateBase]
#        lines_clases = [ProductLine, ServiceLine] #Line
        billing_classes = [Invoice, Quote, SalesOrder,
                           get_credit_note_model(), get_template_base_model(),
                          ]
        lines_clases = [get_product_line_model(), get_service_line_model()] #Line

        self.get_relationtype_or_fail(REL_SUB_BILL_ISSUED,       billing_classes, [Organisation])
        self.get_relationtype_or_fail(REL_SUB_BILL_RECEIVED,     billing_classes, [Organisation, Contact])
        self.get_relationtype_or_fail(REL_SUB_HAS_LINE,          billing_classes, lines_clases)
        self.get_relationtype_or_fail(REL_SUB_LINE_RELATED_ITEM, lines_clases,    [Product, Service])

        self.assertEqual(1, SalesOrderStatus.objects.filter(pk=1).count())
        self.assertEqual(2, InvoiceStatus.objects.filter(pk__in=(1, 2)).count())
        self.assertEqual(1, CreditNoteStatus.objects.filter(pk=1).count())

        #self.assertEqual(5, Vat.objects.count()) #in creme_core populate...
        self.assertTrue(Vat.objects.exists()) #in creme_core populate...

        #contribution to activities
        from creme.activities.constants import REL_SUB_ACTIVITY_SUBJECT

        rtype = self.get_object_or_fail(RelationType, pk=REL_SUB_ACTIVITY_SUBJECT)
        get_ct = ContentType.objects.get_for_model
        ct_ids = [get_ct(m).id for m in (Invoice, Quote, SalesOrder)]
        self.assertEqual(len(ct_ids), rtype.subject_ctypes.filter(id__in=ct_ids).count())
        self.assertTrue(rtype.subject_ctypes.filter(id=get_ct(Contact).id).exists())
        self.assertEqual(len(ct_ids), rtype.symmetric_type.object_ctypes.filter(id__in=ct_ids).count())

    def test_portal(self):
        self.login()
        self.assertGET200('/billing/')

    @skipIfCustomOrganisation
    def test_algoconfig(self):
        user = self.login()

        Invoice    = get_invoice_model()
        Quote      = get_quote_model()
        SalesOrder = get_sales_order_model()

        orga = Organisation.objects.create(user=user, name='NERV')

        self.assertFalse(ConfigBillingAlgo.objects.filter(organisation=orga))
        self.assertFalse(SimpleBillingAlgo.objects.filter(organisation=orga))

        self._set_managed(orga)

        algoconfs = ConfigBillingAlgo.objects.filter(organisation=orga)
        self.assertEqual(['SIMPLE_ALGO'] * 3, [algoconf.name_algo for algoconf in algoconfs])
        self.assertEqual({Quote, Invoice, SalesOrder},
                         {algoconf.ct.model_class() for algoconf in algoconfs}
                        )

        simpleconfs = SimpleBillingAlgo.objects.filter(organisation=orga)
        self.assertEqual([0] * 3, [simpleconf.last_number for simpleconf in simpleconfs])
        self.assertEqual({Quote, Invoice, SalesOrder},
                         {simpleconf.ct.model_class() for simpleconf in simpleconfs}
                        )

    def _merge_organisations(self, orga1, orga2):
        user = self.user
        response = self.client.post(self.build_merge_url(orga1, orga2), follow=True,
                                    data={'user_1':      user.id,
                                          'user_2':      user.id,
                                          'user_merged': user.id,

                                          'name_1':      orga1.name,
                                          'name_2':      orga2.name,
                                          'name_merged': orga1.name,
                                         }
                                   )
        self.assertNoFormError(response)
        self.assertStillExists(orga1)
        self.assertDoesNotExist(orga2)

    def _remove_managed_prop(self, orga):
        CremeProperty.objects.get(type=PROP_IS_MANAGED_BY_CREME, creme_entity=orga).delete()

    def _ids_list(self, queryset, length):
        ids_list = list(queryset.values_list('id', flat=True))
        self.assertEqual(length, len(ids_list))

        return ids_list

    @skipIfCustomOrganisation
    def test_merge_algoconfig01(self):
        "One managed organisation"
        user = self.login()

        create_orga = partial(Organisation.objects.create, user=user)
        orga1 = create_orga(name='NERV')
        orga2 = create_orga(name='Nerv'); self._set_managed(orga2)

        cba_filter = ConfigBillingAlgo.objects.filter
        sba_filter = SimpleBillingAlgo.objects.filter
        self.assertFalse(cba_filter(organisation=orga1))
        self.assertFalse(sba_filter(organisation=orga1))

        cba_ids_list2 = self._ids_list(cba_filter(organisation=orga2), 3)
        sba_ids_list2 = self._ids_list(sba_filter(organisation=orga2), 3)

        self._merge_organisations(orga1, orga2)

        cba_list2 = list(cba_filter(pk__in=cba_ids_list2))
        self.assertEqual(3, len(cba_list2))
        self.assertEqual(orga1, cba_list2[0].organisation)

        sba_list2 = list(sba_filter(pk__in=sba_ids_list2))
        self.assertEqual(3, len(sba_list2))
        self.assertEqual(orga1, sba_list2[0].organisation)

    @skipIfCustomOrganisation
    def test_merge_algoconfig02(self):
        "Two managed organisations"
        user = self.login()

        create_orga = partial(Organisation.objects.create, user=user)
        orga1 = create_orga(name='NERV'); self._set_managed(orga1)
        orga2 = create_orga(name='Nerv'); self._set_managed(orga2)

        cba_filter = ConfigBillingAlgo.objects.filter
        sba_filter = SimpleBillingAlgo.objects.filter
        cba_ids_list1 = self._ids_list(cba_filter(organisation=orga1), 3)
        sba_ids_list1 = self._ids_list(sba_filter(organisation=orga1), 3)

        cba_ids_list2 = self._ids_list(cba_filter(organisation=orga2), 3)
        sba_ids_list2 = self._ids_list(sba_filter(organisation=orga2), 3)

        self._merge_organisations(orga1, orga2)

        self.assertFalse(cba_filter(pk__in=cba_ids_list2))
        self.assertEqual(3, cba_filter(pk__in=cba_ids_list1).count())

        self.assertFalse(sba_filter(pk__in=sba_ids_list2))
        self.assertEqual(3, sba_filter(pk__in=sba_ids_list1).count())

    @skipIfCustomOrganisation
    def test_merge_algoconfig03(self):
        "Two managed with algo config, but not managed"
        user = self.login()

        create_orga = partial(Organisation.objects.create, user=user)
        orga1 = create_orga(name='NERV'); self._set_managed(orga1)
        orga2 = create_orga(name='Nerv'); self._set_managed(orga2)

        self._remove_managed_prop(orga1)
        self._remove_managed_prop(orga2)

        cba_filter = ConfigBillingAlgo.objects.filter
        sba_filter = SimpleBillingAlgo.objects.filter
        cba_ids_list1 = self._ids_list(cba_filter(organisation=orga1), 3)
        sba_ids_list1 = self._ids_list(sba_filter(organisation=orga1), 3)

        cba_ids_list2 = self._ids_list(cba_filter(organisation=orga2), 3)
        sba_ids_list2 = self._ids_list(sba_filter(organisation=orga2), 3)

        self._merge_organisations(orga1, orga2)

        self.assertFalse(cba_filter(pk__in=cba_ids_list2))
        self.assertEqual(3, cba_filter(pk__in=cba_ids_list1).count())

        self.assertFalse(sba_filter(pk__in=sba_ids_list2))
        self.assertEqual(3, sba_filter(pk__in=sba_ids_list1).count())

    @skipIfCustomOrganisation
    def test_merge_algoconfig04(self):
        """Two managed with algo config, but only the second is managed
            => we delete the config of the first one.
        """
        user = self.login()

        create_orga = partial(Organisation.objects.create, user=user)
        orga1 = create_orga(name='NERV'); self._set_managed(orga1)
        orga2 = create_orga(name='Nerv'); self._set_managed(orga2)

        self._remove_managed_prop(orga1)

        cba_filter = ConfigBillingAlgo.objects.filter
        sba_filter = SimpleBillingAlgo.objects.filter
        cba_ids_list1 = self._ids_list(cba_filter(organisation=orga1), 3)
        sba_ids_list1 = self._ids_list(sba_filter(organisation=orga1), 3)

        cba_ids_list2 = self._ids_list(cba_filter(organisation=orga2), 3)
        sba_ids_list2 = self._ids_list(sba_filter(organisation=orga2), 3)

        self._merge_organisations(orga1, orga2)

        self.assertFalse(cba_filter(pk__in=cba_ids_list1))
        self.assertEqual(3, cba_filter(pk__in=cba_ids_list2).count())

        self.assertFalse(sba_filter(pk__in=sba_ids_list1))
        self.assertEqual(3, sba_filter(pk__in=sba_ids_list2).count())

    def _get_setting_value(self):
        return self.get_object_or_fail(SettingValue, key_id=DISPLAY_PAYMENT_INFO_ONLY_CREME_ORGA)

    @skipIfCustomOrganisation
    def test_block_orga01(self):
        self.login()

        sv = self._get_setting_value()
        self.assertIs(True, sv.value)

        orga = Organisation.objects.create(user=self.user, name='NERV')

        response = self.assertGET200(orga.get_absolute_url())
        payment_info_tlpt = 'billing/templatetags/block_payment_information.html'
        self.assertTemplateNotUsed(response, payment_info_tlpt)
        self.assertTemplateUsed(response, 'billing/templatetags/block_received_invoices.html')
        self.assertTemplateUsed(response, 'billing/templatetags/block_received_billing_document.html')

        sv.value = False
        sv.save()

        response = self.assertGET200(orga.get_absolute_url())
        self.assertTemplateUsed(response, payment_info_tlpt)

    @skipIfCustomOrganisation
    def test_block_orga02(self):
        "Managed organisation"
        self.login()

        orga = Organisation.objects.create(user=self.user, name='NERV')
        self._set_managed(orga)

        response = self.assertGET200(orga.get_absolute_url())
        payment_info_tlpt = 'billing/templatetags/block_payment_information.html'
        self.assertTemplateUsed(response, payment_info_tlpt)
        self.assertTemplateUsed(response, 'billing/templatetags/block_received_invoices.html')
        self.assertTemplateUsed(response, 'billing/templatetags/block_received_billing_document.html')

        sv = self._get_setting_value()
        sv.value = False
        sv.save()

        response = self.assertGET200(orga.get_absolute_url())
        self.assertTemplateUsed(response, payment_info_tlpt)

    @skipIfCustomOrganisation
    def test_block_orga03(self):
        "Statistics"
        self.login()

        orga = Organisation.objects.create(user=self.user, name='NERV')

        BlockDetailviewLocation.create(block_id=persons_statistics_block.id_, order=1000,
                                        zone=BlockDetailviewLocation.LEFT, model=Organisation,
                                       )

        response = self.assertGET200(orga.get_absolute_url())
        self.assertTemplateUsed(response, 'billing/templatetags/block_persons_statistics.html')
        self.assertContains(response, 'id="%s"' % persons_statistics_block.id_)
