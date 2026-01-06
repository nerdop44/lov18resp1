odoo.define('1010_pos_dual_currency.TicketScreen', function (require) {
    'use strict';

    const { Order } = require('point_of_sale.models');
    const TicketScreen = require('point_of_sale.TicketScreen');
    const Registries = require('point_of_sale.Registries');
    const IndependentToOrderScreen = require('point_of_sale.IndependentToOrderScreen');
    const NumberBuffer = require('point_of_sale.NumberBuffer');
    const { useListener } = require("@web/core/utils/hooks");
    const { parse } = require('web.field_utils');

    const { onMounted, onWillUnmount, useState } = owl;

    const TicketScreenUSD = (TicketScreen) =>
    class extends TicketScreen {

        getTotalUSD(order) {
            const trm = 1/this.env.pos.config.show_currency_rate;
            if (trm!=0){
                return this.env.pos.format_currency_ref(order.get_total_with_tax()/trm);
                }
            else{
                return this.env.pos.format_currency_ref(order.get_total_with_tax());
                }
            }
    };

    Registries.Component.extend(TicketScreen, TicketScreenUSD);

    return TicketScreen;
});
