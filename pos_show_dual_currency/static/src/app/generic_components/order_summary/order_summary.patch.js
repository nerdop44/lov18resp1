/** @odoo-module */

import { OrderSummary } from "@point_of_sale/app/generic_components/order_summary/order_summary";
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";

patch(OrderSummary.prototype, {
    setup() {
        super.setup();
        this.pos = useService("pos");
    },

    get totalInRefCurrency() {
        if (!this.pos || !this.pos.config.show_dual_currency) {
            return null;
        }
        // OrderSummary receives 'total' or 'taxTotals' in props
        const total = this.props.total || 0;
        return this.pos.format_currency_ref(total * this.pos.config.show_currency_rate);
    }
});
