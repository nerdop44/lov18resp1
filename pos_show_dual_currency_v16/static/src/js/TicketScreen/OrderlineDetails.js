odoo.define('1010_pos_dual_currency.OrderlineDetails', function (require) {
    'use strict';

    const OrderlineDetails = require('point_of_sale.OrderlineDetails');
    const Registries = require('point_of_sale.Registries');
    const { format } = require('web.field_utils');
    const { round_precision: round_pr } = require('web.utils');

    /**
     * @props {pos.order.line} line
     */
     const OrderlineDetailsUSD = (OrderlineDetails) =>
        class extends OrderlineDetails {

        get totalPrice_ref() {
            const trm = 1/this.env.pos.config.show_currency_rate;
            if (trm!=0){
                return this.env.pos.format_currency_ref(this.line.totalPrice/trm);
                }
            else{
                return this.env.pos.format_currency_ref(this.line.totalPrice);
                }

        }

        get unitPrice_ref() {
            const trm = 1/this.env.pos.config.show_currency_rate;
            if (trm!=0){
                return this.env.pos.format_currency_ref(this.line.unitPrice/trm);
                }
            else{
                return this.env.pos.format_currency_ref(this.line.unitPrice);
                }
        }
        get pricePerUnit() {
            const trm = 1/this.env.pos.config.show_currency_rate;
            if (trm!=0){
                return ` ${this.unit} at ${this.unitPrice} - ${this.unitPrice_ref} / ${this.unit}`;
            }else{
                return ` ${this.unit} at ${this.unitPrice} / ${this.unit}`;
            }

        }

    };


    Registries.Component.extend(OrderlineDetails, OrderlineDetailsUSD);

    return OrderlineDetails;
});
