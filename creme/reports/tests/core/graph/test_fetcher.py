# -*- coding: utf-8 -*-

try:
    from django.utils.translation import gettext as _, pgettext

    from creme.creme_core.models import (
        FieldsConfig,
        InstanceBrickConfigItem,
        FakeOrganisation, FakeContact, FakeImage,
    )
    from creme.creme_core.tests.base import CremeTestCase
    from creme.creme_core.tests.fake_constants import (
        FAKE_REL_SUB_EMPLOYED_BY,
        FAKE_REL_SUB_BILL_ISSUED,
    )

    from creme.reports.bricks import ReportGraphBrick
    from creme.reports.constants import (
        RGT_YEAR,
        RGA_COUNT,
        RGF_NOLINK, RGF_FK, RGF_RELATION,
    )
    from creme.reports.core.graph.fetcher import (
        GraphFetcher,
        SimpleGraphFetcher,
        RegularFieldLinkedGraphFetcher,
        RelationLinkedGraphFetcher,
    )
    from creme.reports.graph_fetcher_registry import GraphFetcherRegistry
    from creme.reports.tests.base import (
        Report, ReportGraph,
    )
except Exception as e:
    print(f'Error in <{__name__}>: {e}')


# TODO: test fetch() ??
class GraphFetcherTestCase(CremeTestCase):
    def test_simple(self):
        user = self.create_user()
        report = Report.objects.create(user=user, name='Field Test', ct=FakeContact)
        graph = ReportGraph.objects.create(
            user=user, name='Field Test', linked_report=report,
            abscissa_cell_value='created', abscissa_type=RGT_YEAR,
            ordinate_type=RGA_COUNT,
        )

        fetcher1 = SimpleGraphFetcher(graph=graph)
        self.assertIsNone(fetcher1.error)
        self.assertEqual(_('No volatile column'), fetcher1.verbose_name)

        ibci = fetcher1.create_brick_config_item()
        self.assertIsInstance(ibci, InstanceBrickConfigItem)
        self.assertEqual(graph.id, ibci.entity_id)
        self.assertEqual(ReportGraphBrick.id_, ibci.brick_class_id)
        self.assertEqual(RGF_NOLINK, ibci.get_extra_data('type'))
        self.assertIsNone(ibci.get_extra_data('value'))

        # ---
        fetcher2 = SimpleGraphFetcher(graph=graph, value='last_name')
        self.assertEqual(
            _('No value is needed.'),
            fetcher2.error
        )

        self.assertListEqual(
            [('', pgettext('reports-volatile_choice', 'None'))],
            [*SimpleGraphFetcher.choices(FakeContact)]
        )

        # ----
        # TODO: move to test for bricks ?
        brick = ReportGraphBrick(ibci)
        self.assertIsNone(brick.errors)
        self.assertEqual(
            '{} - {}'.format(graph.name, _('No volatile column')),
            brick.verbose_name
        )
        self.assertListEqual([], brick.target_ctypes)

        b_fetcher = brick.fetcher
        self.assertIsInstance(b_fetcher, SimpleGraphFetcher)
        self.assertIsNone(b_fetcher.error)
        self.assertEqual(graph, b_fetcher.graph)

    def test_fk01(self):
        user = self.create_user()
        report = Report.objects.create(user=user, name='Field Test', ct=FakeContact)
        graph = ReportGraph.objects.create(
            user=user, name='Field Test', linked_report=report,
            abscissa_cell_value='created', abscissa_type=RGT_YEAR,
            ordinate_type=RGA_COUNT,
        )

        fname = 'image'
        fetcher1 = RegularFieldLinkedGraphFetcher(graph=graph, value=fname)
        self.assertIsNone(fetcher1.error)
        self.assertEqual(
            _('{field} (Field)').format(field=_('Photograph')),
            fetcher1.verbose_name
        )

        ibci = fetcher1.create_brick_config_item()
        self.assertEqual(RGF_FK, ibci.get_extra_data('type'))
        self.assertEqual(fname, ibci.get_extra_data('value'))

        fetcher2 = RegularFieldLinkedGraphFetcher(graph=graph)
        self.assertEqual(
            _('No field given.'),
            fetcher2.error
        )
        self.assertEqual('??', fetcher2.verbose_name)

        fetcher3 = RegularFieldLinkedGraphFetcher(graph=graph, value='invalid')
        self.assertEqual(
            _('The field is invalid.'),
            fetcher3.error
        )

        fetcher4 = RegularFieldLinkedGraphFetcher(graph=graph, value='last_name')
        self.assertEqual(
            _('The field is invalid (not a foreign key).'),
            fetcher4.error
        )

        fetcher5 = RegularFieldLinkedGraphFetcher(graph=graph, value='position')
        self.assertEqual(
            _('The field is invalid (not a foreign key to CremeEntity).'),
            fetcher5.error
        )

        self.assertListEqual(
            [(f'image', _('Photograph'))],
            [*RegularFieldLinkedGraphFetcher.choices(FakeContact)]
        )

        # ----
        # TODO: move to test for bricks ?
        brick = ReportGraphBrick(ibci)
        self.assertIsNone(brick.errors)
        self.assertEqual(
            '{} - {}'.format(
                graph.name,
                _('{field} (Field)').format(field=_('Photograph')),
            ),
            brick.verbose_name
        )
        self.assertListEqual([FakeImage], brick.target_ctypes)

        b_fetcher = brick.fetcher
        self.assertIsInstance(b_fetcher, RegularFieldLinkedGraphFetcher)
        self.assertIsNone(b_fetcher.error)
        # self.assertEqual(fname, b_fetcher._field_name)
        self.assertEqual(fname, b_fetcher._field.name)

    def test_fk02(self):
        "Hidden field."
        hidden_fname = 'image'
        FieldsConfig.objects.create(
            content_type=FakeContact,
            descriptions=[(hidden_fname, {FieldsConfig.HIDDEN: True})],
        )

        user = self.create_user()
        report = Report.objects.create(user=user, name='Field Test', ct=FakeContact)
        graph = ReportGraph(user=user, name='Field Test', linked_report=report)

        fetcher = RegularFieldLinkedGraphFetcher(graph=graph, value=hidden_fname)
        self.assertEqual(
            _('The field is hidden.'),
            fetcher.error
        )

    def test_relation(self):
        user = self.create_user()
        report = Report.objects.create(user=user, name='Field Test', ct=FakeContact)
        graph = ReportGraph.objects.create(
            user=user, name='Field Test', linked_report=report,
            abscissa_cell_value='created', abscissa_type=RGT_YEAR,
            ordinate_type=RGA_COUNT,
        )

        fetcher1 = RelationLinkedGraphFetcher(graph=graph, value=FAKE_REL_SUB_EMPLOYED_BY)
        self.assertIsNone(fetcher1.error)
        self.assertEqual(
            _('{rtype} (Relationship)').format(
                rtype='is an employee of — employs',
            ),
            fetcher1.verbose_name
        )

        ibci = fetcher1.create_brick_config_item()
        self.assertEqual(RGF_RELATION, ibci.get_extra_data('type'))
        self.assertEqual(FAKE_REL_SUB_EMPLOYED_BY, ibci.get_extra_data('value'))

        fetcher2 = RelationLinkedGraphFetcher(graph=graph)
        self.assertEqual(
            _('No relationship type given.'),
            fetcher2.error
        )
        self.assertEqual('??', fetcher2.verbose_name)

        fetcher3 = RelationLinkedGraphFetcher(graph=graph, value='invalid')
        self.assertEqual(
            _('The relationship type is invalid.'),
            fetcher3.error
        )

        fetcher4 = RelationLinkedGraphFetcher(graph=graph, value=FAKE_REL_SUB_BILL_ISSUED)
        self.assertEqual(
            _('The relationship type is not compatible with «{}».').format(
                'Test Contact',
            ),
            fetcher4.error
        )

        choices = [*RelationLinkedGraphFetcher.choices(FakeContact)]
        self.assertInChoices(
            value=f'{FAKE_REL_SUB_EMPLOYED_BY}',
            label='is an employee of — employs',
            choices=choices,
        )
        self.assertNotInChoices(
            value=f'{FAKE_REL_SUB_BILL_ISSUED}',
            choices=choices,
        )

        # ----
        # TODO: move to test for bricks ?
        brick = ReportGraphBrick(ibci)
        self.assertIsNone(brick.errors)
        self.assertListEqual([FakeOrganisation], brick.target_ctypes)

    def test_create_brick_config_item(self):
        "Other brick class."
        class OtherReportGraphBrick(ReportGraphBrick):
            id_ = ReportGraphBrick.generate_id('reports', 'other_graph')

        user = self.create_user()
        report = Report.objects.create(user=user, name='Field Test', ct=FakeContact)
        graph = ReportGraph.objects.create(
            user=user, name='Field Test', linked_report=report,
            abscissa_cell_value='created', abscissa_type=RGT_YEAR,
            ordinate_type=RGA_COUNT,
        )

        ibci = SimpleGraphFetcher(graph=graph).create_brick_config_item(
            brick_class=OtherReportGraphBrick,
        )
        self.assertEqual(OtherReportGraphBrick.id_, ibci.brick_class_id)


