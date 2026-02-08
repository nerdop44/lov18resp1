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
        // Wait, Orderline in generic_components is for the widget, not the main screen line?
        // Actually Orderline in generic_components is for the widget, not the main screen line?
        // Let's verify what 'line' is. 
        // In OrderWidget, it passes `line`, which is `currentOrder.get_orderlines()`. 
        // So `line` is an instance of Orderline model.

        const line = this.props.line;
        let price = 0;

        // Try to get the unit price with tax included
        // In Odoo 18/17, get_unit_display_price() usually returns tax-included price if configured
        if (typeof line.get_unit_display_price === 'function') {
            price = line.get_unit_display_price();
        } else if (typeof line.get_display_price === 'function') {
            price = line.get_display_price();
        } else {
            // Fallback: Manually calculate if object properties exist
            // check for price_subtotal_incl and quantity
            if (line.get_price_with_tax) {
                price = line.get_price_with_tax();
            } else if (line.get_taxed_price) {
                price = line.get_taxed_price();
            } else {
                // Fallback to basic price, but this might be without tax
                price = line.get_unit_price ? line.get_unit_price() : (line.price || 0);
            }
        }

        // If price is 0, maybe try get_all_prices if available
        if (price === 0 && typeof line.get_all_prices === 'function') {
            const allPrices = line.get_all_prices();
            price = allPrices.priceWithTax || allPrices.unitPrice || 0;
        }

        const rate = this.pos.config.show_currency_rate || 1;

        if (!rate || rate === 0) return "";

        const priceInRef = price / rate;
        if (isNaN(priceInRef)) return "";

        return this.pos.format_currency_ref(priceInRef);
    }
});
