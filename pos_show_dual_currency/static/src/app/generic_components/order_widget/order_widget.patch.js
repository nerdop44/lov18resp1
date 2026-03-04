/** @odoo-module */

import { OrderWidget } from "@point_of_sale/app/generic_components/order_widget/order_widget";
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";

patch(OrderWidget.prototype, {
    setup() {
        if (super.setup) {
            super.setup();
        }
        try {
            this.pos = useService("pos");
        } catch (e) {
            console.error("Failed to load 'pos' service in OrderWidget:", e);
        }
    },

    get totalInRefCurrency() {
        if (!this.pos || !this.pos.config.show_dual_currency || !this.props.taxTotals) {
            return null;
        }
        const total = this.props.taxTotals.order_total || 0;
        const sign = this.props.taxTotals.order_sign || 1;
        // Calculate total with sign
        const amount = total * sign;
        return this.pos.getAmountInRefCurrency(amount);
    }
});
