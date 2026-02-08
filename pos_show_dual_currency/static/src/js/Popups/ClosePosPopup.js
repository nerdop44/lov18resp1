odoo.define('1010_pos_dual_currency.ClosePosPopup', function(require) {
    'use strict';

    const ClosePosPopup = require('point_of_sale.ClosePosPopup');
    const Registries = require('point_of_sale.Registries');
    const { identifyError } = require('point_of_sale.utils');
    const { ConnectionLostError, ConnectionAbortedError} = require('@web/core/network/rpc_service')
    const { useState } = owl;

    const ClosePosPopupUSD = (ClosePosPopup) =>
            class extends ClosePosPopup {
                setup() {
                    super.setup();
                    this.manualInputCashCountUSD = false;
                    Object.assign(this, this.props.info);
                    this.state = useState({
                        displayMoneyDetailsPopupUSD: false,
                    });

                    Object.assign(this.state, this.props.info.state);
                    }

                //@override
                async confirm() {
                    if (!this.cashControl || !this.hasDifferenceUSD()) {
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
                            this.env.pos.format_currency_ref(this.amountAuthorizedDiffUSD)
                        ),
                        confirmText: this.env._t('OK'),
                    })
                }
                }
                openDetailsPopupUSD() {

                    this.state.payments_usd[this.defaultCashDetails.default_cash_details_ref.id].counted = 0;
                    this.state.payments_usd[this.defaultCashDetails.default_cash_details_ref.id].difference = -this.defaultCashDetails.default_cash_details_ref.amount;

                    this.state.displayMoneyDetailsPopupUSD = true;
                }
                closeDetailsPopupUSD() {
                    this.state.displayMoneyDetailsPopupUSD = false;
                 }

                handleInputChangeUSD(paymentId) {

                    let expectedAmount;
                    if (paymentId === this.defaultCashDetails.default_cash_details_ref.id) {
                        this.manualInputCashCountUSD = true;
                        expectedAmount = this.defaultCashDetails.default_cash_details_ref.amount;
                    } else {
                        expectedAmount = this.otherPaymentMethods.find(pm => paymentId === pm.id).amount;
                    }
                    this.state.payments_usd[paymentId].difference =
                        this.env.pos.round_decimals_currency(this.state.payments_usd[paymentId].counted - expectedAmount);
                }

                updateCountedCashUSD({ total_ref, moneyDetailsNotesRef}) {
                    this.state.payments_usd[this.defaultCashDetails.default_cash_details_ref.id].counted = total_ref;
                    this.state.payments_usd[this.defaultCashDetails.default_cash_details_ref.id].difference =
                        this.env.pos.round_decimals_currency(this.state.payments_usd[[this.defaultCashDetails.default_cash_details_ref.id]].counted - this.defaultCashDetails.default_cash_details_ref.amount);
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
                    return this.isManager || this.amountAuthorizedDiffUSD == null || Math.max(...absDifferences) <= this.amountAuthorizedDiffUSD;
                }

                async closeSession() {
                    if (!this.closeSessionClicked) {
                        this.closeSessionClicked = true;
                        let response;
                        if (this.cashControl) {
                            response = await this.rpc({
                                model: 'pos.session',
                                method: 'post_closing_cash_details_ref',
                                args: [this.env.pos.pos_session.id],
                                kwargs: {
                                counted_cash: this.state.payments_usd[this.defaultCashDetails.default_cash_details_ref.id].counted,
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



    };

    Registries.Component.extend(ClosePosPopup, ClosePosPopupUSD);

    return ClosePosPopup;
});
