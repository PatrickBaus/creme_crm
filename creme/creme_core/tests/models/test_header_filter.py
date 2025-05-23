from functools import partial

from django.contrib.contenttypes.models import ContentType
from django.utils.translation import gettext as _

from creme.creme_core.constants import REL_SUB_HAS
from creme.creme_core.core.entity_cell import (
    EntityCellCustomField,
    EntityCellFunctionField,
    EntityCellRegularField,
    EntityCellRelation,
)
from creme.creme_core.models import (
    CustomField,
    FakeCivility,
    FakeContact,
    FakeOrganisation,
    FakePosition,
    FieldsConfig,
    HeaderFilter,
    RelationType,
    SettingValue,
)
from creme.creme_core.models.header_filter import HeaderFilterList
from creme.creme_core.setting_keys import global_filters_edition_key

from ..base import CremeTestCase


class HeaderFiltersTestCase(CremeTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        get_ct = ContentType.objects.get_for_model
        cls.contact_ct = get_ct(FakeContact)  # TODO: used once ?!
        cls.orga_ct    = get_ct(FakeOrganisation)

    def test_manager_create_if_needed01(self):
        name = 'Contact view'
        pk   = 'tests-hf_contact'
        hf = HeaderFilter.objects.create_if_needed(
            pk=pk, name=name, model=FakeContact, is_custom=True,
        )
        self.assertEqual(pk,   hf.pk)
        self.assertEqual(name, hf.name)
        self.assertIsNone(hf.user)
        self.assertEqual(self.contact_ct, hf.entity_type)
        self.assertIs(hf.is_custom, True)
        self.assertIs(hf.is_private, False)
        self.assertDictEqual({}, hf.extra_data)
        self.assertListEqual([], hf.json_cells)
        self.assertFalse(hf.cells)
        self.assertListEqual([], hf.filtered_cells)

        hf.cells = [EntityCellRegularField.build(model=FakeContact, name='first_name')]
        hf.save()

        hf = self.refresh(hf)
        self.assertEqual(1, len(hf.cells))

        with self.assertNoException():
            deserialized = hf.json_cells

        self.assertListEqual(
            [{'type': 'regular_field', 'value': 'first_name'}],
            deserialized,
        )

        self.assertListEqual(
            [EntityCellRegularField.build(model=FakeContact, name='first_name')],
            hf.filtered_cells,
        )

    def test_manager_create_if_needed02(self):
        "With cells & extra_data."
        user = self.get_root_user()

        create_rtype = RelationType.objects.smart_update_or_create
        loves = create_rtype(
            ('test-subject_love', 'Is loving'),
            ('test-object_love',  'Is loved by'),
        )[0]
        likes = create_rtype(
            ('test-subject_like', 'Is liking'),
            ('test-object_like',  'Is liked by'),
        )[0]

        extra_data = {'my_key': 'my_value'}
        hf = HeaderFilter.objects.create_if_needed(
            pk='tests-hf_contact', name='Contact view',
            model=FakeContact, is_custom=True, is_private=True,
            user=user,
            cells_desc=[
                (EntityCellRegularField, {'name': 'last_name'}),
                EntityCellRelation(model=FakeContact, rtype=loves),
                # (EntityCellRelation, {'rtype_id': likes.id}),
                (EntityCellRelation, {'name': likes.id}),
                None,
            ],
            extra_data=extra_data,
        )

        hf = self.refresh(hf)
        self.assertEqual(user, hf.user)
        self.assertTrue(hf.is_private)
        self.assertListEqual(
            [
                EntityCellRegularField.build(model=FakeContact, name='last_name'),
                EntityCellRelation(model=FakeContact, rtype=loves),
                EntityCellRelation(model=FakeContact, rtype=likes),
            ],
            hf.cells,
        )
        self.assertDictEqual(extra_data, hf.extra_data)

    def test_manager_create_if_needed03(self):
        "Do not modify if it already exists."
        pk = 'tests-hf_contact'
        name = 'Contact view'
        HeaderFilter.objects.create_if_needed(
            pk=pk, name=name,
            model=FakeContact, is_custom=False,
            cells_desc=[(EntityCellRegularField, {'name': 'last_name'})],
        )

        hf = HeaderFilter.objects.create_if_needed(
            pk=pk, name='Contact view edited', user=self.get_root_user(),
            model=FakeContact, is_custom=False,
            cells_desc=[
                (EntityCellRegularField, {'name': 'first_name'}),
                (EntityCellRegularField, {'name': 'last_name'}),
            ],
        )
        self.assertEqual(name, hf.name)
        self.assertIsNone(hf.user)
        self.assertListEqual(
            [EntityCellRegularField.build(model=FakeContact, name='last_name')],
            hf.cells,
        )

    def test_manager_create_if_needed04(self):
        "Errors."
        user = self.get_root_user()

        # Private + no user => error
        with self.assertRaises(ValueError):
            HeaderFilter.objects.create_if_needed(
                pk='tests-hf_contact', name='Contact view edited',
                model=FakeContact, is_private=True,
                cells_desc=[(EntityCellRegularField, {'name': 'last_name'})],
            )

        # Private + not is_custom => error
        with self.assertRaises(ValueError):
            HeaderFilter.objects.create_if_needed(
                pk='tests-hf_contact', name='Contact view edited',
                user=user, model=FakeContact,
                is_private=True, is_custom=False,
                cells_desc=[(EntityCellRegularField, {'name': 'last_name'})],
            )

    def test_can_edit__root(self):
        sv_open = SettingValue.objects.get_4_key(global_filters_edition_key)
        self.assertFalse(sv_open.value)

        root = self.get_root_user()
        other = self.create_user()
        team1 = self.create_team('team A', other, root)
        team2 = self.create_team('team B', other)
        OK = (True, 'OK')
        self.assertTupleEqual(
            OK, HeaderFilter(entity_type=FakeContact).can_edit(root),
        )
        self.assertTupleEqual(
            OK, HeaderFilter(entity_type=FakeContact, user=other).can_edit(root),
        )
        KO = (False, _('You are not allowed to edit/delete this view'))
        self.assertTupleEqual(
            KO, HeaderFilter(entity_type=FakeContact, user=other, is_private=True).can_edit(root),
        )
        self.assertTupleEqual(
            OK, HeaderFilter(entity_type=FakeContact, user=root, is_private=True).can_edit(root),
        )
        self.assertTupleEqual(
            KO, HeaderFilter(entity_type=FakeContact, user=team2, is_private=True).can_edit(root),
        )
        self.assertTupleEqual(
            OK, HeaderFilter(entity_type=FakeContact, user=team1, is_private=True).can_edit(root),
        )

    def test_can_edit__staff(self):
        staff = self.create_user(index=1, is_staff=True)
        self.assertTrue(
            HeaderFilter(
                entity_type=FakeContact, user=self.get_root_user(), is_private=True,
            ).can_edit(staff)[0],
        )

    def test_can_edit__regular_user(self):
        from creme.documents import get_document_model

        setting_value = SettingValue.objects.get_4_key(global_filters_edition_key)
        self.assertFalse(setting_value.value)

        user = self.create_user(index=1, role=self.create_role(allowed_apps=['creme_core']))
        # self.assertTrue(HeaderFilter(entity_type=FakeContact).can_edit(user)[0])
        self.assertTupleEqual(
            (True, 'OK'),
            HeaderFilter(user=user, entity_type=FakeContact).can_edit(user),
        )
        self.assertTupleEqual(
            (False, _('Only superusers can edit/delete this view (no owner)')),
            HeaderFilter(entity_type=FakeContact).can_edit(user),
        )
        self.assertTupleEqual(
            (False, _('You are not allowed to access to this app')),
            HeaderFilter(entity_type=get_document_model()).can_edit(user),
        )

    def test_can_edit__regular_user__setting_value_true(self):
        setting_value = SettingValue.objects.get_4_key(global_filters_edition_key)
        setting_value.value = True
        setting_value.save()

        user = self.create_user(index=1, role=self.get_regular_role())
        self.assertTupleEqual(
            (True, 'OK'),
            HeaderFilter(user=user, entity_type=FakeContact).can_edit(user),
        )
        self.assertTupleEqual(
            (True, 'OK'),
            HeaderFilter(entity_type=FakeContact).can_edit(user),
        )

    def test_ct_cache(self):
        hf = HeaderFilter.objects.create_if_needed(
            pk='tests-hf_contact', name='Contact view',
            model=FakeContact, is_custom=True,
        )

        with self.assertNumQueries(0):
            ContentType.objects.get_for_id(hf.entity_type_id)

        hf = self.refresh(hf)

        with self.assertNumQueries(0):
            hf.entity_type  # NOQA

    def test_cells_property01(self):
        model = FakeContact
        fname1 = 'last_name'
        cfield = CustomField.objects.create(
            name='Size (cm)',
            field_type=CustomField.INT,
            content_type=model,
        )

        build_rcell = partial(EntityCellRegularField.build, model=model)
        cells = [
            build_rcell(name=fname1),
            EntityCellCustomField(customfield=cfield),
        ]
        hf = HeaderFilter.objects.create_if_needed(
            pk='test-hf01', name='Contact view', model=FakeContact,
            cells_desc=cells,
        )
        self.assertListEqual(
            [
                {'type': 'regular_field', 'value': fname1},
                # {'type': 'custom_field', 'value': str(cfield.id)},
                {'type': 'custom_field', 'value': str(cfield.uuid)},
            ],
            hf.json_cells,
        )

        # ---
        fname2 = 'description'
        cells.append(build_rcell(name=fname2))
        hf.cells = cells
        hf.save()

        hf = self.refresh(hf)
        self.assertEqual(
            [
                {'type': 'regular_field', 'value': fname1},
                # {'type': 'custom_field', 'value': str(cfield.id)},
                {'type': 'custom_field', 'value': str(cfield.uuid)},
                {'type': 'regular_field', 'value': fname2},
            ],
            hf.json_cells,
        )
        self.assertListEqual(
            [
                build_rcell(name=fname1),
                EntityCellCustomField(customfield=cfield),
                build_rcell(name=fname2),
            ],
            hf.cells,
        )

    def test_cells_property02(self):
        "None value are ignored."
        hf = HeaderFilter.objects.create_if_needed(
            pk='test-hf01', name='Contact view', model=FakeContact,
        )

        build_cell = partial(EntityCellRegularField.build, model=FakeContact)
        cell01 = build_cell(name='first_name')
        cell02 = build_cell(name='invalid_field')
        cell03 = build_cell(name='last_name')
        self.assertIsNone(cell02)

        hf.cells = [cell01, cell02, cell03]
        hf.save()

        self.assertListEqual(
            [cell01, cell03],
            self.refresh(hf).cells,
        )

    def test_cells_property_errors01(self):
        ffield_name = 'get_pretty_properties'
        rfield_name = 'last_name'
        hf = HeaderFilter.objects.create_if_needed(
            pk='test-hf', name='Contact view', model=FakeContact,
            cells_desc=[
                # (EntityCellFunctionField, {'func_field_name': ffield_name}),
                (EntityCellFunctionField, {'name': ffield_name}),
                (EntityCellRegularField,  {'name': rfield_name}),
            ],
        )

        with self.assertNoException():
            deserialized1 = hf.json_cells

        self.assertListEqual(
            [
                {'type': 'function_field', 'value': ffield_name},
                {'type': 'regular_field',  'value': rfield_name},
            ],
            deserialized1,
        )

        # We use update() in order to bypass the checking by HeaderFilter
        # methods and inject errors : it simulates a human that modifies
        # directly the DB column.
        HeaderFilter.objects.filter(id=hf.id).update(
            json_cells=[
                {
                    'type': 'invalid_type',  # <===
                    'value': ffield_name,
                },
                {'type': 'regular_field', 'value': rfield_name},
            ],
        )

        hf = self.refresh(hf)
        valid_cells = [EntityCellRegularField.build(model=FakeContact, name=rfield_name)]
        self.assertListEqual(valid_cells, hf.cells)

        with self.assertNoException():
            deserialized2 = hf.json_cells

        self.assertListEqual(
            [{'type': 'regular_field',  'value': rfield_name}],
            deserialized2,
        )

        # ---------------------------------------------------------------------
        HeaderFilter.objects.filter(
            id=hf.id,
        ).update(
            json_cells=[
                {'type': 'function_field'},
                {'type': 'regular_field', 'value': rfield_name},
            ],
        )
        self.assertListEqual(valid_cells, self.refresh(hf).cells)

        # ---------------------------------------------------------------------
        HeaderFilter.objects.filter(
            id=hf.id,
        ).update(
            json_cells=[
                {'type': 'function_field'},  # Not 'value' key
                {'type': 'regular_field', 'value': rfield_name},
            ],
        )
        self.assertListEqual(valid_cells, self.refresh(hf).cells)

        # ---------------------------------------------------------------------
        HeaderFilter.objects.filter(
            id=hf.id,
        ).update(
            json_cells=[
                {},  # No 'type' key
                {'type': 'regular_field', 'value': rfield_name},
            ],
        )
        self.assertListEqual(valid_cells, self.refresh(hf).cells)

        # ---------------------------------------------------------------------
        HeaderFilter.objects.filter(id=hf.id).update(json_cells=[1])  # Not a dict
        self.assertFalse(self.refresh(hf).cells)

        # ---------------------------------------------------------------------
        HeaderFilter.objects.filter(id=hf.id).update(json_cells=1)  # Not a list
        self.assertFalse(self.refresh(hf).cells)

    def test_filtered_cells(self):
        hidden = 'first_name'
        FieldsConfig.objects.create(
            content_type=FakeContact,
            descriptions=[
                (hidden,  {FieldsConfig.HIDDEN: True}),
            ],
        )

        rtype = self.get_object_or_fail(RelationType, id=REL_SUB_HAS)

        hf = HeaderFilter.objects.create_if_needed(
            pk='tests-hf_contact', name='Contact view',
            model=FakeContact,
            cells_desc=[
                (EntityCellRegularField, {'name': 'last_name'}),
                (EntityCellRegularField, {'name': hidden}),
                EntityCellRelation(model=FakeContact, rtype=rtype),
            ],
        )
        self.assertListEqual(
            [
                EntityCellRegularField.build(FakeContact, 'last_name'),
                EntityCellRelation(model=FakeContact, rtype=rtype),
            ],
            hf.filtered_cells,
        )

    def test_populate_entities_fields01(self):
        "Regular fields: no FK."
        user = self.get_root_user()
        hf = HeaderFilter.objects.create_if_needed(
            pk='test-hf', name='Contact view', model=FakeContact,
            cells_desc=[
                (EntityCellRegularField, {'name': 'last_name'}),
                (EntityCellRegularField, {'name': 'first_name'}),
            ],
        )

        pos = FakePosition.objects.create(title='Pilot')
        create_contact = partial(FakeContact.objects.create, user=user, position_id=pos.id)
        contacts = [
            create_contact(first_name='Nagate',  last_name='Tanikaze'),
            create_contact(first_name='Shizuka', last_name='Hoshijiro'),
        ]

        with self.assertNumQueries(0):
            hf.populate_entities(contacts, user)

        with self.assertNumQueries(1):
            contacts[0].position  # NOQA

    def test_populate_entities_fields02(self):
        "Regular fields: FK."
        user = self.get_root_user()
        build = partial(EntityCellRegularField.build, model=FakeContact)
        hf = HeaderFilter.objects.create_if_needed(
            pk='test-hf', name='Contact view', model=FakeContact,
            cells_desc=[
                build(name='last_name'), build(name='first_name'),
                build(name='position'),
                build(name='civility__title'),
            ],
        )

        pos = FakePosition.objects.all()[0]
        civ = FakeCivility.objects.all()[0]
        create_contact = partial(
            FakeContact.objects.create, user=user, position=pos, civility=civ,
        )
        contact1 = create_contact(first_name='Nagate', last_name='Tanikaze')
        contact2 = create_contact(first_name='Shizuka', last_name='Hoshijiro')
        # NB: we refresh because the __str__() method retrieves the civility
        contacts = [self.refresh(contact1), self.refresh(contact2)]

        with self.assertNumQueries(2):
            hf.populate_entities(contacts, user)

        with self.assertNumQueries(0):
            contacts[0].position
            contacts[1].position
            contacts[0].civility
            contacts[1].civility

    def test_populate_entities_fields03(self):
        "Regular fields: invalid fields are removed automatically."
        user = self.get_root_user()

        cell1 = EntityCellRegularField.build(model=FakeContact, name='last_name')

        cell2 = EntityCellRegularField.build(model=FakeContact, name='first_name')
        cell2.value = 'invalid'

        hf = HeaderFilter.objects.create_if_needed(
            pk='test-hf', name='Contact view',
            model=FakeContact, cells_desc=[cell1, cell2],
        )

        create_contact = partial(FakeContact.objects.create, user=user)
        contacts = [
            create_contact(first_name='Nagate',  last_name='Tanikaze'),
            create_contact(first_name='Shizuka', last_name='Hoshijiro'),
        ]

        hf = self.refresh(hf)
        new_cells = hf.cells
        self.assertListEqual([cell1], new_cells)

        with self.assertNoException():
            deserialized = hf.json_cells

        self.assertListEqual(
            [{'type': 'regular_field', 'value': 'last_name'}],
            deserialized,
        )

        with self.assertNoException():
            with self.assertNumQueries(0):
                hf.populate_entities(contacts, user)

    def test_manager_filter_by_user(self):
        user = self.login_as_standard()
        other_user = self.get_root_user()

        teammate = self.create_user(index=1, role=user.role)

        tt_team = self.create_team('TeamTitan', user, teammate)
        a_team = self.create_team('A-Team', other_user)

        cells = [EntityCellRegularField.build(model=FakeOrganisation, name='name')]

        def create_hf(id, **kwargs):
            return HeaderFilter.objects.create_if_needed(
                pk=f'test-hf_orga{id}',
                name=f'Orga view #{id}',
                model=FakeOrganisation, cells_desc=cells,
                **kwargs
            )

        hfilters = [
            create_hf(1),
            create_hf(2,  user=user),
            create_hf(3,  user=other_user),
            create_hf(4,  user=tt_team),
            create_hf(5,  user=a_team),
            create_hf(6,  user=user,       is_private=True, is_custom=True),
            create_hf(7,  user=tt_team,    is_private=True, is_custom=True),
            create_hf(8,  user=other_user, is_private=True, is_custom=True),
            create_hf(9,  user=a_team,     is_private=True, is_custom=True),
            create_hf(10, user=teammate,   is_private=True, is_custom=True),
        ]

        filtered1 = [*HeaderFilter.objects.filter_by_user(user)]
        self.assertIn(hfilters[0], filtered1)
        self.assertIn(hfilters[1], filtered1)
        self.assertIn(hfilters[2], filtered1)
        self.assertIn(hfilters[3], filtered1)
        self.assertIn(hfilters[4], filtered1)
        self.assertIn(hfilters[5], filtered1)
        self.assertIn(hfilters[6], filtered1)
        self.assertNotIn(hfilters[7], filtered1)
        self.assertNotIn(hfilters[8], filtered1)
        self.assertNotIn(hfilters[9], filtered1)

        # ---
        with self.assertRaises(ValueError):
            HeaderFilter.objects.filter_by_user(tt_team)

        # ---
        staff = self.create_user(index=2, is_staff=True)
        filtered2 = [*HeaderFilter.objects.filter_by_user(staff)]
        for hf in hfilters:
            self.assertIn(hf, filtered2)

    def test_filterlist01(self):
        user = self.get_root_user()
        create_hf = partial(
            HeaderFilter.objects.create_if_needed,
            name='Orga view',
            model=FakeOrganisation,
            cells_desc=[
                EntityCellRegularField.build(model=FakeOrganisation, name='name'),
            ],
        )
        hf1 = create_hf(pk='test-hf_orga1')
        hf2 = create_hf(pk='test-hf_orga2', user=user)
        hf3 = create_hf(pk='test-hf_contact', model=FakeContact, name='Contact view')
        hf4 = create_hf(pk='test-hf_orga3', user=self.create_user())

        ct = self.orga_ct
        hfl = HeaderFilterList(ct, user)
        self.assertIn(hf1, hfl)
        self.assertIn(hf2, hfl)
        self.assertIn(hf4, hfl)
        self.assertEqual(hf1, hfl.select_by_id(hf1.id))
        self.assertEqual(hf2, hfl.select_by_id(hf2.id))
        self.assertEqual(hf2, hfl.select_by_id('unknown_id', hf2.id))

        self.assertEqual(hf1.can_view(user), (True, 'OK'))
        # self.assertEqual(hf1.can_view(user, ct), (True, 'OK'))

        # self.assertEqual(hf3.can_view(user, ct), (False, 'Invalid entity type'))
        self.assertNotIn(hf3, hfl)

    def test_filterlist02(self):
        "Private filters + not superuser (+ team management)."
        user = self.login_as_standard()
        other_user = self.get_root_user()
        teammate = self.create_user(index=1, role=user.role)
        tt_team = self.create_team('TeamTitan', user, teammate)
        a_team = self.create_team('A-Team', other_user)

        cells = [EntityCellRegularField.build(model=FakeOrganisation, name='name')]

        def create_hf(id, **kwargs):
            return HeaderFilter.objects.create_if_needed(
                pk=f'test-hf_orga{id}',
                name=f'Orga view #{id}',
                model=FakeOrganisation, cells_desc=cells,
                **kwargs
            )

        hf01 = create_hf(1)
        hf02 = create_hf(2,  user=user)
        hf03 = create_hf(3,  user=other_user)
        hf04 = create_hf(4,  user=tt_team)
        hf05 = create_hf(5,  user=a_team)
        hf06 = create_hf(6,  user=user,       is_private=True, is_custom=True)
        hf07 = create_hf(7,  user=tt_team,    is_private=True, is_custom=True)
        hf08 = create_hf(8,  user=other_user, is_private=True, is_custom=True)
        hf09 = create_hf(9,  user=a_team,     is_private=True, is_custom=True)
        hf10 = create_hf(10, user=teammate,   is_private=True, is_custom=True)

        hfl = HeaderFilterList(self.orga_ct, user)
        self.assertIn(hf01, hfl)
        self.assertIn(hf02, hfl)
        self.assertIn(hf03, hfl)
        self.assertIn(hf04, hfl)
        self.assertIn(hf05, hfl)
        self.assertIn(hf06, hfl)
        self.assertIn(hf07, hfl)
        self.assertNotIn(hf08, hfl)
        self.assertNotIn(hf09, hfl)
        self.assertNotIn(hf10, hfl)

    def test_filterlist03(self):
        "Staff user -> can see all filters."
        user = self.login_as_super(is_staff=True)
        other_user = self.get_root_user()

        cells = [EntityCellRegularField.build(model=FakeOrganisation, name='name')]

        def create_hf(hf_id, **kwargs):
            return HeaderFilter.objects.create_if_needed(
                pk=f'test-hf_orga{hf_id}',
                name=f'Orga view #{hf_id}',
                model=FakeOrganisation, cells_desc=cells,
                **kwargs
            )

        hf1 = create_hf(1)

        with self.assertRaises(ValueError):
            create_hf(2,  user=user)

        hf3 = create_hf(3,  user=other_user)

        # This one cannot be seen by not staff users
        hf4 = create_hf(4,  user=other_user, is_private=True, is_custom=True)

        hfl = HeaderFilterList(self.orga_ct, user)
        self.assertIn(hf1, hfl)
        self.assertIn(hf3, hfl)
        self.assertIn(hf4, hfl)
