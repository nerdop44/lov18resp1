odoo.define('1010_pos_dual_currency.OrderDetails', function (require) {
    'use strict';

    const OrderDetails = require('point_of_sale.OrderDetails');
    const Registries = require('point_of_sale.Registries');

    const OrderDetailsUSD = (OrderDetails) =>
    class extends OrderDetails {

        get total_ref() {
            const trm = 1/this.env.pos.config.show_currency_rate;
            if (trm!=0){
                return this.env.pos.format_currency_ref(this.order ? this.order.get_total_with_tax() / trm : 0);
                }
            else{
                return this.env.pos.format_currency_ref(this.order ? this.order.get_total_with_tax() : 0);
                }

        }
        get tax_ref() {
            const trm = 1/this.env.pos.config.show_currency_rate;
            if (trm!=0){
                return this.env.pos.format_currency_ref(this.order ? this.order.get_total_tax() / trm : 0);
                }
            else{
                return this.env.pos.format_currency_ref(this.order ? this.order.get_total_tax() : 0)
                }

        }
    };


    Registries.Component.extend(OrderDetails, OrderDetailsUSD);

    return OrderDetails;
});
