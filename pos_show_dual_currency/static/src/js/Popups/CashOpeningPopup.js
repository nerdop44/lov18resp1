/** @odoo-module **/

import { OpeningControlPopup } from "@point_of_sale/app/store/opening_control_popup/opening_control_popup";
import { patch } from "@web/core/utils/patch";
import { usePos } from "@point_of_sale/app/store/pos_hook";

patch(OpeningControlPopup.prototype, {
      setup() {
            super.setup();
            this.pos = usePos();
            this.manualInputCashCountUSD = false;
            Object.assign(this.state, {
                  openingCashUSD: this.pos.pos_session.cash_register_balance_start_mn_ref || 0,
                  displayMoneyDetailsPopupUSD: false,
            });
      },

      //@override
      async confirm() {
            this.pos.pos_session.cash_register_balance_start_mn_ref = this.state.openingCashUSD;
            await this.pos.data.call('pos.session', 'set_cashbox_pos_usd', [
                  [this.pos.pos_session.id],
                  this.state.openingCashUSD,
                  this.state.notes || '',
            ]);
            return super.confirm();
      },

      openDetailsPopupUSD() {
            this.state.openingCashUSD = 0;
            this.state.displayMoneyDetailsPopupUSD = true;
      },

      closeDetailsPopupUSD() {
            this.state.displayMoneyDetailsPopupUSD = false;
      },

      updateCashOpeningUSD({ total_ref, moneyDetailsNotesRef }) {
            this.state.openingCashUSD = total_ref;
            if (moneyDetailsNotesRef) {
                  this.state.notes = (this.state.notes || '') + moneyDetailsNotesRef;
            }
            this.manualInputCashCountUSD = false;
            this.closeDetailsPopupUSD();
      },

      handleInputChangeUSD() {
            this.manualInputCashCountUSD = true;
      }
});
