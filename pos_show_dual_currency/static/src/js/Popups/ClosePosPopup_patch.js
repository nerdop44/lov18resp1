odoo.define('1010_pos_dual_currency.ClosePosPopupFix', function (require) {
    'use strict';

    const { ClosePosPopup } = require('point_of_sale.ClosePosPopup');
    const { patch } = require('@web/core/utils/patch');

    patch(ClosePosPopup.prototype, {
        setup() {
            super.setup();
            this.manualInputCashCountUSD = false;
            // Use this.props directly or state
            if (this.props.state) {
                Object.assign(this.state, this.props.state);
            }
        },
        // We added other methods via the previous extend, 
        // but if that extend didn't work, we should move them here.
    });

    // Directly modify the static props to allow the new keys
    if (!ClosePosPopup.props.includes("other_payment_methods")) {
        ClosePosPopup.props.push("other_payment_methods");
    }
    if (!ClosePosPopup.props.includes("amount_authorized_diff_ref")) {
        ClosePosPopup.props.push("amount_authorized_diff_ref");
    }
    if (!ClosePosPopup.props.includes("state")) {
        ClosePosPopup.props.push("state");
    }
    if (!ClosePosPopup.props.includes("cashControl")) {
        ClosePosPopup.props.push("cashControl");
    }
});
