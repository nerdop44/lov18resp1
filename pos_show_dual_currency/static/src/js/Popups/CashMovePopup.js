/** @odoo-module **/

import { AbstractAwaitablePopup } from "@point_of_sale/app/utils/abstract_awaitable_popup/abstract_awaitable_popup";
import { Dialog } from "@web/core/dialog/dialog";
import { _t } from "@web/core/l10n/translation";
import { parseFloat as _parseFloat } from "@web/views/fields/formatters";
import { useRef, useState } from "@odoo/owl";
import { usePos } from "@point_of_sale/app/store/pos_hook";

export class CashMovePopupRefCurrency extends AbstractAwaitablePopup {
    static template = "pos_show_dual_currency.CashMovePopupRefCurrency";
    static components = { Dialog };
    static props = {
        ...AbstractAwaitablePopup.props,
        cancelText: { type: String, optional: true },
        title: { type: String, optional: true },
    };
    static defaultProps = {
        cancelText: _t('Cancel'),
        title: _t('Cash In/Out (Ref)'),
    };

    setup() {
        super.setup();
        this.pos = usePos();
        this.state = useState({
            inputType: '', // '' | 'in' | 'out'
            inputAmount: '',
            inputReason: '',
            inputHasError: false,
        });
        this.inputAmountRef = useRef('input-amount-ref');
    }

    confirm() {
        let amount;
        try {
            amount = _parseFloat(this.state.inputAmount);
        } catch (_error) {
            this.state.inputHasError = true;
            this.errorMessage = _t('Invalid amount');
            return;
        }
        if (this.state.inputType == '') {
            this.state.inputHasError = true;
            this.errorMessage = _t('Select either Cash In or Cash Out before confirming.');
            return;
        }
        if (this.state.inputType === 'out' && amount > 0) {
            this.state.inputHasError = true;
            this.errorMessage = _t('Insert a negative amount with the Cash Out option.');
            return;
        }
        if (this.state.inputType === 'in' && amount < 0) {
            this.state.inputHasError = true;
            this.errorMessage = _t('Insert a positive amount with the Cash In option.');
            return;
        }
        if (amount < 0) {
            this.state.inputAmount = this.state.inputAmount.substring(1);
        }
        return super.confirm();
    }

    _onAmountKeypress(event) {
        if (event.key === '-') {
            event.preventDefault();
            this.state.inputAmount = this.state.inputType === 'out' ? this.state.inputAmount.substring(1) : `-${this.state.inputAmount}`;
            this.state.inputType = this.state.inputType === 'out' ? 'in' : 'out';
        }
    }

    onClickButton(type) {
        let amount = this.state.inputAmount;
        if (type === 'in') {
            this.state.inputAmount = amount.charAt(0) === '-' ? amount.substring(1) : amount;
        } else {
            this.state.inputAmount = amount.charAt(0) === '-' ? amount : `-${amount}`;
        }
        this.state.inputType = type;
        this.state.inputHasError = false;
        this.inputAmountRef.el && this.inputAmountRef.el.focus();
    }

    getPayload() {
        return {
            amount: _parseFloat(this.state.inputAmount),
            reason: this.state.inputReason.trim(),
            type: this.state.inputType,
            currency_ref: this.pos.res_currency_ref,
        };
    }
}
