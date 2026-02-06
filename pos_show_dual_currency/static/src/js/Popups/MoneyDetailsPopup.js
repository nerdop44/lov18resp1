/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { NumericInput } from "@point_of_sale/app/generic_components/inputs/numeric_input/numeric_input";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { parseFloat as _parseFloat } from "@web/views/fields/formatters";

export class MoneyDetailsPopupUSD extends Component {
    static template = "pos_show_dual_currency.MoneyDetailsPopupUSD";
    static components = { Dialog, NumericInput };
    static props = ["manualInputCashCountUSD", "onConfirm", "onDiscard"];

    setup() {
        this.pos = usePos();
        this._parseFloat = _parseFloat;
        this.state = useState({
            moneyDetailsRef: Object.fromEntries(this.pos.bills.map(bill => ([bill.value, 0]))),
            total_ref: 0,
        });
        if (this.props.manualInputCashCountUSD) {
            this.reset();
        }
    }

    updateMoneyDetailsAmountRef() {
        let total_ref = Object.entries(this.state.moneyDetailsRef).reduce(
            (total, [value, qty]) => total + value * qty, 0
        );
        this.state.total_ref = total_ref;
    }

    confirm() {
        let moneyDetailsNotesRef = this.state.total_ref ? 'Ref Currency Money details: \n' : null;
        this.pos.bills.forEach(bill => {
            if (this.state.moneyDetailsRef[bill.value]) {
                moneyDetailsNotesRef += `  - ${this.state.moneyDetailsRef[bill.value]} x ${this.pos.format_currency_ref(bill.value)}\n`;
            }
        });
        const payload = {
            total_ref: this.state.total_ref,
            moneyDetailsNotesRef,
            moneyDetailsRef: { ...this.state.moneyDetailsRef }
        };
        this.props.onConfirm(payload);
    }

    reset() {
        for (let key in this.state.moneyDetailsRef) {
            this.state.moneyDetailsRef[key] = 0;
        }
        this.state.total_ref = 0;
    }

    discard() {
        this.props.onDiscard();
    }
}
