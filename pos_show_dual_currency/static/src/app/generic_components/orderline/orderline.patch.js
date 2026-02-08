/** @odoo-module */

import { Orderline } from "@point_of_sale/app/generic_components/orderline/orderline";
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";

patch(Orderline.prototype, {
    setup() {
        super.setup();
        this.pos = useService("pos");
    },

    get priceInRefCurrency() {
        const line = this.props.line;
        // Access config from the pos service
        if (!this.pos.config.show_dual_currency) {
            return null;
        }

        const price = line.get_display_price();
        const rate = this.pos.config.show_currency_rate || 1;

        if (rate === 0) return "";

        // Use the helper method on pos store if available, or format manually
        if (this.pos.format_currency_ref) {
            return this.pos.format_currency_ref(price / rate);
        }

        return (price / rate).toFixed(2);
    }
});
