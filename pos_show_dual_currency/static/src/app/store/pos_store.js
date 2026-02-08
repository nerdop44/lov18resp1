/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { PosStore } from "@point_of_sale/app/store/pos_store";
import { PosData } from "@point_of_sale/app/models/data_service";
import { formatMonetary } from "@web/views/fields/formatters";

// Patch PosData to intercept the load_data result
patch(PosData.prototype, {
    async loadInitialData() {
        const response = await super.loadInitialData(...arguments);
        console.log(">>>>>>>> PosData Patched: loadInitialData Response Keys:", Object.keys(response));

        if (response && response["pos.session"]) {
            const session = response["pos.session"].data[0];
            if (session && session.res_currency_ref) {
                this.res_currency_ref = session.res_currency_ref;
                console.log(">>>>>>>> Intercepted res_currency_ref from RPC:", this.res_currency_ref);
            } else {
                console.warn(">>>>>>>> res_currency_ref NOT found in RPC response for pos.session", response["pos.session"]);
            }
        }
        return response;
    }
});

// Patch PosStore to use the intercepted data
patch(PosStore.prototype, {
    format_currency_ref(value) {
        const currency = this.res_currency_ref || {
            symbol: this.config.show_currency_symbol || "$",
            position: this.config.show_currency_position || "after",
            rounding: 0.01,
            decimal_places: 2,
        };

        // Ensure value is a number
        const amount = typeof value === 'number' ? value : parseFloat(value) || 0;

        let formatted = formatMonetary(amount, {
            currencyId: currency.id,
            currencySymbol: currency.symbol,
            currencyPosition: currency.position,
            rounding: currency.rounding,
            digits: [69, currency.decimal_places],
        });

        // Fallback: If formatMonetary returns just the number or fails to add symbol, force it
        if (!formatted.includes(currency.symbol)) {
            if (currency.position === 'before') {
                formatted = currency.symbol + ' ' + amount.toFixed(currency.decimal_places);
            } else {
                formatted = amount.toFixed(currency.decimal_places) + ' ' + currency.symbol;
            }
        }
        return formatted;
    },

    getProductPriceFormatted(product, ref = false) {
        // Get base price from pricelist (tax depends on pricelist setting)
        const price = product.get_price(this.pricelist, 1);

        // Calculate tax if needed (assuming we want tax-included for display if configured)
        const priceWithTax = this.get_product_price_with_tax(product, price);

        if (ref && this.config.show_dual_currency) {
            const rate = this.config.show_currency_rate || 1;
            if (rate === 0) return "";
            return this.format_currency_ref(priceWithTax / rate);
        }
        return this.formatCurrency(price);
    },

    get_product_price_with_tax(product, price) {
        var taxes = this.taxes_by_id[product.taxes_id] || [];
        // Odoo 18 Logic: compute_all might differ, but generally available in pos model
        // If not, we basic check
        if (!taxes || taxes.length === 0) return price;

        // Use standard compute_all if available
        // Note: compute_all is usually on 'pos' instance or imported
        // In Odoo 18 PosStore has get_taxes_after_fp

        var taxes_ids = this.get_taxes_after_fp(product.taxes_id, this.fiscal_position);
        var all_taxes = this.compute_all(taxes_ids, price, 1, this.currency.id);
        return all_taxes.total_included;
    },

    get show_currency_rate_display() {
        const rate = this.config.show_currency_rate || 0;
        return rate.toFixed(2);
    }
});
