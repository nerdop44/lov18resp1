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
                // Save to the PosData instance
                this.res_currency_ref = session.res_currency_ref;
                // ALSO try to attach it to the session object itself for easier access if it's consumed later
                // session.res_currency_ref is already there
                console.log(">>>>>>>> Intercepted res_currency_ref in PosData:", this.res_currency_ref);
            } else {
                console.warn(">>>>>>>> res_currency_ref NOT found in RPC response for pos.session", response["pos.session"]);
            }
        }

        if (response['account.tax']) {
            console.log(">>>>>>>> Account Taxes loaded in RPC:", response['account.tax'].data ? response['account.tax'].data.length : 'N/A');
        } else {
            console.warn(">>>>>>>> Account Taxes MISSING in RPC response");
        }

        return response;
    }
});

// Patch PosStore to use the intercepted data
patch(PosStore.prototype, {
    get res_currency_ref() {
        return this.get_currency_ref();
    },

    get_currency_ref() {
        // 1. Try accessing from PosData if available (this.data is commonly the data service in Odoo 18 PosStore)
        if (this.data && this.data.res_currency_ref) {
            return this.data.res_currency_ref;
        }

        // 2. Try accessing from this.session (if loaded as a property)
        if (this.session && this.session.res_currency_ref) {
            return this.session.res_currency_ref;
        }

        // 3. Try finding it in the loaded models if they are accessible
        if (this.models && this.models['pos.session']) {
            // It might be a collection or array
            const sessionData = this.models['pos.session'].data || this.models['pos.session'];
            if (Array.isArray(sessionData) && sessionData.length > 0) {
                const sess = sessionData.find(s => s.id === this.session.id) || sessionData[0];
                if (sess && sess.res_currency_ref) return sess.res_currency_ref;
            }
        }

        return null;
    },

    format_currency_ref(value) {
        const currency = this.get_currency_ref() || {
            symbol: this.config.show_currency_symbol || "$",
            position: this.config.show_currency_position || "after",
            rounding: 0.01,
            decimal_places: 2,
            id: 999999 // Fallback ID
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
        } else {
            // Correct usage of symbol position if formatMonetary didn't respect it (e.g. locale overrides)
            if (currency.position === 'before' && !formatted.startsWith(currency.symbol)) {
                // heuristic check: if it ends with symbol but should start
                if (formatted.endsWith(currency.symbol)) {
                    formatted = currency.symbol + ' ' + formatted.slice(0, -currency.symbol.length).trim();
                } else {
                    formatted = currency.symbol + ' ' + amount.toFixed(currency.decimal_places);
                }
            }
        }
        return formatted;
    },

    getAmountInRefCurrency(amount) {
        if (!amount && amount !== 0) return "";
        let rate = 1.0;
        if (this.res_currency_ref && this.res_currency_ref.rate) {
            rate = this.res_currency_ref.rate;
        } else {
            rate = this.config.show_currency_rate;
        }

        if (typeof rate !== 'number') {
            rate = parseFloat(rate);
        }
        if (isNaN(rate) || rate === 0) rate = 1;

        const final_val = amount * rate;
        return this.format_currency_ref(final_val);
    },

    getProductPriceFormatted(product, ref = false) {
        // Use get_product_price_with_tax to include taxes if possible
        let price = product.get_price(this.pricelist, 1);
        if (typeof price !== 'number') price = 0;

        const price_with_tax = this.get_product_price_with_tax(product, price);

        if (ref && (this.config.show_dual_currency || this.res_currency_ref)) {
            // Use the new centralized helper
            return this.getAmountInRefCurrency(price_with_tax);
        }
        if (this.currency) {
            return formatMonetary(price_with_tax, {
                currencyId: this.currency.id,
                currencySymbol: this.currency.symbol,
                currencyPosition: this.currency.position,
                rounding: this.currency.rounding,
                digits: [69, this.currency.decimal_places],
            });
        }
        return "" + price_with_tax;
    },

    get_product_price_with_tax(product, price) {
        if (!product.taxes_id || product.taxes_id.length === 0) return price;

        let taxes = [];
        // 1. Try checking this.taxes (Odoo 16/17 style)
        if (this.taxes) {
            taxes = this.taxes.filter(t => product.taxes_id.includes(t.id));
        } else if (this.taxes_by_id) {
            taxes = product.taxes_id.map(id => this.taxes_by_id[id]).filter(Boolean);
        }

        // 2. Try checking Odoo 18 models service style
        if (taxes.length === 0 && this.models && this.models['account.tax']) {
            try {
                // If it's a DataStore collection
                const taxModel = this.models['account.tax'];
                if (typeof taxModel.getAll === 'function') {
                    taxes = taxModel.getAll().filter(t => product.taxes_id.includes(t.id));
                } else if (Array.isArray(taxModel)) {
                    taxes = taxModel.filter(t => product.taxes_id.includes(t.id));
                } else if (taxModel.data) {
                    taxes = taxModel.data.filter(t => product.taxes_id.includes(t.id));
                }
            } catch (e) { console.error("Error accessing models['account.tax']", e); }
        }

        if (taxes.length === 0) return price;

        try {
            // Compute taxes
            // Logic adapted for Odoo 18/Owl where compute_all might be a utility
            // or we use a simplified calculation for display if compute_all is missing

            if (typeof this.compute_all === 'function') {
                // compute_all(taxes, price, quantity, currency)
                var all_taxes = this.compute_all(taxes, price, 1, this.currency.id);
                return all_taxes.total_included;
            } else if (this.get_taxes_after_fp) {
                // Fallback if compute_all is missing logic (unlikely in POS)
                return price;
            }
        } catch (error) {
            console.error("Error calculating tax:", error);
            return price;
        }
        return price;
    },

    get show_currency_rate_display() {
        const rate = this.config.show_currency_rate || 0;
        return rate.toFixed(2);
    }
});
