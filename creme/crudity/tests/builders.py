# -*- coding: utf-8 -*-

import re
import os
from xml.etree.ElementTree import XML, tostring, Element
from tempfile import gettempdir

from django.contrib.auth.models import User
from django.db.models.fields import FieldDoesNotExist
from django.utils import translation
from django.utils.translation import ugettext_lazy as _, ugettext

from creme_core.models.entity import CremeEntity
from crudity.backends.registry import from_email_crud_registry
from crudity.builders.infopath import InfopathFormBuilder, InfopathFormField
from crudity.tests.backends import CrudityTestCase
from persons.models.contact import Contact


class InfopathFormBuilderTestCase(CrudityTestCase):
    def setUp(self):
        super(InfopathFormBuilderTestCase, self).setUp()
        self.response = self.client.get('/')#Url doesn't matter
        self.request  = self.response.context['request']

    def _get_builder(self, backend):
        builder = InfopathFormBuilder(request=self.request, backend=backend)
        return builder

    def test_builder_01(self):
        backend = self._get_create_from_email_backend(model=None)
        self.assertRaises(AssertionError, self._get_builder, backend)

    def test_builder_02(self):
        backend = self._get_create_from_email_backend(subject="create_ce")
        builder = self._get_builder(backend)

        now = builder.now
        now_str = now.strftime('%Y-%m-%dT%H:%M:%S')

        expected_urn = "urn:schemas-microsoft-com:office:infopath:%s:-myXSD-%s" % ("create-create_ce", now_str)

        self.assertEqual("http://schemas.microsoft.com/office/infopath/2003/myXSD/%s" % now_str, builder.namespace)
        self.assertEqual(expected_urn, builder.urn)

    def test_builder_get_lang(self):
        backend = self._get_create_from_email_backend(subject="create_ce")
        builder = self._get_builder(backend)

        translation.activate("fr")
        response = self.client.get('/')
        request  = response.context['request']
        self.assertEqual("1036", builder._get_lang_code(request.LANGUAGE_CODE))

    def test_builder_fields_property(self):
        backend = self._get_create_from_email_backend(subject="create_contact",
                                                      model=Contact,
                                                      body_map={'user_id': 1, 'is_actived': True, "first_name":"",
                                                                "last_name":"", "email": "none@none.com",
                                                                "description": "", "birthday":"",
                                                                "password": "creme"})
        builder = self._get_builder(backend)

        for field in builder.fields:
            self.assert_(field.name in backend.body_map.keys())
            self.assertEqual(Contact, field.model)

        for field in builder.fields:#Two passes because of cache
            self.assert_(field.name in backend.body_map.keys())
            self.assertEqual(Contact, field.model)

    def test_manifest_xsf_01(self):#Test some base values
        backend = self._get_create_from_email_backend(subject="create_ce")
        builder = self._get_builder(backend)
        xsf_ns  = "{http://schemas.microsoft.com/office/infopath/2003/solutionDefinition}"
        d_ns    = {'ns': xsf_ns, 'ns2': "{http://schemas.microsoft.com/office/infopath/2006/solutionDefinition/extensions}"}

        content = builder._render_manifest_xsf(self.request)
        xml = XML(content)
        xml_find = xml.find

        self.assertEqual(re.search('xmlns:my="(?P<ns>[\w\d\-:/\.]*)"', content).groupdict()['ns'], builder.get_namespace())#Can't be got with ElementTree, because it's a namespace

        self.assertEqual(builder.get_urn(), xml.get('name'))
        self.assertEqual(builder.get_namespace(), xml_find('%(ns)spackage/%(ns)sfiles/%(ns)sfile/%(ns)sfileProperties/%(ns)sproperty' % d_ns).get('value'))
        self.assertEqual(builder.get_namespace(), xml_find('%(ns)sapplicationParameters/%(ns)ssolutionProperties' % d_ns).get('fullyEditableNamespace'))
        self.assertEqual(builder.get_namespace(), xml_find('%(ns)sdocumentSchemas/%(ns)sdocumentSchema' % d_ns).get('location').split()[0])

        file_nodes = xml.findall('%(ns)spackage/%(ns)sfiles/%(ns)sfile/' % d_ns)#ElementTree 1.2.6 (shipped with python <= 2.6) doesn't support advanced xpath expressions
        found_node = None
        for node in file_nodes:
            if node.get('name') == "view1.xsl":
                found_node = node
                break
        self.assert_(found_node, '<xsf:file name="view1.xsl"> not found')

        property_node = None
        for node in found_node.findall('%(ns)sfileProperties/%(ns)sproperty' % d_ns):
            if node.get('name') == "lang":
                property_node = node
                self.assertEqual(builder._get_lang_code(self.request.LANGUAGE_CODE), node.get('value'))
                break
        self.assert_(property_node is not None, '<xsf:property name="lang" type="string" value=""></xsf:property> not found')

        mail_form_name = backend.subject
        self.assertEqual(mail_form_name, xml_find('%(ns)sextensions/%(ns)sextension/%(ns2)ssolutionDefinition/%(ns2)ssolutionPropertiesExtension/%(ns2)smail' % d_ns).get('formName'))

