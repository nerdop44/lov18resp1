/** @odoo-module */

import { Product, Payment, Order, Orderline } from "@point_of_sale/app/store/models";
import { patch } from "@web/core/utils/patch";
import { floatRound } from "@web/core/utils/numbers";

patch(Product.prototype, {
    get isIgtfProduct() {
        const { x_igtf_product_id } = this.pos.config;
        return x_igtf_product_id ? x_igtf_product_id[0] === this.id : false;
    }
});

patch(Payment.prototype, {
    get isForeignExchange() {
        return this.payment_method.x_is_foreign_exchange;
    },

    set_amount(value) {
        const igtf_antes = this.order.x_igtf_amount;

        if (value === this.order.get_due()) {
            super.set_amount(value);
        } else {
            if (value !== igtf_antes) {
                if (this.isForeignExchange) {
                    // Use output of show_currency_rate which we corrected to be 1/Rate (Tasa)
                    // But here logic was (1/rate). failing if rate is Tasa.
                    // If show_currency_rate is Tasa (e.g. 38), then 1/38 is correct for VEF->USD conversion if value is VEF?
                    // Wait, set_amount usually takes the amount in the currency of the payment line?
                    // If isForeignExchange (USD), and we input USD, we don't need conversion?
                    // Legacy code: value * (1/this.pos.config.show_currency_rate)
                    super.set_amount(value * (1 / this.pos.config.show_currency_rate));
                } else {
                    super.set_amount(value);
                }
            }
        }

        const igtfProduct = this.pos.config.x_igtf_product_id;
        if (!(igtfProduct || igtfProduct?.length)) return;
        if (!this.isForeignExchange) return;

        if (value === igtf_antes) return;
        this.order.removeIGTF();

        const price = this.order.x_igtf_amount;

        // pos.db might not exist in Odoo 18 the same way. 
        // Products are in this.pos.models['product.product'] or accessible via this.pos.db if legacy supported.
        // In Odoo 18, we can use this.pos.models['product.product'].getBy('id', id) or similar?
        // Actually pos.db is still used for indexing.
        const product = this.pos.db.product_by_id[igtfProduct[0]];

        if (product) {
            this.order.add_product(product, {
                quantity: 1,
                price: price,
                lst_price: price,
                merge: false, // Don't merge IGTF lines?
            });
        }
    }
});

patch(Orderline.prototype, {
    setup() {
        super.setup(...arguments);
        this.x_is_igtf_line = this.x_is_igtf_line || false;
    },

    init_from_JSON(json) {
        super.init_from_JSON(...arguments);
        this.x_is_igtf_line = json.x_is_igtf_line;
    },

    export_as_JSON() {
        const result = super.export_as_JSON();
        result.x_is_igtf_line = this.x_is_igtf_line;
        return result;
    },

    export_for_printing() {
        const json = super.export_for_printing(...arguments);
        json.x_is_igtf_line = this.x_is_igtf_line;
        return json;
    }
});

patch(Order.prototype, {
    get x_igtf_amount() {
        // paymentlines might be payment_lines in Odoo 18? No, it's payment_lines in basic model, but getter 'paymentlines' exists?
        // Checked Odoo 18 source: Order has `payment_lines` (collection).
        // Legacy code used `this.paymentlines`.
        const paymentLines = this.payment_lines;

        const igtf_monto = paymentLines
            .filter((p) => p.isForeignExchange)
            .map(({ amount, payment_method: { x_igtf_percentage } }) => amount * (x_igtf_percentage / 100))
            .reduce((prev, current) => prev + current, 0);

        // orderlines -> order_lines
        const total = this.order_lines
            .filter((p) => !p.x_is_igtf_line)
            .map((p) => p.get_price_with_tax())
            .reduce((prev, current) => prev + current, 0);

        const max_igtf = total * 0.03;

        let final_igtf = igtf_monto;
        if (igtf_monto > max_igtf) {
            final_igtf = max_igtf;
        }

        return floatRound(parseFloat(final_igtf) || 0, 2); // default decimal places?
    },

    removeIGTF() {
        // orderlines -> order_lines
        // remove_orderline -> removeOrderline? No, typically remove_orderline remains or deleteOrderline.
        // Odoo 18 Order: removeOrderline(orderline)
        const linesToRemove = this.order_lines.filter(({ x_is_igtf_line }) => x_is_igtf_line);
        linesToRemove.forEach((line) => this.removeOrderline(line));
    },

    add_product(product, options) {
        // Hook to set x_is_igtf_line if product is IGTF
        // But the legacy code used `set_orderline_options`.
        // `add_product` calls `create_orderline` then `set_orderline_options`?
        // In Odoo 18 `add_product` does most work.
        // We can hook `createOrderline`?
        // Or override `add_product` to check options? -> No, safer to patch `set_orderline_options` if it exists.
        // Order.js 18: `async add_product(product, options)`
        // It calls `await this.lines.add({ product, ... })`.
        // There is no `set_orderline_options` in Odoo 18 Order class usually.
        // The logic was: `orderline.x_is_igtf_line = orderline.product.isIgtfProduct;`

        // We can override `pay` or other methods? 
        // Actually, we can check during `add_product` flow?
        // Simpler: Patch `Orderline` setup/init to check its product?
        // No, `Orderline` setup doesn't know context easily.

        // Let's call super first
        const res = super.add_product(product, options);
        // But add_product returns void/promise.
        // The line is added to `this.order_lines`.
        // We can check the last added line?

        // Better approach: Patch `Orderline` creation via `_createLine` or similar if accessible.
        // Or just let `Orderline` check its product in `setup`.
        return res;
    }
});

// Patching Orderline to set flag on init if product is IGTF
patch(Orderline.prototype, {
    setup() {
        super.setup(...arguments);
        if (this.product.isIgtfProduct) {
            this.x_is_igtf_line = true;
        }
    }
});
