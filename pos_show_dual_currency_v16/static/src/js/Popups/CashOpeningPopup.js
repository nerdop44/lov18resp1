odoo.define('1010_pos_dual_currency.CashOpeningPopup', function (require) {
    'use strict';

    const CashOpeningPopup = require('point_of_sale.CashOpeningPopup');
    const Registries = require('point_of_sale.Registries');
    const { useState } = owl;



    const CashOpeningPopupUSD = (CashOpeningPopup) =>
          class extends CashOpeningPopup {
              setup() {
                    super.setup();
                    this.manualInputCashCountUSD = null;
                    this.state = useState({
                        openingCash: this.env.pos.pos_session.cash_register_balance_start || 0,
                        openingCashUSD: this.env.pos.pos_session.cash_register_balance_start_mn_ref || 0,
                        displayMoneyDetailsPopupUSD: false,
                    });
                }
              //@override
              async confirm() {
                    this.env.pos.pos_session.cash_register_balance_start_mn_ref = this.state.openingCashUSD;
                    this.rpc({
                           model: 'pos.session',
                            method: 'set_cashbox_pos_usd',
                            args: [this.env.pos.pos_session.id, this.state.openingCashUSD, this.state.notes_ref],
                    });
                    super.confirm();
                    }
              openDetailsPopupUSD() {
                    this.state.openingCashUSD = 0;
                    this.state.displayMoneyDetailsPopupUSD = true;
                    }
              closeDetailsPopupUSD() {
                    this.state.displayMoneyDetailsPopupUSD = false;
              }
              updateCashOpeningUSD({ total_ref, moneyDetailsNotesRef }) {
                    this.state.openingCashUSD = total_ref;
                    if (moneyDetailsNotesRef) {
                        this.state.notes += moneyDetailsNotesRef;
                    }
                    this.manualInputCashCountUSD = false;
                    this.closeDetailsPopupUSD();
            }
              handleInputChangeUSD() {
                    this.manualInputCashCountUSD = true;
                    if (typeof(this.state.openingCashUSD) !== "number") {
                        this.state.openingCashUSD = 0;
                    }
                    }
          };

    Registries.Component.extend(CashOpeningPopup, CashOpeningPopupUSD);

    return CashOpeningPopup;
});
