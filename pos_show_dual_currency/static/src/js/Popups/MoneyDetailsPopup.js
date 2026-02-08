odoo.define('1010_pos_dual_currency.MoneyDetailsPopupUSD', function(require) {
    'use strict';

    const PosComponent = require('point_of_sale.PosComponent');
    const Registries = require('point_of_sale.Registries');

    const { useState } = owl;

    /**
     * Even if this component has a "confirm and cancel"-like buttons, this should not be an AbstractAwaitablePopup.
     * We currently cannot show two popups at the same time, what we do is mount this component with its parent
     * and hide it with some css. The confirm button will just trigger an event to the parent.
     */
    class MoneyDetailsPopupUSD extends PosComponent {
        setup() {
            super.setup();
            this.currency_ref = this.env.pos.res_currency_ref;
            this.state = useState({
                moneyDetailsRef: Object.fromEntries(this.env.pos.bills.map(bill => ([bill.value, 0]))),
                total_ref: 0,
            });
            if (this.props.manualInputCashCountUSD) {
                this.reset();
            }
        }
        get firstHalfMoneyDetailsRef() {
            const moneyDetailsKeysRef = Object.keys(this.state.moneyDetailsRef).sort((a, b) => a - b);
            return moneyDetailsKeysRef.slice(0, Math.ceil(moneyDetailsKeysRef.length/2));
        }
        get lastHalfMoneyDetailsRef() {
            const moneyDetailsKeysRef = Object.keys(this.state.moneyDetailsRef).sort((a, b) => a - b);
            return moneyDetailsKeysRef.slice(Math.ceil(moneyDetailsKeysRef.length/2), moneyDetailsKeysRef.length);
        }
        updateMoneyDetailsAmountRef() {
            let total_ref = Object.entries(this.state.moneyDetailsRef).reduce((total_ref, money_ref) => total_ref + money_ref[0] * money_ref[1], 0);
            this.state.total_ref = this.env.pos.round_decimals_currency(total_ref);
        }
        confirm() {
            let moneyDetailsNotesRef = this.state.total_ref  ? 'Ref Currency Money details: \n' : null;
            this.env.pos.bills.forEach(bill => {
                if (this.state.moneyDetailsRef[bill.value]) {
                    moneyDetailsNotesRef += `  - ${this.state.moneyDetailsRef[bill.value]} x ${this.env.pos.format_currency_ref(bill.value)}\n`;
                }
            })
            const payload = { total_ref: this.state.total_ref, moneyDetailsNotesRef, moneyDetailsRef: { ...this.state.moneyDetailsRef } };
            this.props.onConfirm(payload);
        }
        reset() {
            for (let key in this.state.moneyDetailsRef) { this.state.moneyDetailsRef[key] = 0 }
            this.state.total_ref = 0;
        }
        discard() {
            this.reset();
            this.props.onDiscard();
        }
    }

    MoneyDetailsPopupUSD.template = 'MoneyDetailsPopupUSD';
    Registries.Component.add(MoneyDetailsPopupUSD);

    return MoneyDetailsPopupUSD;

});
