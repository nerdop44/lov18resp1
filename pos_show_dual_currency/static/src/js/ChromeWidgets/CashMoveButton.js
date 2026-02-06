/** @odoo-module **/

import { Component } from "@odoo/owl";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";
import { CashMovePopupRefCurrency } from "../Popups/CashMovePopup";

const TRANSLATED_CASH_MOVE_TYPE = {
    in: _t('in'),
    out: _t('out'),
};

export class CashMoveButtonRefCurrency extends Component {
    static template = "pos_show_dual_currency.CashMoveButtonRefCurrency";

    setup() {
        this.pos = usePos();
        this.popup = useService("popup");
        this.notification = useService("notification");
    }

    async onClickUSD() {
        const { confirmed, payload } = await this.popup.add(CashMovePopupRefCurrency);
        if (!confirmed) return;

        const { type, amount, reason, currency_ref } = payload;
        const translatedType = TRANSLATED_CASH_MOVE_TYPE[type];
        const formattedAmount = this.pos.format_currency_ref(amount);

        if (!amount) {
            this.notification.add(
                _.str.sprintf(_t('Cash in/out of %s is ignored.'), formattedAmount),
                { type: "warning" }
            );
            return;
        }

        const extras = { formattedAmount, translatedType };
        await this.pos.data.call('pos.session', 'try_cash_in_out_ref_currency', [
            [this.pos.session.id],
            type,
            amount,
            reason,
            extras,
            currency_ref
        ]);

        this.notification.add(
            _.str.sprintf(_t('Successfully made a cash %s of %s.'), type, formattedAmount),
            { type: "success" }
        );
    }
}
