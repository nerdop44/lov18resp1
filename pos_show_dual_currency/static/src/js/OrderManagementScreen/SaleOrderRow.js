odoo.define('1010_pos_dual_currency.SaleOrderRow', function (require) {
    'use strict';

    const SaleOrderRow = require('pos_sale.SaleOrderRow');
    const Registries = require('point_of_sale.Registries');
    const utils = require('web.utils');
    const SaleOrderRowUSD = (SaleOrderRow) =>
        class extends SaleOrderRow {
            get total_ref() {
                const trm = 1/this.env.pos.config.show_currency_rate
                if (trm!=0){
                    return this.env.pos.format_currency_ref(this.order.amount_total/trm);
                }else{
                    return this.env.pos.format_currency_ref(this.order.amount_total);
                }

            }
            get showAmountUnpaid_ref() {
                const difference = this.order.amount_total - this.order.amount_unpaid
                const isFullAmountUnpaid = utils.float_is_zero(Math.abs(difference), this.env.pos.show_currency.decimal_places);
                const trm = 1/this.env.pos.config.show_currency_rate
                if (trm!=0){
                    isFullAmountUnpaid = utils.float_is_zero(Math.abs(difference/trm), this.env.pos.show_currency.decimal_places);
                    return !isFullAmountUnpaid && !utils.float_is_zero(this.order.amount_unpaid * trm, this.env.pos.show_currency.decimal_places);
                }else{
                    return !isFullAmountUnpaid && !utils.float_is_zero(this.order.amount_unpaid, this.env.pos.show_currency.decimal_places);
                }

            }


    };


    Registries.Component.extend(SaleOrderRow, SaleOrderRowUSD);

    return SaleOrderRow;
});
