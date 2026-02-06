/** @odoo-module **/

import { PosStore } from "@point_of_sale/app/store/pos_store";
import { patch } from "@web/core/utils/patch";

patch(PosStore.prototype, {
    async setup() {
        await super.setup(...arguments);
        this.res_currency_ref = this.data.get("res_currency_ref") || null;
    },

    format_currency_ref(amount) {
        if (!this.res_currency_ref) {
            return "";
        }
        const formattedAmount = this.env.utils.formatCurrency(amount, false, this.res_currency_ref);
        return formattedAmount;
    },

    getProductPriceFormatted(product, ref = false) {
        const price = this.getProductPrice(product);
        if (ref && this.config.show_dual_currency) {
            const rate = this.config.show_currency_rate || 1;
            return this.format_currency_ref(price / rate);
        }
        const formattedUnitPrice = this.env.utils.formatCurrency(price);
        if (product.to_weight) {
            return `${formattedUnitPrice}/${product.uom_id.name}`;
        } else {
            return formattedUnitPrice;
        }
    },

    async getClosePosInfo() {
        const info = await super.getClosePosInfo();
        // Ensure keys from session are passed to popup props
        return {
            ...info,
            other_payment_methods: info.other_payment_methods || [],
            amount_authorized_diff_ref: info.amount_authorized_diff_ref,
        };
    }
});
