/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { PosStore } from "@point_of_sale/app/store/pos_store";
import { PosData } from "@point_of_sale/app/models/data_service";
// import { formatMonetary } from "@web/views/fields/formatters"; // Possible missing module in some asset bundles

// Patch PosData to intercept the load_data result
patch(PosData.prototype, {
    async loadInitialData() {
        const response = await super.loadInitialData(...arguments);
        console.log(">>>>>>>> PosData Patched: loadInitialData Response Keys:", Object.keys(response));

        if (response && response.res_currency_ref) {
            console.log(">>>>>>>> Intercepted res_currency_ref in PosData Root:", response.res_currency_ref);
        } else if (response && response["pos.session"]) {
            const sessionModel = response["pos.session"];
            const res_currency_ref = sessionModel.res_currency_ref || (sessionModel.data && sessionModel.data[0] ? sessionModel.data[0].res_currency_ref : null);
            if (res_currency_ref) {
                console.log(">>>>>>>> Intercepted res_currency_ref in PosData (Session lvl):", res_currency_ref);
            } else {
                console.warn(">>>>>>>> res_currency_ref NOT found in RPC response for pos.session", sessionModel);
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
            const sessionModel = this.models['pos.session'];
            if (sessionModel.res_currency_ref) return sessionModel.res_currency_ref;

            const sessionData = sessionModel.data || sessionModel;
            if (Array.isArray(sessionData) && sessionData.length > 0) {
                const sess = sessionData.find(s => s.id === this.session?.id) || sessionData[0];
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

        let formatted = "";
        try {
            // Manual formatting as fallback - explicit string conversion for safety
            const symbol = String(currency.symbol || "");
            const position = String(currency.position || "after");
            const decimals = parseInt(currency.decimal_places) || 2;

            formatted = (position === 'before' ? symbol + ' ' : '') +
                amount.toFixed(decimals).replace(/\./g, ",") +
                (position === 'after' ? ' ' + symbol : '');
        } catch (e) {
            console.warn("Manual formatting in format_currency_ref failed:", e);
            formatted = amount.toFixed(2);
        }

        return formatted;
    },

    getAmountInRefCurrency(amount) {
        if (!amount && amount !== 0) return "";
        let rate = 1.0;
        let active_currency_ref = this.res_currency_ref;

        // Reconstruct res_currency_ref from config if missing
        if (!active_currency_ref && this.config) {
            active_currency_ref = {
                symbol: this.config.show_currency_symbol || "$",
                position: this.config.show_currency_position || "after",
                rounding: 0.01,
                decimal_places: 2,
                rate: this.config.show_currency_rate || 1.0,
            };
        }

        if (active_currency_ref && active_currency_ref.rate) {
            rate = active_currency_ref.rate;
        } else {
            rate = this.config.show_currency_rate;
        }

        if (typeof rate !== 'number') {
            rate = parseFloat(rate);
        }
        if (isNaN(rate) || rate === 0) rate = 1;

        let final_val = 0;
        const ref_symbol = active_currency_ref ? active_currency_ref.symbol : (this.config.show_currency_symbol || '$');

        // NEW LOGIC (Pachacutec): Base is USD (list_price). 
        // 1. If we want USD (Reference), and input is USD, return direct.
        // 2. If we want Bs (Reference), multiply USD * Rate.

        if (ref_symbol === '$' || ref_symbol === 'USD') {
            // Base is USD, we want USD. No conversion needed.
            final_val = amount;
        } else {
            // Base is USD, we want Bs (Reference). Multiply.
            final_val = amount * rate;
        }

        return this.format_currency_ref(final_val);
    },

    getProductPriceFormatted(product, ref = false) {
        if (!product) return "";
        // Use get_product_price_with_tax to include taxes if possible
        let price = 0;
        try {
            price = product.get_price(this.pricelist, 1);
        } catch (e) {
            console.warn("Error getting product price:", e);
        }

        if (typeof price !== 'number') price = 0;

        const price_with_tax = this.get_product_price_with_tax(product, price);

        if (ref && (this.config?.show_dual_currency || this.res_currency_ref)) {
            // Use the new centralized helper
            return this.getAmountInRefCurrency(price_with_tax);
        }

        if (this.currency) {
            try {
                // NEW LOGIC (Pachacutec): If main currency is НЕ USD (e.g. VEF/Bs), 
                // we must multiply the price (USD) by the system rate.
                let rate = this.config.show_currency_rate || 1.0;
                if (typeof rate !== 'number') rate = parseFloat(rate) || 1.0;

                const ref_symbol = this.res_currency_ref ? this.res_currency_ref.symbol : (this.config.show_currency_symbol || '$');

                // If main currency is e.g. Bs, and Reference is USD, or if main is just not USD.
                // We assume main currency here is the one needing conversion from USD base.
                let display_amount = price_with_tax;
                if (this.currency.name !== 'USD' && this.currency.symbol !== '$') {
                    display_amount = price_with_tax * rate;
                }

                // Fix: Ensure we extract the symbol as string, not the JS primitive Symbol type
                const curr_sym = typeof this.currency.symbol === 'symbol' ? '' : (this.currency.symbol || '');
                return (this.currency.position === 'before' ? curr_sym + ' ' : '') +
                    display_amount.toFixed(this.currency.decimal_places).replace(/\./g, ",") +
                    (this.currency.position === 'after' ? ' ' + curr_sym : '');
            } catch (e) {
                console.warn("Formatting failed for main currency:", e);
                return price_with_tax.toFixed(2);
            }
        }
        return "" + price_with_tax.toFixed(2);
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
        return rate.toFixed(4);
    }
});
