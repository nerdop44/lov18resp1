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
        // Price with tax included is typically what we want for display on the line total or unit price depending on context
        // Orderline props.line is a generic object in generic_components ?? 
        // Wait, Orderline in generic_components takes 'line' prop which is a Json object or similar, 
        // BUT in the main screen it might be the model. 
        // Actually Orderline in generic_components is for the widget, not the main screen line?
        // Let's verify what 'line' is. 
        // In OrderWidget, it passes `line`, which is `currentOrder.get_orderlines()`. 
        // So `line` is an instance of Orderline model.

        const line = this.props.line;
        const price = line.get_display_price(); // This includes tax if configured
        const rate = this.pos.config.show_currency_rate || 1;

        if (rate === 0) return "";
        return this.pos.format_currency_ref(price / rate);
    }
});
