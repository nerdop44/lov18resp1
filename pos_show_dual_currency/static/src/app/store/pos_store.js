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
        // Check if symbol is missing
        if (!formatted.includes(currency.symbol)) {
            if (currency.position === 'before') {
                formatted = currency.symbol + ' ' + amount.toFixed(currency.decimal_places);
            } else {
                formatted = amount.toFixed(currency.decimal_places) + ' ' + currency.symbol;
            }
        } else {
            // If symbol exists but position is wrong (e.g. Odoo formatted it as "100 $" but config says "before")
            // This is tricky because formatMonetary might have its own logic.
            // But let's trust formatMonetary unless it failed to add symbol.
            // However, user said "simbolo de $ debe salir antes del monto".
            // Let's force it if config says so and it's not seemingly right.
            if (currency.position === 'before' && !formatted.startsWith(currency.symbol)) {
                // It might be "100 $"
                formatted = currency.symbol + ' ' + amount.toFixed(currency.decimal_places);
            }
        }
        return formatted;
    },

    getProductPriceFormatted(product, ref = false) {
        // Use get_product_price_with_tax to include taxes if possible
        const price_with_tax = this.get_product_price_with_tax(product, product.get_price(this.pricelist, 1));

        if (ref && this.config.show_dual_currency) {
            const rate = this.config.show_currency_rate || 1;
            if (rate === 0) return "";
            // Use multiplication as now rate is Tasa (USD -> VEF = price * tasa)
            return this.format_currency_ref(price_with_tax * rate);
        }
        return this.formatCurrency(price_with_tax);
    },

    get_product_price_with_tax(product, price) {
        if (!product.taxes_id || product.taxes_id.length === 0) return price;

        // 1. Check if taxes_by_id generally exists (it might not in Odoo 18)
        // 2. product.taxes_id is an Array, don't use it as a key directly!

        let taxes = [];
        if (this.taxes_by_id) {
            taxes = product.taxes_id.map(id => this.taxes_by_id[id]).filter(Boolean);
        }

        // Fallback: search in this.taxes array if taxes_by_id missed or empty
        if (taxes.length === 0 && this.taxes) {
            taxes = this.taxes.filter(t => product.taxes_id.includes(t.id));
        }

        if (taxes.length === 0) {
            console.warn("PosStore: Taxes found/loaded for product?", product.id, taxes.length, "Total taxes loaded:", this.taxes ? this.taxes.length : 0);
            return price;
        }

        // Odoo 18 should have get_taxes_after_fp and compute_all
        try {
            var taxes_to_compute = taxes;

            // If get_taxes_after_fp exists, use it to map regular taxes to fiscal position
            if (typeof this.get_taxes_after_fp === 'function') {
                taxes_to_compute = this.get_taxes_after_fp(product.taxes_id, this.fiscal_position);
            }

            // Compute taxes
            // Use compute_all if available, otherwise just default to price for now to prevent crash
            if (typeof this.compute_all === 'function') {
                // compute_all(taxes, price, quantity, currency)
                // Note: taxes argument might expect IDs or Objects depending on version.
                // In Odoo 16/17 JS, it usually expects Objects or IDs.
                // Let's try passing the objects we found/filtered.
                var all_taxes = this.compute_all(taxes_to_compute, price, 1, this.currency.id);
                return all_taxes.total_included;
            } else {
                console.warn("PosStore.compute_all not found. Returning base price.");
            }
        } catch (error) {
            console.error("Error calculating tax for product:", product.id, error);
            // Fallback to base price
            return price;
        }

        return price;
    },

    get show_currency_rate_display() {
        const rate = this.config.show_currency_rate || 0;
        return rate.toFixed(2);
    }
});
