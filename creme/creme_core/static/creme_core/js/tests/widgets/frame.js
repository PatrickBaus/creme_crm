/* globals setTimeout */
(function($) {

function mock_frame_create(url, noauto) {
    var select = $('<div widget="ui-creme-frame" class="ui-creme-frame ui-creme-widget"/>');

    if (url !== undefined) {
        select.attr('url', url);
    }

    if (!noauto) {
        select.addClass('widget-auto');
    }

    return select;
}

var MOCK_FRAME_CONTENT = '<div class="mock-content"><h1>This a frame test</h1></div>';
var MOCK_FRAME_CONTENT_LIST = '<div class="mock-content"><ul><li>Item 1</li><li>Item 2</li></ul></div>';
var MOCK_FRAME_CONTENT_FORM = '<form action="mock/submit"><input type="text" id="firstname"/><input type="text" id="lastname"/></form>';
var MOCK_FRAME_CONTENT_FORM_NOACTION = '<form action=""><input type="text" id="firstname"/><input type="text" id="lastname"/></form>';
var MOCK_FRAME_CONTENT_SUBMIT_JSON = '<json>' + $.toJSON({value: 1, added: [1, 'John Doe']}) + '</json>';
var MOCK_FRAME_CONTENT_SUBMIT_JSON_NOTAG = $.toJSON({value: 1, added: [1, 'John Doe']});
var MOCK_FRAME_CONTENT_SUBMIT_JSON_INVALID = '<json>' + '{"value":1, added:[1, "John Doe"}' + '</json>';

QUnit.module("creme.widget.frame.js", new QUnitMixin(QUnitEventMixin, QUnitAjaxMixin, {
    buildMockBackend: function() {
        return new creme.ajax.MockAjaxBackend({delay: 150, sync: true, name: 'creme.widget.frame.js'});
    },

    beforeEach: function() {
        var self = this;
        this.setMockBackendGET({
            'mock/html': this.backend.response(200, MOCK_FRAME_CONTENT),
            'mock/html2': this.backend.response(200, MOCK_FRAME_CONTENT_LIST),
            'mock/submit': this.backend.response(200, MOCK_FRAME_CONTENT_FORM),
            'mock/forbidden': this.backend.response(403, 'HTTP - Error 403'),
            'mock/error': this.backend.response(500, 'HTTP - Error 500'),
            'mock/custom': function(url, data, options) {
                return self._custom_GET(url, data, options);
            }
        });

        this.setMockBackendPOST({
            'mock/submit/json': this.backend.response(200, MOCK_FRAME_CONTENT_SUBMIT_JSON),
            'mock/submit': this.backend.response(200, MOCK_FRAME_CONTENT_FORM),
            'mock/forbidden': this.backend.response(403, 'HTTP - Error 403'),
            'mock/error': this.backend.response(500, 'HTTP - Error 500')
        });
    },

    afterEach: function() {
        $('.ui-dialog-content').dialog('destroy');
        creme.widget.shutdown($('body'));
    },

    _custom_GET: function(url, data, options) {
        return this.backend.response(200, '<div>' + $.toJSON({url: url, method: 'GET', data: data}) + '</div>');
    }
}));

function assertOverlay(element, status, active) {
    var overlay = $('.ui-creme-overlay', element);
    equal(overlay.length, active ? 1 : 0, 'has overlay');
    equal(overlay.attr('status'), status, 'overlay status:' + status);
    equal(overlay.hasClass('overlay-active'), active || false, 'overlay isactive');
}

QUnit.test('creme.widget.Frame.create (undefined)', function(assert) {
    var element = mock_frame_create();

    creme.widget.create(element, {backend: this.backend});
    equal(element.hasClass('widget-active'), true);
    equal(element.hasClass('widget-ready'), true);

    assertOverlay(element, undefined, false);
    equal(0, $('h1', element).length);
});

QUnit.test('creme.widget.Frame.create (empty)', function(assert) {
    var element = mock_frame_create();

    creme.widget.create(element, {url: '', backend: this.backend});
    equal(element.hasClass('widget-active'), true);
    equal(element.hasClass('widget-ready'), true);

    assertOverlay(element, undefined, false);
    equal(0, $('h1', element).length);
});

QUnit.test('creme.widget.Frame.create (url)', function(assert) {
    var element = mock_frame_create('mock/html');

    creme.widget.create(element, {backend: this.backend});
    equal(element.hasClass('widget-active'), true);
    equal(element.hasClass('widget-ready'), true);

    assertOverlay(element, undefined, false);
    equal(1, $('h1', element).length);
});

QUnit.test('creme.widget.Frame.create (404)', function() {
    var element = mock_frame_create('mock/unknown');

    creme.widget.create(element, {backend: this.backend});
    equal(element.hasClass('widget-active'), true);
    equal(element.hasClass('widget-ready'), true);

    assertOverlay(element, '404', true);
    equal(0, $('h1', element).length);
});

QUnit.test('creme.widget.Frame.create (403)', function(assert) {
    var element = mock_frame_create('mock/forbidden');

    creme.widget.create(element, {backend: this.backend});
    equal(element.hasClass('widget-active'), true);
    equal(element.hasClass('widget-ready'), true);

    assertOverlay(element, '403', true);
    equal(0, $('h1', element).length);
});

QUnit.test('creme.widget.Frame.create (500)', function(assert) {
    var element = mock_frame_create('mock/error');

    creme.widget.create(element, {backend: this.backend});
    equal(element.hasClass('widget-active'), true);
    equal(element.hasClass('widget-ready'), true);

    assertOverlay(element, '500', true);
    equal(0, $('h1', element).length);
});

QUnit.test('creme.widget.Frame.create (url, overlay not shown, async)', function(assert) {
    this.backend.options.sync = false;
    this.backend.options.delay = 100;

    var element = mock_frame_create('mock/html');

    creme.widget.create(element, {backend: this.backend});
    equal(element.hasClass('widget-active'), true);
    equal(element.hasClass('widget-ready'), true);
    equal(element.creme().widget().options().overlay_delay, 100);

    assertOverlay(element, undefined, false);
    equal(0, $('h1', element).length, 'content');

    stop(2);

    setTimeout(function() {
        assertOverlay(element, undefined, false);
        equal($('h1', element).length, 0);
        start();
    }, 90);

    setTimeout(function() {
        assertOverlay(element, undefined);
        equal($('h1', element).length, 1);
        start();
    }, 150);
});

QUnit.test('creme.widget.Frame.create (url, overlay shown, async)', function(assert) {
    this.backend.options.sync = false;
    this.backend.options.delay = 500;

    var element = mock_frame_create('mock/html');

    creme.widget.create(element, {backend: this.backend});
    equal(element.hasClass('widget-active'), true);
    equal(element.hasClass('widget-ready'), true);
    equal(element.creme().widget().options().overlay_delay, 100);

    assertOverlay(element, undefined);
    equal(0, $('h1', element).length);

    stop(3);

    setTimeout(function() {
        assertOverlay(element, undefined);
        equal(0, $('h1', element).length);
        start();
    }, 90);

    setTimeout(function() {
        assertOverlay(element, 'wait', true);
        equal(0, $('h1', element).length);
        start();
    }, 200);

    setTimeout(function() {
        assertOverlay(element, undefined);
        equal(1, $('h1', element).length);
        start();
    }, 700);
});

QUnit.test('creme.widget.Frame.create (url, overlay shown, async, error)', function(assert) {
    this.backend.options.sync = false;
    this.backend.options.delay = 500;

    var element = mock_frame_create('mock/forbidden');

    creme.widget.create(element, {backend: this.backend});
    equal(element.hasClass('widget-active'), true);
    equal(element.hasClass('widget-ready'), true);
    equal(element.creme().widget().options().overlay_delay, 100);

    assertOverlay(element, undefined);
    equal(0, $('h1', element).length);

    stop(3);

    setTimeout(function() {
        assertOverlay(element, undefined);
        equal(0, $('h1', element).length);
        start();
    }, 90);

    setTimeout(function() {
        assertOverlay(element, 'wait', true);
        equal(0, $('h1', element).length);
        start();
    }, 150);

    setTimeout(function() {
        assertOverlay(element, '403', true);
        equal(0, $('h1', element).length);
        start();
    }, 600);
});

QUnit.test('creme.widget.Frame.fill', function(assert) {
    var element = mock_frame_create();

    creme.widget.create(element, {backend: this.backend});
    equal(element.hasClass('widget-active'), true);
    equal(element.hasClass('widget-ready'), true);

    assertOverlay(element, undefined);
    equal(0, $('h1', element).length);
    equal(0, $('ul', element).length);

    element.creme().widget().fill(MOCK_FRAME_CONTENT);

    assertOverlay(element, undefined);
    equal(1, $('h1', element).length);
    equal(0, $('ul', element).length);

    element.creme().widget().fill(MOCK_FRAME_CONTENT);

    assertOverlay(element, undefined);
    equal(1, $('h1', element).length);
    equal(0, $('ul', element).length);

    element.creme().widget().fill(MOCK_FRAME_CONTENT_LIST);

    assertOverlay(element, undefined);
    equal(0, $('h1', element).length);
    equal(1, $('ul', element).length);
});

QUnit.test('creme.widget.Frame.reload (none)', function(assert) {
    var element = mock_frame_create('mock/html');

    creme.widget.create(element, {backend: this.backend});
    equal(element.hasClass('widget-active'), true);
    equal(element.hasClass('widget-ready'), true);

    assertOverlay(element, undefined);
    equal(1, $('h1', element).length);
    equal(0, $('ul', element).length);

    this.backend.GET['mock/html'] = this.backend.response(200, MOCK_FRAME_CONTENT_LIST);

    element.creme().widget().reload();

    assertOverlay(element, undefined);
    equal(0, $('h1', element).length);
    equal(1, $('ul', element).length);
});

QUnit.test('creme.widget.Frame.reload (none, async)', function(assert) {
    var element = mock_frame_create('mock/html');

    creme.widget.create(element, {backend: this.backend});
    equal(element.hasClass('widget-active'), true);
    equal(element.hasClass('widget-ready'), true);

    assertOverlay(element, undefined);
    equal(1, $('h1', element).length);
    equal(0, $('ul', element).length);

    this.backend.options.sync = false;
    this.backend.options.delay = 500;
    this.backend.GET['mock/html'] = this.backend.response(200, MOCK_FRAME_CONTENT_LIST);

    element.creme().widget().reload();

    stop(3);

    setTimeout(function() {
        assertOverlay(element, undefined);
        equal(1, $('h1', element).length);
        equal(0, $('ul', element).length);
        start();
    }, 90);

    setTimeout(function() {
        assertOverlay(element, 'wait', true);
        equal(1, $('h1', element).length);
        equal(0, $('ul', element).length);
        start();
    }, 150);

    setTimeout(function() {
        assertOverlay(element, undefined);
        equal(0, $('h1', element).length);
        equal(1, $('ul', element).length);
        start();
    }, 600);
});

QUnit.test('creme.widget.Frame.reload (url)', function(assert) {
    var element = mock_frame_create('mock/html');

    creme.widget.create(element, {backend: this.backend});
    equal(element.hasClass('widget-active'), true);
    equal(element.hasClass('widget-ready'), true);

    assertOverlay(element, undefined);
    equal(1, $('h1', element).length);
    equal(0, $('ul', element).length);

    element.creme().widget().reload('mock/html2');

    assertOverlay(element, undefined);
    equal(0, $('h1', element).length);
    equal(1, $('ul', element).length);
});

QUnit.test('creme.widget.Frame.reload (url, data)', function(assert) {
    var element = mock_frame_create('mock/html');

    creme.widget.create(element, {backend: this.backend});
    equal(element.hasClass('widget-active'), true);
    equal(element.hasClass('widget-ready'), true);

    assertOverlay(element, undefined);
    equal(1, $('h1', element).length);
    equal(0, $('ul', element).length);

    element.creme().widget().reload('mock/custom', {});

    assertOverlay(element, undefined);
    equal(0, $('h1', element).length);
    equal(element.html(), '<div>' + $.toJSON({url: 'mock/custom', method: 'GET', data: {}}) + '</div>');

    element.creme().widget().reload('mock/custom', {'a': 12});
    equal(0, $('h1', element).length);
    equal(element.html(), '<div>' + $.toJSON({url: 'mock/custom', method: 'GET', data: {'a': 12}}) + '</div>');
});

QUnit.test('creme.widget.Frame.reload (url, async)', function(assert) {
    var element = mock_frame_create('mock/html');

    creme.widget.create(element, {backend: this.backend});
    equal(element.hasClass('widget-active'), true);
    equal(element.hasClass('widget-ready'), true);

    assertOverlay(element, undefined);
    equal(1, $('h1', element).length);
    equal(0, $('ul', element).length);

    this.backend.options.sync = false;
    this.backend.options.delay = 500;

    element.creme().widget().reload('mock/html2');

    stop(3);

    setTimeout(function() {
        assertOverlay(element, undefined);
        equal(1, $('h1', element).length);
        equal(0, $('ul', element).length);
        start();
    }, 90);

    setTimeout(function() {
        assertOverlay(element, 'wait', true);
        equal(1, $('h1', element).length);
        equal(0, $('ul', element).length);
        start();
    }, 150);

    setTimeout(function() {
        assertOverlay(element, undefined);
        equal(0, $('h1', element).length);
        equal(1, $('ul', element).length);
        start();
    }, 600);
});

QUnit.test('creme.widget.Frame.reload (invalid url)', function(assert) {
    var element = mock_frame_create('mock/html');

    creme.widget.create(element, {backend: this.backend});
    equal(element.hasClass('widget-active'), true);
    equal(element.hasClass('widget-ready'), true);

    assertOverlay(element, undefined);
    equal(1, $('h1', element).length);
    equal(0, $('ul', element).length);

    element.creme().widget().reload('mock/error');

    assertOverlay(element, '500', true);
    equal(1, $('h1', element).length);
    equal(0, $('ul', element).length);
});

QUnit.test('creme.widget.Frame.reload (invalid url, async)', function(assert) {
    var element = mock_frame_create('mock/html');
    creme.widget.create(element, {backend: this.backend});
    equal(element.hasClass('widget-active'), true);
    equal(element.hasClass('widget-ready'), true);

    assertOverlay(element, undefined);
    equal(1, $('h1', element).length);
    equal(0, $('ul', element).length);

    this.backend.options.sync = false;
    this.backend.options.delay = 500;

    element.creme().widget().reload('mock/unknown');

    stop(3);

    setTimeout(function() {
        assertOverlay(element, undefined);
        equal(1, $('h1', element).length);
        equal(0, $('ul', element).length);
        start();
    }, 90);

    setTimeout(function() {
        assertOverlay(element, 'wait', true);
        equal(1, $('h1', element).length);
        equal(0, $('ul', element).length);
        start();
    }, 150);

    setTimeout(function() {
        assertOverlay(element, '404', true);
        equal(1, $('h1', element).length);
        equal(0, $('ul', element).length);
        start();
    }, 600);
});

QUnit.test('creme.widget.Frame.submit', function(assert) {
    var element = mock_frame_create('mock/submit');

    creme.widget.create(element, {backend: this.backend});
    equal(element.hasClass('widget-active'), true);
    equal(element.hasClass('widget-ready'), true);

    assertOverlay(element, undefined);
    equal(1, $('form', element).length);

    var listeners = {
        'submit-done': this.mockListener('success'),
        'submit-fail': this.mockListener('error')
    };

    element.creme().widget().submit($('form', element), listeners);
    deepEqual(this.mockListenerCalls('success'), [
        ['submit-done', MOCK_FRAME_CONTENT_FORM, 'ok', 'text/html']
    ], 'form html');
});

QUnit.test('creme.widget.Frame.submit (empty action)', function(assert) {
    var element = mock_frame_create('');

    creme.widget.create(element, {backend: this.backend});
    equal(element.hasClass('widget-active'), true);
    equal(element.hasClass('widget-ready'), true);

    element.creme().widget().fill(MOCK_FRAME_CONTENT_FORM_NOACTION);

    assertOverlay(element, undefined);
    equal(1, $('form', element).length);

    var listeners = {
        'submit-done': this.mockListener('success'),
        'submit-fail': this.mockListener('error')
    };


    // <form> action is empty. returns 404
    this.resetMockListenerCalls();
    this.setMockBackendPOST({
        'mock/submit': this.backend.response(200, MOCK_FRAME_CONTENT_FORM_NOACTION)
    });

    element.creme().widget().submit($('form', element), listeners);
    deepEqual(this.mockListenerCalls('error').map(function(e) { return e.slice(0, 1); }), [
        ['submit-fail']
    ]);
});

QUnit.test('creme.widget.Frame.submit (json)', function(assert) {
    var element = mock_frame_create('mock/submit');

    creme.widget.create(element, {backend: this.backend});
    equal(element.hasClass('widget-active'), true);
    equal(element.hasClass('widget-ready'), true);

    assertOverlay(element, undefined);
    equal(1, $('form', element).length);

    var listeners = {
        'submit-done': this.mockListener('success'),
        'submit-fail': this.mockListener('error')
    };

    // <json>{...}</json> response
    this.setMockBackendPOST({
        'mock/submit': this.backend.response(200, MOCK_FRAME_CONTENT_SUBMIT_JSON)
    });

    element.creme().widget().submit($('form', element), listeners);
    deepEqual(this.mockListenerCalls('success'), [
        ['submit-done', $.toJSON({value: 1, added: [1, 'John Doe']}), 'ok', 'text/json']
    ], 'form json');

    // {...} response
    this.resetMockListenerCalls();
    this.setMockBackendPOST({
        'mock/submit': this.backend.response(200, MOCK_FRAME_CONTENT_SUBMIT_JSON_NOTAG, {'content-type': 'text/json'})
    });

    element.creme().widget().reload('mock/submit');
    element.creme().widget().submit($('form', element), listeners);
    deepEqual(this.mockListenerCalls('success'), [
        ['submit-done', $.toJSON({value: 1, added: [1, 'John Doe']}), 'ok', 'text/json']
    ], 'form json no tag');

    // {invalid json} response
    this.resetMockListenerCalls();
    this.setMockBackendPOST({
        'mock/submit': this.backend.response(200, MOCK_FRAME_CONTENT_SUBMIT_JSON_INVALID)
    });

    element.creme().widget().reload('mock/submit');
    element.creme().widget().submit($('form', element), listeners);
    deepEqual(this.mockListenerCalls('success'), [
        ['submit-done', MOCK_FRAME_CONTENT_SUBMIT_JSON_INVALID, 'ok', 'text/html']
    ], 'form json invalid');
});

QUnit.test('creme.widget.Frame.submit (error)', function(assert) {
    var element = mock_frame_create('mock/submit');

    creme.widget.create(element, {backend: this.backend});
    equal(element.hasClass('widget-active'), true);
    equal(element.hasClass('widget-ready'), true);

    assertOverlay(element, undefined);
    equal(1, $('form', element).length);

    var listeners = {
        'submit-done': this.mockListener('success'),
        'submit-fail': this.mockListener('error')
    };

    this.setMockBackendPOST({
        'mock/submit': this.backend.response(500, 'HTTP - Error 500')
    });

    element.creme().widget().submit($('form', element), listeners);
    deepEqual(this.mockListenerCalls('error').map(function(e) { return e.slice(0, 1); }), [
        ['submit-fail']
    ]);
});

}(jQuery));
