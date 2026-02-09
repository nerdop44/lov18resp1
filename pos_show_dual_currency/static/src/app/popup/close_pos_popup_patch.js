/** @odoo-module */

import { ClosePosPopup } from "@point_of_sale/app/navbar/closing_popup/closing_popup";
import { patch } from "@web/core/utils/patch";

patch(ClosePosPopup, {
    props: {
        ...ClosePosPopup.props,
        other_payment_methods: { optional: true },
        amount_authorized_diff_ref: { optional: true },
    }
});
