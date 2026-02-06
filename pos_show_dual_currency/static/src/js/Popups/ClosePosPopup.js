odoo.define('1010_pos_dual_currency.ClosePosPopup', function (require) {
    'use strict';

    const ClosePosPopup = require('point_of_sale.ClosePosPopup');
    const Registries = require('point_of_sale.Registries');
    const { identifyError } = require('point_of_sale.utils');
    const { ConnectionLostError, ConnectionAbortedError } = require('@web/core/network/rpc_service')
    const { useState } = owl;

    const ClosePosPopupUSD = (ClosePosPopup) => {
        class classUSD extends ClosePosPopup {
            setup() {
                super.setup();
                this.manualInputCashCountUSD = false;
                this.state = useState({
                    displayMoneyDetailsPopupUSD: false,
                    ...(this.props.state || {}),
                });
            }

            //@override
            async confirm() {
                if (!this.props.cashControl || !this.hasDifferenceUSD()) {
                    super.confirm();
                } else if (this.hasUserAuthorityUSD()) {
                    const { confirmed } = await this.showPopup('ConfirmPopup', {
                        title: this.env._t('Currency Ref Payments Difference'),
                        body: this.env._t('Do you want to accept currency ref payments difference and post a profit/loss journal entry?'),
                    });
                    if (confirmed) {
                        super.confirm();
                    }
                } else {
                    await this.showPopup('ConfirmPopup', {
                        title: this.env._t('Currency Ref Payments Difference'),
                        body: _.str.sprintf(
                            this.env._t('The maximum difference by currency ref allowed is %s.\n\
                            Please contact your manager to accept the closing difference.'),
                            this.env.pos.format_currency_ref(this.props.amount_authorized_diff_ref)
                        ),
                        confirmText: this.env._t('OK'),
                    })
                }
            }
            openDetailsPopupUSD() {
                this.state.payments_usd[this.props.default_cash_details.default_cash_details_ref.id].counted = 0;
                this.state.payments_usd[this.props.default_cash_details.default_cash_details_ref.id].difference = -this.props.default_cash_details.default_cash_details_ref.amount;
                this.state.displayMoneyDetailsPopupUSD = true;
            }
            closeDetailsPopupUSD() {
                this.state.displayMoneyDetailsPopupUSD = false;
            }

            handleInputChangeUSD(paymentId) {
                let expectedAmount;
                if (paymentId === this.props.default_cash_details.default_cash_details_ref.id) {
                    this.manualInputCashCountUSD = true;
                    expectedAmount = this.props.default_cash_details.default_cash_details_ref.amount;
                } else {
                    expectedAmount = this.props.other_payment_methods.find(pm => paymentId === pm.id).amount;
                }
                this.state.payments_usd[paymentId].difference =
                    this.env.pos.round_decimals_currency(this.state.payments_usd[paymentId].counted - expectedAmount);
            }

            updateCountedCashUSD({ total_ref, moneyDetailsNotesRef }) {
                const ref_id = this.props.default_cash_details.default_cash_details_ref.id;
                this.state.payments_usd[ref_id].counted = total_ref;
                this.state.payments_usd[ref_id].difference =
                    this.env.pos.round_decimals_currency(this.state.payments_usd[ref_id].counted - this.props.default_cash_details.default_cash_details_ref.amount);
                if (moneyDetailsNotesRef) {
                    this.state.notes += moneyDetailsNotesRef;
                }
                this.manualInputCashCountUSD = false;
                this.closeDetailsPopupUSD();
            }

            hasDifferenceUSD() {
                return Object.entries(this.state.payments_usd).find(pm => pm[1].difference != 0);
            }
            hasUserAuthorityUSD() {
                const absDifferences = Object.entries(this.state.payments_usd).map(pm => Math.abs(pm[1].difference));
                return this.props.is_manager || this.props.amount_authorized_diff_ref == null || Math.max(...absDifferences) <= this.props.amount_authorized_diff_ref;
            }

            async closeSession() {
                if (!this.closeSessionClicked) {
                    this.closeSessionClicked = true;
                    let response;
                    if (this.props.cashControl) {
                        response = await this.rpc({
                            model: 'pos.session',
                            method: 'post_closing_cash_details_ref',
                            args: [this.env.pos.pos_session.id],
                            kwargs: {
                                counted_cash: this.state.payments_usd[this.props.default_cash_details.default_cash_details_ref.id].counted,
                            }
                        })
                        if (!response.successful) {
                            return super.handleClosingError(response);
                        }
                    }
                    await this.rpc({
                        model: 'pos.session',
                        method: 'update_closing_control_state_session_ref',
                        args: [this.env.pos.pos_session.id, this.state.notes]
                    })
                    this.closeSessionClicked = false;
                }
                super.closeSession();
            }
        }
        classUSD.props = [
            ...ClosePosPopup.props,
            "other_payment_methods",
            "amount_authorized_diff_ref",
            "state",
            "cashControl",
        ];
        return classUSD;
    };

    Registries.Component.extend(ClosePosPopup, ClosePosPopupUSD);

    return ClosePosPopup;
});
