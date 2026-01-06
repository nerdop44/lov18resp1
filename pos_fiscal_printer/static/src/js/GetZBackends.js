odoo.define('pos_fiscal_printer.get_z_backend_widget', function (require) {
"use strict";

    var core = require('web.core');
    var Widget = require('web.Widget');

    var CustomWidget = Widget.extend({
        template: 'your_module.custom_template',

        init: function (parent) {
            this._super(parent);
        },

        customFunction: function () {
            // your code here
            alert('Hello World');
        },
    });

    return CustomWidget;

});