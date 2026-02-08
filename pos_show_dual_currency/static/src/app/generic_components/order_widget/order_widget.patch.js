/** @odoo-module */

import { OrderWidget } from "@point_of_sale/app/generic_components/order_widget/order_widget";
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";

patch(OrderWidget.prototype, {
    setup() {
        super.setup();
        this.pos = useService("pos");
    },

    get totalInRefCurrency() {
        if (!this.pos || !this.pos.config.show_dual_currency) {
            return null;
        }
        const total = this.props.taxTotals?.order_total || this.props.total || 0;
        return this.pos.format_currency_ref(total * this.pos.config.show_currency_rate);
    }
});
