odoo.define('1010_pos_dual_currency.OrderSummary', function(require) {
    'use strict';

    const OrderSummary = require('point_of_sale.OrderSummary');
    const Registries = require('point_of_sale.Registries');
    const { float_is_zero } = require('web.utils');

    const OrderSummaryUSD = (OrderSummary) =>
    class  extends OrderSummary {
        getTaxRef() {
            const trm = 1/this.env.pos.config.show_currency_rate;
            const total = this.props.order.get_total_with_tax();
            const totalWithoutTax = this.props.order.get_total_without_tax();
            if (trm!=0){
                const taxAmount = (total - totalWithoutTax)/ trm;
                return {
                hasTax: !float_is_zero(taxAmount, this.env.pos.currency.decimal_places),
                displayAmount: this.env.pos.format_currency_ref(taxAmount),
            };
            }else{
                return {
                hasTax: !float_is_zero(taxAmount, this.env.pos.currency.decimal_places),
                displayAmount: this.env.pos.format_currency_ref(taxAmount),
            };
            }


        }
    };
    Registries.Component.extend(OrderSummary, OrderSummaryUSD);

    return OrderSummary;
});
