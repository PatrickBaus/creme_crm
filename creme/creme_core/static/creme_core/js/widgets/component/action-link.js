/*******************************************************************************
 Creme is a free/open-source Customer Relationship Management software
 Copyright (C) 2015-2018  Hybird

 This program is free software: you can redistribute it and/or modify
 it under the terms of the GNU Affero General Public License as published by
 the Free Software Foundation, either version 3 of the License, or
 (at your option) any later version.

 This program is distributed in the hope that it will be useful,
 but WITHOUT ANY WARRANTY; without even the implied warranty of
 MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 GNU Affero General Public License for more details.

 You should have received a copy of the GNU Affero General Public License
 along with this program.  If not, see <http://www.gnu.org/licenses/>.
 *******************************************************************************/

(function($) {
"use strict";

creme.action = creme.action || {};

creme.action.ActionLink = creme.component.Component.sub({
    _init_: function(options) {
        this._options = $.extend({
            strict: false,
            debounce: 0
        }, options || {});

        this._running = false;
        this._events = new creme.component.EventHandler();
        this._registry = new creme.action.ActionBuilderRegistry();
    },

    on: function(event, listener, decorator) {
        this._events.on(event, listener, decorator);
        return this;
    },

    off: function(event, listener) {
        this._events.off(event, listener);
        return this;
    },

    one: function(event, listener) {
        this._events.one(event, listener);
    },

    onComplete: function(listener, decorator) {
        this.on('action-link-done action-link-cancel action-link-fail', listener, decorator);
    },

    builders: function(builders) {
        if (builders instanceof creme.action.ActionBuilderRegistry) {
            this._registry = builders;
        } else if (Object.isFunc(builders)) {
            this._registry = new creme.action.ActionBuilderRegistry({
                fallback: builders
            });
        } else if (builders instanceof Object) {
            this._registry = new creme.action.ActionBuilderRegistry({
                builders: builders
            });
        } else {
            throw Error('action builder "%s" is not valid'.format(builders));
        }

        return this;
    },

    trigger: function(event) {
        this._events.trigger(event, Array.copy(arguments).slice(1), this);
        return this;
    },

    isRunning: function() {
        return this._running === true;
    },

    isBound: function() {
        return Object.isNone(this._button) === false;
    },

    isDisabled: function() {
        return this.isBound() && this._button.is('.is-disabled');
    },

    options: function() {
        return this._options;
    },

    _debounce: function(handler, delay) {
        if (delay > 0) {
            return creme.utils.debounce(handler, delay);
        } else {
            return handler;
        }
    },

    _optActionBuilder: function(button, actiontype) {
        return this._registry.get(actiontype, this.options().strict);
    },

    _optActionData: function(button) {
        try {
            var data = $('script:first', button).text();
            return Object.isEmpty(data) ? {} : JSON.parse(data);
        } catch (e) {
            console.warn(e);
            return {};
        }
    },

    _optDebounceDelay: function(button) {
        var delay = parseInt(button.attr('data-debounce') || '');
        return isNaN(delay) ? this._options.debounce : delay;
    },

    bind: function(button) {
        if (this.isBound()) {
            throw Error('action link is already bound');
        }

        var url = button.attr('href') || button.attr('data-action-url');
        var enabled = button.is(':not(.is-disabled)');
        var actiontype = button.attr('data-action') || '';
        var isRunning = this.isRunning.bind(this);
        var trigger = this.trigger.bind(this);
        var setRunning = function(state) {
                             this._running = state;
                             button.toggleClass('is-loading', state);
                         }.bind(this);

        var debounceDelay = this._optDebounceDelay(button);
        var actiondata = this._optActionData(button);
        var builder = this._optActionBuilder(button, actiontype);
        var isvalid = Object.isFunc(builder);

        if (isvalid && enabled) {
            var handler = this._debounce(function(e) {
                if (!isRunning()) {
                    var action = builder(url, actiondata.options, actiondata.data, e);

                    if (Object.isNone(action) === false) {
                        trigger('action-link-start', url, actiondata.options || {}, actiondata.data || {}, e);
                        setRunning(true);
                        action.one('done fail cancel error', function() {
                                   setRunning(false);
                               })
                              .one({
                                  error: function(e, key, data, listener) {
                                      trigger('action-link-error', Array.copy(arguments).slice(1), this);
                                  },
                                  done: function() {
                                      trigger('action-link-done', Array.copy(arguments).slice(1), this);
                                  },
                                  cancel: function() {
                                      trigger('action-link-cancel', Array.copy(arguments).slice(1), this);
                                  },
                                  fail: function() {
                                      trigger('action-link-fail', Array.copy(arguments).slice(1), this);
                                  }
                               })
                              .start();
                    }
                }
            }, debounceDelay);

            // the handler is deferred, not the event. This prevents default behaviour of links.
            button.click(function(e) {
                e.preventDefault();
                e.stopPropagation();
                handler(e);
            });
        } else {
            button.addClass('is-disabled');
            button.click(function(e) {
                e.preventDefault();
                e.stopPropagation();
                return false;
            });
        }

        this._button = button;
        return this;
    }
});

}(jQuery));
