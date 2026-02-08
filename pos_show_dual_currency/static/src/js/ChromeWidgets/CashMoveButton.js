odoo.define('pos_show_dual_currency.CashMoveButtonRefCurrency', function (require) {
    'use strict';

    const PosComponent = require('point_of_sale.PosComponent');
    const Registries = require('point_of_sale.Registries');
    const { _t } = require('web.core');
    const { renderToString } = require('@web/core/utils/render');

    const TRANSLATED_CASH_MOVE_TYPE = {
        in: _t('in'),
        out: _t('out'),
    };

    class CashMoveButtonRefCurrency extends PosComponent {
        async onClickUSD() {
            const { confirmed, payload } = await this.showPopup('CashMovePopupRefCurrency');
            if (!confirmed) return;
            const { type, amount, reason, currency_ref } = payload;
            const translatedType = TRANSLATED_CASH_MOVE_TYPE[type];
            const formattedAmount = this.env.pos.format_currency_ref(amount);
            if (!amount) {
                return this.showNotification(
                    _.str.sprintf(this.env._t('Cash in/out of %s is ignored.'), formattedAmount),
                    3000
                );
            }
            const extras = { formattedAmount, translatedType };
            await this.rpc({
                model: 'pos.session',
                method: 'try_cash_in_out_ref_currency',
                args: [[this.env.pos.pos_session.id], type, amount, reason, extras, currency_ref],
            });
            this.showNotification(
                _.str.sprintf(this.env._t('Successfully made a cash %s of %s.'), type, formattedAmount),
                3000
            );
        }

    }
    CashMoveButtonRefCurrency.template = 'CashMoveButtonRefCurrency';

    Registries.Component.add(CashMoveButtonRefCurrency);

    return CashMoveButtonRefCurrency;
});
