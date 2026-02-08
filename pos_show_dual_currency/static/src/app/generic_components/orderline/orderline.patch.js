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
        if (!this.pos.config.show_dual_currency) {
            return null;
        }
        const rate = this.pos.config.show_currency_rate || 1;
        // In generic orderline, the price is passed in props
        const price = parseFloat(this.props.line.price.replace(/[^0-9.-]+/g, "")) || 0;
        return this.pos.format_currency_ref(price * rate);
    }
});