class GraphFetcherRegistryTestCase(CremeTestCase):
    def test_default_class(self):
        registry = GraphFetcherRegistry(SimpleGraphFetcher)
        self.assertEqual(SimpleGraphFetcher, registry.default_class)

        class OtherSimpleGraphFetcher(GraphFetcher):
            pass

        registry.default_class = OtherSimpleGraphFetcher
        self.assertEqual(OtherSimpleGraphFetcher, registry.default_class)

    def test_register01(self):
        user = self.create_user()
        report = Report.objects.create(user=user, name='Field Test', ct=FakeContact)
        graph = ReportGraph(user=user, name='Field Test', linked_report=report)

        registry = GraphFetcherRegistry(SimpleGraphFetcher)
        self.assertFalse([*registry.fetcher_classes])
        fetcher_dict = {
            'type': RGF_FK,
            'value': 'image',
        }

        with self.assertLogs(level='WARNING') as logs_manager1:
            fetcher1 = registry.get(graph=graph, fetcher_dict=fetcher_dict)

        self.assertIsInstance(fetcher1, SimpleGraphFetcher)
        self.assertEqual(
            _('Invalid volatile link ; please contact your administrator.'),
            fetcher1.error
        )
        self.assertIn(
            'invalid ID "reports-fk" for fetcher (basic fetcher is used)',
            logs_manager1.output[0]
        )

        # -----
        registry.register(
            RegularFieldLinkedGraphFetcher,
            RelationLinkedGraphFetcher,
        )
        self.assertCountEqual(
            [
                RegularFieldLinkedGraphFetcher,
                RelationLinkedGraphFetcher,
            ],
            [*registry.fetcher_classes]
        )
        fetcher2 = registry.get(graph=graph, fetcher_dict=fetcher_dict)
        self.assertIsInstance(fetcher2, RegularFieldLinkedGraphFetcher)
        self.assertIsNone(fetcher2.error)

        # Invalid dict (no type) --
        with self.assertLogs(level='WARNING') as logs_manager2:
            fetcher3 = registry.get(graph=graph, fetcher_dict={'value': 'image'})

        self.assertIsInstance(fetcher3, SimpleGraphFetcher)
        self.assertEqual(
            _('Invalid volatile link ; please contact your administrator.'),
            fetcher3.error
        )
        self.assertIn(
            'no fetcher ID given (basic fetcher is used)',
            logs_manager2.output[0]
        )

    def test_register02(self):
        "Duplicates."
        registry = GraphFetcherRegistry(SimpleGraphFetcher).register(
            RegularFieldLinkedGraphFetcher,
            RelationLinkedGraphFetcher,
        )

        class OtherFKGraphFetcher(RegularFieldLinkedGraphFetcher):
            pass

        with self.assertRaises(GraphFetcherRegistry.RegistrationError):
            registry.register(OtherFKGraphFetcher)