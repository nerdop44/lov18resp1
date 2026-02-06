/* global waitForWebfonts */
odoo.define('pos_show_dual_currency.models', function (require) {
    "use strict";

    const { PosGlobalState } = require('point_of_sale.models');
    const Registries = require('point_of_sale.Registries');
    const { uuidv4 } = require('point_of_sale.utils');
    const core = require('web.core');
    const Printer = require('point_of_sale.Printer').Printer;
    const { batched } = require('point_of_sale.utils')
    const QWeb = core.qweb;


    const CurrencyRefPosGlobalState = (PosGlobalState) => class CurrencyRefPosGlobalState extends PosGlobalState {
        constructor(obj) {
            super(obj);
            this.res_currency_ref = null;
        }
        //@override
        async _processData(loadedData) {
            await super._processData(...arguments);
            this.res_currency_ref = loadedData['res_currency_ref'];
        }
        format_currency_ref(amount) {
            amount = this.format_currency_no_symbol(amount, this.res_currency_ref.decimal_places, this.res_currency_ref);
            if (this.res_currency_ref.position === 'after') {
                return amount + ' ' + (this.res_currency_ref.symbol || '');
            } else {
                return (this.res_currency_ref.symbol || '') + ' ' + amount;
            }
        }
        async getClosePosInfo() {
            const info = await super.getClosePosInfo();
            const amount_authorized_diff_ref = info.amount_authorized_diff_ref;

            const state_new = { notes: '', acceptClosing: false, payments: {}, notes_ref: '', acceptClosing_usd: false, payments_usd: {} };
            if (info.cashControl || info.default_cash_details) {
                const default_cash = info.default_cash_details;
                state_new.payments[default_cash.id] = { counted: 0, difference: -default_cash.amount, number: 0 };
                if (default_cash.default_cash_details_ref) {
                    state_new.payments_usd[default_cash.default_cash_details_ref.id] = { counted: 0, difference: -default_cash.default_cash_details_ref.amount, number: 0 };
                }
            }

            const non_cash_methods = info.non_cash_payment_methods || info.other_payment_methods || [];
            if (non_cash_methods.length > 0) {
                non_cash_methods.forEach(pm => {
                    if (pm.type === 'bank') {
                        state_new.payments[pm.id] = { counted: this.env.utils.isValidFloat(pm.amount) ? pm.amount : 0, difference: 0, number: pm.number }
                    }
                })
            }

            return {
                ...info,
                state: state_new,
                amount_authorized_diff_ref,
            }
        }


    }
    Registries.Model.extend(PosGlobalState, CurrencyRefPosGlobalState);

});
