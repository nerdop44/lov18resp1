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
        return formatMonetary(value, {
            currencyId: currency.id,
            currencySymbol: currency.symbol,
            currencyPosition: currency.position,
            rounding: currency.rounding,
            digits: [69, currency.decimal_places],
        });
    },

    getProductPriceFormatted(product, ref = false) {
        const price = product.get_price(this.pricelist, 1);
        if (ref && this.config.show_dual_currency) {
            const rate = this.config.show_currency_rate || 1;
            if (rate === 0) return "";
            // Use the rate directly as it is now the "Tasa" (Price / Tasa)
            return this.format_currency_ref(price / rate);
        }
        return this.formatCurrency(price);
    },

    get show_currency_rate_display() {
        const rate = this.config.show_currency_rate || 0;
        return rate.toFixed(2);
    }
});
