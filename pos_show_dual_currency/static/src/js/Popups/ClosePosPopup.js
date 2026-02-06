/** @odoo-module **/

import { ClosePosPopup } from "@point_of_sale/app/navbar/closing_popup/closing_popup";
import { MoneyDetailsPopupUSD } from "./MoneyDetailsPopup";
import { patch } from "@web/core/utils/patch";
import { useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { ask } from "@point_of_sale/app/store/make_awaitable_dialog";

patch(ClosePosPopup.prototype, {
    setup() {
        super.setup();
        this.manualInputCashCountUSD = false;
        // The pos store should already have some payments_usd initialized if coming from getClosePosInfo
        Object.assign(this.state, {
            displayMoneyDetailsPopupUSD: false,
            payments_usd: this.props.state?.payments_usd || {},
            ...(this.props.state || {}),
        });
    },

    //@override
    async confirm() {
        if (!this.props.cashControl || !this.hasDifferenceUSD()) {
            return super.confirm();
        } else if (this.hasUserAuthorityUSD()) {
            const confirmed = await ask(this.dialog, {
                title: _t('Currency Ref Payments Difference'),
                body: _t('Do you want to accept currency ref payments difference and post a profit/loss journal entry?'),
            });
            if (confirmed) {
                return super.confirm();
            }
        } else {
            await ask(this.dialog, {
                title: _t('Currency Ref Payments Difference'),
                body: _.str.sprintf(
                    _t('The maximum difference by currency ref allowed is %s.\n\
                    Please contact your manager to accept the closing difference.'),
                    this.pos.format_currency_ref(this.props.amount_authorized_diff_ref)
                ),
                confirmLabel: _t('OK'),
            });
        }
    },

    openDetailsPopupUSD() {
        const ref_id = this.props.default_cash_details.default_cash_details_ref.id;
        if (!this.state.payments_usd[ref_id]) {
            this.state.payments_usd[ref_id] = { counted: 0, difference: 0 };
        }
        this.state.payments_usd[ref_id].counted = 0;
        this.state.payments_usd[ref_id].difference = -this.props.default_cash_details.default_cash_details_ref.amount;
        this.state.displayMoneyDetailsPopupUSD = true;
    },

    closeDetailsPopupUSD() {
        this.state.displayMoneyDetailsPopupUSD = false;
    },

    handleInputChangeUSD(paymentId) {
        let expectedAmount;
        if (paymentId === this.props.default_cash_details.default_cash_details_ref.id) {
            this.manualInputCashCountUSD = true;
            expectedAmount = this.props.default_cash_details.default_cash_details_ref.amount;
        } else {
            expectedAmount = this.props.other_payment_methods.find(pm => paymentId === pm.id).amount;
        }
        this.state.payments_usd[paymentId].difference =
            this.pos.round_decimals_currency(this.state.payments_usd[paymentId].counted - expectedAmount);
    },

    updateCountedCashUSD({ total_ref, moneyDetailsNotesRef }) {
        const ref_id = this.props.default_cash_details.default_cash_details_ref.id;
        this.state.payments_usd[ref_id].counted = total_ref;
        this.state.payments_usd[ref_id].difference =
            this.pos.round_decimals_currency(this.state.payments_usd[ref_id].counted - this.props.default_cash_details.default_cash_details_ref.amount);
        if (moneyDetailsNotesRef) {
            this.state.notes += moneyDetailsNotesRef;
        }
        this.manualInputCashCountUSD = false;
        this.closeDetailsPopupUSD();
    },

    hasDifferenceUSD() {
        return Object.entries(this.state.payments_usd).find(pm => pm[1].difference != 0);
    },

    hasUserAuthorityUSD() {
        const absDifferences = Object.entries(this.state.payments_usd).map(pm => Math.abs(pm[1].difference));
        return this.props.is_manager || this.props.amount_authorized_diff_ref == null || Math.max(...absDifferences) <= this.props.amount_authorized_diff_ref;
    },

    //@override
    async closeSession() {
        if (!this.closeSessionClicked) {
            this.closeSessionClicked = true;
            if (this.props.cashControl) {
                const ref_id = this.props.default_cash_details.default_cash_details_ref.id;
                const response = await this.pos.data.call('pos.session', 'post_closing_cash_details_ref', [
                    [this.pos.session.id],
                    this.state.payments_usd[ref_id].counted,
                ]);
            }
            await this.pos.data.call('pos.session', 'update_closing_control_state_session_ref', [
                [this.pos.session.id],
                this.state.notes
            ]);
            this.closeSessionClicked = false;
        }
        return super.closeSession();
    }
});

// Update static parts
ClosePosPopup.components = { ...ClosePosPopup.components, MoneyDetailsPopupUSD };

// Redefine props to satisfy Owl 2 validation
const originalClosePosPopupProps = ClosePosPopup.props;
ClosePosPopup.props = [
    ...originalClosePosPopupProps,
    "other_payment_methods",
    "amount_authorized_diff_ref",
    "state",
    "cashControl",
];
