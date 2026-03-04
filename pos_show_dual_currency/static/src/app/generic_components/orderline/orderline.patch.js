/** @odoo-module */

import { Orderline } from "@point_of_sale/app/generic_components/orderline/orderline";
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";

patch(Orderline.prototype, {
    setup() {
        if (super.setup) {
            super.setup();
        }
        try {
            this.pos = useService("pos");
        } catch (e) {
            console.error("Failed to load 'pos' service in Orderline:", e);
        }
    },

    get priceInRefCurrency() {
        const line = this.props.line;

        // Helper to safely parse localized numbers (expecting 1.000,00 format for VE/ES)
        const parseValue = (val) => {
            if (typeof val === 'number') return val;
            if (!val) return 0;
            // Remove currency symbol and whitespace (keep digits, comma, dot, minus)
            let clean = val.toString().replace(/[^\d.,-]/g, "").trim();

            // Clean up leading/trailing punctuation (e.g. from "Bs.F" -> ".")
            clean = clean.replace(/^[.,]+|[.,]+$/g, "");

            // Handle 1.000,00 format (common in this context) -> 1000.00
            // If comma exists and is after the last dot (or no dot), assume it's decimal separator
            if (clean.includes(',') && (!clean.includes('.') || clean.lastIndexOf(',') > clean.lastIndexOf('.'))) {
                clean = clean.replace(/\./g, "").replace(",", ".");
            } else {
                // Handle 1,000.00 format -> 1000.00
                clean = clean.replace(/,/g, "");
            }
            const floatVal = parseFloat(clean);
            return isNaN(floatVal) ? 0 : floatVal;
        };

        try {


            if (!this.pos.config.show_dual_currency && !this.pos.res_currency_ref) {
                return null;
            }

            let price = 0;

            // Method 1: Try structured object (priceWithTax) if available
            if (typeof line.get_all_prices === 'function') {
                const prices = line.get_all_prices();
                price = prices.priceWithTax;
            }
            // Method 2: Try specific getter
            else if (typeof line.get_price_with_tax === 'function') {
                price = line.get_price_with_tax();
            }
            // Method 3: Parse from props (Fallback for Display Props)
            else {
                // Safe bet: Parse unitPrice * Parse qty.
                const rawUnit = line.unitPrice || line.price;
                const rawQty = line.qty;

                const unitP = parseValue(rawUnit);
                const q = parseValue(rawQty);
                price = unitP * q;
            }

            if (!price) price = 0;

            return this.pos.getAmountInRefCurrency(price, true);

        } catch (e) {
            console.error("Orderline Price Calculation Error:", e);
            return "ERR";
        }
    }
});
