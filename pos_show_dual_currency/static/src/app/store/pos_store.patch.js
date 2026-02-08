/** @odoo-module */

import { PosStore } from "@point_of_sale/app/store/pos_store";
import { patch } from "@web/core/utils/patch";

patch(PosStore.prototype, {
    async setup() {
        await super.setup(...arguments);
        console.log("PosStore Patch Setup: Dual Currency");
    },

    get currencyRef() {
        // Access data loaded via _load_pos_data_fields
        // In V18, loaded data is often available directly on the session or config
        return this.session.ref_me_currency_id;
    },

    format_currency_ref(amount) {
        const currency = this.currencyRef;
        if (!currency) {
            return "";
        }
        return this.env.utils.formatCurrency(amount, false, currency);
    },

    getProductPriceFormatted(product, ref = false) {
        const price = this.get_product_price(product);
        if (ref && this.config.show_dual_currency) {
            const rate = this.config.show_currency_rate || 1;
            // Avoid division by zero
            if (rate === 0) return "";
            return this.format_currency_ref(price / rate);
        }
        return this.env.utils.formatCurrency(price);
    }
});