#TODO: Remove me
#    def test_manifest_xsf_02(self):#Test fields values
#        body_map={'user_id': 1, 'is_actived': True, "first_name":"",
#                  "last_name":"", "email": "none@none.com",
#                  "description": "", "birthday":"",}
#        backend = self._get_create_from_email_backend(subject="create_contact",
#                                                      body_map=body_map,
#                                                      model=Contact)
#        builder = self._get_builder(backend)
#        d_ns    = {'ns': "{http://schemas.microsoft.com/office/infopath/2003/solutionDefinition}", 'ns2': "{http://schemas.microsoft.com/office/infopath/2006/solutionDefinition/extensions}"}
#
#        xml     = XML(builder._render_manifest_xsf(self.request))
#
#        extensions_cn = set(node.get('columnName') for node in xml.findall('%(ns)sextensions/%(ns)sextension/%(ns2)ssolutionDefinition/%(ns2)slistPropertiesExtension/%(ns2)sfieldsExtension/%(ns2)sfieldExtension' % d_ns))
#        fields_cn = set(node.get('columnName') for node in xml.findall('%(ns)slistProperties/%(ns)sfields/%(ns)sfield' % d_ns))
#
#        self.assertEqual(extensions_cn, fields_cn)
#
#        field_nodes = xml.findall('%(ns)slistProperties/%(ns)sfields/%(ns)sfield' % d_ns)
#
#        #BEGIN TODO
##        model_get_field = Contact._meta.get_field
##        model_get_field_vb = lambda field_name: model_get_field(field_name).verbose_name
##        verbose_names = set(model_get_field_vb(name) for name in ['user','is_actived', "first_name", "last_name", "email", "description", "birthday"])
##        field_nodes_vb = set(field.get('name') for field in field_nodes)
#        #TODO: Uncomment lines above, and remove those ones below, when the unicode decode error will be fixed in the template
#        verbose_names = set(['user_id','is_actived', "first_name", "last_name", "email", "description", "birthday"])
#        field_nodes_vb = set(field.get('name').lower() for field in field_nodes)
#        self.assertEqual(verbose_names, field_nodes_vb)
#        #END TODO
#
#        paths = set('/my:CremeCRMCrudity/my:%s' % name for name in body_map.iterkeys())
#        node_attrs = set(field.get('node') for field in field_nodes)
#        self.assertEqual(paths, node_attrs)

    def test_myschema_xsd01(self):
        body_map={'user_id': 1, 'is_actived': True, "first_name":"",
                  "last_name":"", "email": "none@none.com",
                  "description": "", "birthday":"", "created":"", 'url_site': ""}
        backend = self._get_create_from_email_backend(subject="create_contact",
                                                      body_map=body_map,
                                                      model=Contact)
        builder = self._get_builder(backend)
        d_ns    = {'xsd': "{http://www.w3.org/2001/XMLSchema}"}

        content = builder._render_myschema_xsd(self.request)
        xml     = XML(content)

        self.assertEqual(builder.namespace, xml.get('targetNamespace'))
        self.assertEqual(builder.namespace, re.search('xmlns:my="(?P<ns>[\w\d\-:/\.]*)"', content).groupdict()['ns'])#Can't be got with ElementTree, because it's a namespace

        ref_attrs = set(node.get('ref') for node in xml.findall('%(xsd)selement/%(xsd)scomplexType/%(xsd)ssequence/%(xsd)selement' % d_ns))
        expected_ref_attrs = set('my:%s' % key for key in body_map.iterkeys())
        self.assertEqual(expected_ref_attrs, ref_attrs)

        xsd_elements = {
                        'CremeCRMCrudity': {'name': 'CremeCRMCrudity'},
                        'user_id':     {'name': 'user_id', 'type': 'xsd:integer'},#"""<xsd:element name="user_id" type="xsd:integer"/>""",
                        'is_actived':  {'name': 'is_actived', 'type': 'xsd:boolean'},#"""<xsd:element name="is_actived" type="xsd:boolean"/>""",
                        "first_name":  {'name': 'first_name', 'type': 'my:requiredString'},#"""<xsd:element name="first_name" type="xsd:requiredString"/>""",
                        "last_name":   {'name': 'last_name', 'type': 'my:requiredString'},#"""<xsd:element name="last_name" type="xsd:requiredString"/>""",
                        "email":       {'name': 'email', 'type': 'xsd:string'},#"""<xsd:element name="email" type="xsd:string"/>""",
                        "description": {'name': 'description'},#"""<xsd:element name="description"><xsd:complexType mixed="true"><xsd:sequence><xsd:any minOccurs="0" maxOccurs="unbounded" namespace="http://www.w3.org/1999/xhtml" processContents="lax"/></xsd:sequence></xsd:complexType></xsd:element>""",
                        "birthday":    {'name': 'birthday', 'type': 'xsd:date', 'nillable': 'true'},#"""<xsd:element name="birthday" nillable="true" type="xsd:date"/>""",
                        "created":     {'name': 'created', 'type': 'xsd:dateTime'},#"""<xsd:element name="created" type="xsd:dateTime"/>""",
                        "url_site":    {'name': 'url_site', 'type': 'xsd:anyURI'},
                        }
        element_nodes = xml.findall('%(xsd)selement' % d_ns)
        for element_node in element_nodes:
            xsd_element_attrs = xsd_elements.get(element_node.get('name'))
            if xsd_element_attrs is not None:
                self.assertEqual(set(xsd_element_attrs.keys()), set(element_node.keys()))
                for attr in element_node.keys():
                    self.assertEqual(xsd_element_attrs[attr], element_node.get(attr))
            else:
                self.fail("There is at least an extra node named: %s" % element_node.get('name'))

    def test_template_xml01(self):
        body_map={'user_id': 1, 'is_actived': True, "first_name":"",
                  "last_name":"", "email": "none@none.com",
                  "description": "", "birthday":"", "created":"", 'url_site': ""}
        backend = self._get_create_from_email_backend(subject="create_contact",
                                                      body_map=body_map,
                                                      model=Contact)
        builder = self._get_builder(backend)

        content = builder._render_template_xml(self.request)
        self.assertEqual(re.search('xmlns:my="(?P<ns>[\w\d\-:/\.]*)"', content).groupdict()['ns'], builder.get_namespace())#Can't be got with ElementTree, because it's a namespace

        d_ns    = {'my': builder.namespace, 'xsi': "{http://www.w3.org/2001/XMLSchema-instance}"}
        xml     = XML(content)

        for field in builder.fields:
            field_node = xml.find('{%s}%s' % (builder.namespace, field.name))
            self.assert_(field_node is not None)#Beware : bool(field_node) doesn't work !
            if field.is_nillable:
                self.assertEqual("true", field_node.get('%(xsi)snil' % d_ns))

    def test_upgrade_xsl01(self):
        body_map={'user_id': 1, 'is_actived': True, "first_name":"",
                  "last_name":"", "email": "none@none.com",
                  "description": "", "birthday":"", "created":"", 'url_site': ""}
        backend = self._get_create_from_email_backend(subject="create_contact",
                                                      body_map=body_map,
                                                      model=Contact)
        builder = self._get_builder(backend)

        content = builder._render_upgrade_xsl(self.request)
        self.assertEqual(re.search('xmlns:my="(?P<ns>[\w\d\-:/\.]*)"', content).groupdict()['ns'], builder.namespace)#Can't be got with ElementTree, because it's a namespace

        d_ns    = {'xsl': "{http://www.w3.org/1999/XSL/Transform}"}
        xml     = XML(content)

        fields_names = set("my:%s" % field_name for field_name in body_map.iterkeys())
        element_nodes = xml.findall("%(xsl)stemplate/%(xsl)scopy/%(xsl)selement/" % d_ns)
        xsl_fields_names = set(element_node.get('name') for element_node in element_nodes)
        self.assertEqual(fields_names, xsl_fields_names)

    def _get_view_xsl(self, body_map):
        backend = self._get_create_from_email_backend(subject="create_contact",
                                                      body_map=body_map,
                                                      model=Contact)
        builder = self._get_builder(backend)

        content = builder._render_view_xsl(self.request)
        self.assertEqual(re.search('xmlns:my="(?P<ns>[\w\d\-:/\.]*)"', content).groupdict()['ns'], builder.namespace)#Can't be got with ElementTree, because it's a namespace
        return XML(content.encode('utf-8'))

    def _test_view_xsl_01(self, field_name, attrs={}, node_type="span"):
        d_ns    = {'xsl': "{http://www.w3.org/1999/XSL/Transform}", 'xd': "{http://schemas.microsoft.com/office/infopath/2003}"}
        xml     = self._get_view_xsl({field_name: ""})
        node_vb =  xml.find('%(xsl)stemplate/div/div/table/tbody/tr/td/div/font/strong' % d_ns)
        self.assert_(node_vb is not None)
        self.assertEqual(Contact._meta.get_field(field_name).verbose_name, node_vb.text)

        node_content =  xml.find(('%(xsl)stemplate/div/div/table/tbody/tr/td/div/font/' % d_ns)+node_type)#TODO span
        for attr, expected_value in attrs.items():
            self.assertEqual(expected_value, node_content.get(attr % d_ns))

    def test_view_xsl01(self):#Simple attr verification
        fields = {
            "first_name": ({
                "class":         "xdTextBox",
                "%(xd)sCtrlId":  "first_name",
                "%(xd)sxctname": "PlainText",
                "%(xd)sbinding": "my:first_name",
            }, "span"),
            "last_name": ({
                "class":         "xdTextBox",
                "%(xd)sCtrlId":  "last_name",
                "%(xd)sxctname": "PlainText",
                "%(xd)sbinding": "my:last_name",
            },"span"),
            "email": ({
                "class":         "xdTextBox",
                "%(xd)sCtrlId":  "email",
                "%(xd)sxctname": "PlainText",
                "%(xd)sbinding": "my:email",
            },"span"),
            "url_site": ({
                "class":         "xdTextBox",
                "%(xd)sCtrlId":  "url_site",
                "%(xd)sxctname": "PlainText",
                "%(xd)sbinding": "my:url_site",
            },"span"),
            "description": ({
                "class":         "xdRichTextBox",
                "%(xd)sCtrlId":  "description",
                "%(xd)sxctname": "RichText",
                "%(xd)sbinding": "my:description",
                "contentEditable": "true",
            },"span"),
            "is_actived": ({
                "class":           "xdBehavior_Boolean",
                "%(xd)sCtrlId":    "is_actived",
                "%(xd)sxctname":   "CheckBox",
                "%(xd)sbinding":   "my:is_actived",
                "%(xd)sboundProp": "xd:value",
                "%(xd)soffValue":  "false",
                "%(xd)sonValue":   "true",
                "type":            "checkbox",
            },"input"),
            "birthday": ({
                "class":           "xdDTPicker",
                "%(xd)sCtrlId":    "birthday",
                "%(xd)sxctname":   "DTPicker",
            },"div"),
            "created": ({
                "class":           "xdDTPicker",
                "%(xd)sCtrlId":    "created",
                "%(xd)sxctname":   "DTPicker",
            },"div"),
        }
        for field_name, attrs_nodetype in fields.iteritems():
            attrs, node_type = attrs_nodetype
            self._test_view_xsl_01(field_name, attrs, node_type)

    def test_view_xsl02(self):#Deeper with DateField
        d_ns    = {'xsl': "{http://www.w3.org/1999/XSL/Transform}", 'xd': "{http://schemas.microsoft.com/office/infopath/2003}"}
        field_name = "birthday"
        xml     = self._get_view_xsl({field_name: ""})
        node_vb =  xml.find('%(xsl)stemplate/div/div/table/tbody/tr/td/div/font/strong' % d_ns)
        self.assert_(node_vb is not None)
        self.assertEqual(Contact._meta.get_field(field_name).verbose_name, node_vb.text)

        target_node =  xml.find('%(xsl)stemplate/div/div/table/tbody/tr/td/div/font/div/span' % d_ns)
        self.assertEqual("my:%s" % field_name, target_node.find('%(xsl)sattribute/%(xsl)svalue-of' % d_ns).get('select'))

    def test_view_xsl03(self):#Deeper with ForeignKey
        d_ns    = {'xsl': "{http://www.w3.org/1999/XSL/Transform}", 'xd': "{http://schemas.microsoft.com/office/infopath/2003}"}
        field_name = "user_id"
        xml     = self._get_view_xsl({field_name: ""})

        node_vb =  xml.find('%(xsl)stemplate/div/div/table/tbody/tr/td/div/font/strong' % d_ns)
        self.assert_(node_vb is not None)
        self.assertEqual(Contact._meta.get_field("user").verbose_name, node_vb.text)

        attrs = {"class":"xdComboBox xdBehavior_Select", "%(xd)sxctname": "dropdown", "%(xd)sCtrlId": field_name, "%(xd)sbinding": "my:%s" % field_name}
        target_node =  xml.find('%(xsl)stemplate/div/div/table/tbody/tr/td/div/font/select' % d_ns)
        for attr, expected_value in attrs.items():
            self.assertEqual(expected_value, target_node.get(attr % d_ns))

        options = target_node.findall('option')
        self.assert_(options)#At least, it must have empty choice

        default_choice_set = set([('my:%s=""' % field_name, ugettext(u"Select..."))])
        users_set = set(('my:%s="%s"' % (field_name, user.pk), unicode(user)) for user in User.objects.all()) | default_choice_set

        options_set = set((option.find('%(xsl)sif' % d_ns).get('test'),re.search(r'if>(?P<username>.*)</option>', tostring(option,  encoding='utf8').decode('utf8')).groupdict()['username']) for option in options)
        self.assertEqual(users_set, options_set)

    def test_render01(self):
        body_map={'user_id': 1, 'is_actived': True, "first_name":"",
          "last_name":"", "email": "none@none.com",
          "description": "", "birthday":"", "created":"", 'url_site': ""}
        backend = self._get_create_from_email_backend(subject="create_contact",
                                                      body_map=body_map,
                                                      model=Contact)
        builder = self._get_builder(backend)
        builder.render()

        backend_dir = builder._get_backend_dir()
        dir_exists = os.path.exists
        join = os.path.join

        self.assert_(dir_exists(backend_dir))
        self.assert_(dir_exists(join(backend_dir, 'creme.png')))
        self.assert_(dir_exists(join(backend_dir, 'manifest.xsf')))
        self.assert_(dir_exists(join(backend_dir, 'myschema.xsd')))
        self.assert_(dir_exists(join(backend_dir, 'template.xml')))
        self.assert_(dir_exists(join(backend_dir, 'upgrade.xsl')))
        self.assert_(dir_exists(join(backend_dir, 'view1.xsl')))

        self.assert_(dir_exists(join(backend_dir, '%s.xsn' % backend.subject)))

    def test_get_create_form_view01(self):#Backend not registered
        subject="create_contact"
        backend = self._get_create_from_email_backend(subject=subject,
                                                      body_map={},
                                                      model=Contact)

        response = self.client.get('/crudity/infopath/create_form/%s' % subject)
        self.assertEqual(404, response.status_code)

    def test_get_create_form_view02(self):
        subject="create_contact"
        backend = self._get_create_from_email_backend(subject=subject,
                                                      body_map={},
                                                      model=Contact)

        from_email_crud_registry.register_creates((subject, backend))

        response = self.client.get('/crudity/infopath/create_form/%s' % subject)
        self.assertEqual(200, response.status_code)



