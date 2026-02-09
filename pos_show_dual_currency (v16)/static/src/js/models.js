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
        const closingData = await this.env.services.rpc({
            model: 'pos.session',
            method: 'get_closing_control_data',
            args: [[this.pos_session.id]]
        });
        const amountAuthorizedDiffUSD = closingData.amount_authorized_diff_ref;

        const info = await super.getClosePosInfo();
        const state_new = {notes: '', acceptClosing: false, payments: {}, notes_ref: '', acceptClosing_usd: false, payments_usd: {}};
        if (info.cashControl) {
            state_new.payments[info.defaultCashDetails.id] = {counted: 0, difference: -info.defaultCashDetails.amount, number: 0};
            state_new.payments_usd[info.defaultCashDetails.default_cash_details_ref.id] = {counted: 0, difference: -info.defaultCashDetails.default_cash_details_ref.amount, number: 0};
        }

        if (info.otherPaymentMethods.length > 0) {
            info.otherPaymentMethods.forEach(pm => {
                if (pm.type === 'bank') {
                    state_new.payments[pm.id] = {counted: this.round_decimals_currency(pm.amount), difference: 0, number: pm.number}
                }
            })
        }

        const state = state_new;
        const ordersDetails = info.ordersDetails;
        const paymentsAmount = info.paymentsAmount;
        const payLaterAmount = info.payLaterAmount;
        const openingNotes = info.openingNotes;
        const defaultCashDetails = info.defaultCashDetails;
        const otherPaymentMethods = info.otherPaymentMethods;
        const isManager = info.isManager;
        const amountAuthorizedDiff = info.amountAuthorizedDiff;
        const cashControl = info.cashControl;


        return {
            ordersDetails, paymentsAmount, payLaterAmount, openingNotes, defaultCashDetails, otherPaymentMethods,
            isManager, amountAuthorizedDiff, state, cashControl, amountAuthorizedDiffUSD
        }
    }


}
Registries.Model.extend(PosGlobalState, CurrencyRefPosGlobalState);

});