class InfopathFormFieldTestCase(CrudityTestCase):
    def test_uuid01(self):#uuid for a field has to be unique and the same BY FORM (so by backend)
        request  = self.client.get('/').context['request']
        #Backend 1
        backend1 = self._get_create_from_email_backend(subject="create_ce")
        builder1 = InfopathFormBuilder(request=request, backend=backend1)
        uuid1 = InfopathFormField(builder1.urn, CremeEntity, 'user_id', request).uuid
        for i in xrange(10):
            self.assertEqual(uuid1, InfopathFormField(builder1.urn, CremeEntity, 'user_id', request).uuid)

        #Backend 2
        backend2 = self._get_create_from_email_backend(subject="create_ce2")
        builder2 = InfopathFormBuilder(request=request, backend=backend2)

        uuid2 = InfopathFormField(builder2.urn, CremeEntity, 'user_id', request).uuid
        for i in xrange(10):
            self.assertEqual(uuid2, InfopathFormField(builder2.urn, CremeEntity, 'user_id', request).uuid)

        self.assertNotEqual(uuid2, uuid1)

        #Backend 3
        backend3 = self._get_create_from_email_backend(subject="create_contact", model=Contact)
        builder3 = InfopathFormBuilder(request=request, backend=backend3)

        uuid3 = InfopathFormField(builder3.urn, Contact, 'user_id', request).uuid
        for i in xrange(10):
            self.assertEqual(uuid3, InfopathFormField(builder3.urn, Contact, 'user_id', request).uuid)

        self.assertNotEqual(uuid1, uuid3)
        self.assertNotEqual(uuid2, uuid3)

        #And again Backend 1
        backend4 = self._get_create_from_email_backend(subject="create_ce")
        builder4 = InfopathFormBuilder(request=request, backend=backend4)

        uuid4 = InfopathFormField(builder4.urn, CremeEntity, 'user_id', request).uuid
        self.assertEqual(uuid1, uuid4)

    def test_get_field01(self):
        request  = self.client.get('/').context['request']
        body_map = {'user_id': 1, 'is_actived': True, "first_name":"",
                    "last_name":"", "email": "none@none.com", "description": "", "birthday":"",}

        backend = self._get_create_from_email_backend(subject="create_contact",
                                                      body_map=body_map,
                                                      model=Contact)
        builder = InfopathFormBuilder(request=request, backend=backend)

        model_get_field = Contact._meta.get_field


        self.assertEqual(model_get_field('user'),        InfopathFormField(builder.urn, Contact, 'user_id', request)._get_model_field())
        self.assertEqual(model_get_field('first_name'),  InfopathFormField(builder.urn, Contact, 'first_name', request)._get_model_field())
        self.assertEqual(model_get_field('last_name'),   InfopathFormField(builder.urn, Contact, 'last_name', request)._get_model_field())
        self.assertEqual(model_get_field('email'),       InfopathFormField(builder.urn, Contact, 'email', request)._get_model_field())
        self.assertEqual(model_get_field('description'), InfopathFormField(builder.urn, Contact, 'description', request)._get_model_field())
        self.assertEqual(model_get_field('birthday'),    InfopathFormField(builder.urn, Contact, 'birthday', request)._get_model_field())

        self.assertRaises(FieldDoesNotExist, InfopathFormField, builder.urn, Contact, 'email_id', request)

    def test_get_choices01(self):
        request  = self.client.get('/').context['request']
        body_map = {'user_id': 1,}
        backend = self._get_create_from_email_backend(subject="create_contact",
                                                      body_map=body_map,
                                                      model=Contact)
        builder = InfopathFormBuilder(request=request, backend=backend)

        user_choices_set = set((user.pk, unicode(user)) for user in User.objects.all())
        self.assertEqual(user_choices_set, set(InfopathFormField(builder.urn, Contact, 'user_id', request)._get_choices()))
