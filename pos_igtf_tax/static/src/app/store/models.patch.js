/** @odoo-module */

import { ProductProduct } from "@point_of_sale/app/models/product_product";
import { PosPayment } from "@point_of_sale/app/models/pos_payment";
import { PosOrder } from "@point_of_sale/app/models/pos_order";
import { PosOrderline } from "@point_of_sale/app/models/pos_order_line";
import { patch } from "@web/core/utils/patch";
import { roundDecimals } from "@web/core/utils/numbers";

patch(ProductProduct.prototype, {
    get isIgtfProduct() {
        const config = this.pos.config;
        return config?.x_igtf_product_id ? config.x_igtf_product_id[0] === this.id : false;
    }
});

patch(PosPayment.prototype, {
    get isForeignExchange() {
        return this.payment_method_id?.x_is_foreign_exchange || false;
    },

    set isForeignExchange(val) {
        // Allow assignment from server data
    },

    set_amount(value) {
        const config = this.pos.config;
        const order = this.pos_order_id;

        // Native apply
        if (this.isForeignExchange) {
            super.set_amount(value * (config.show_currency_rate || 1.0));
        } else {
            super.set_amount(value);
        }

        const igtfProduct = config.x_igtf_product_id;
        if (!(igtfProduct || igtfProduct?.length)) return;
        if (!this.isForeignExchange) {
            // If we are changing from a foreign exchange to something else, remove IGTF
            order.removeIGTF();
            return;
        }

        // Add/Refresh IGTF line
        order.removeIGTF();
        const price = order.x_igtf_amount;
        const product = this.models["product.product"].get(igtfProduct[0]);

        if (product && price > 0) {
            order.add_product(product, {
                quantity: 1,
                price: price,
                lst_price: price,
                merge: false,
                extra_vals: { x_is_igtf_line: true }
            });
        }
    }
});

patch(PosOrderline.prototype, {
    setup() {
        super.setup(...arguments);
        this.x_is_igtf_line = this.x_is_igtf_line || false;
        if (this.product_id?.isIgtfProduct) {
            this.x_is_igtf_line = true;
        }
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

patch(PosOrder.prototype, {
    get x_igtf_amount() {
        const paymentLines = this.payment_ids || [];

        const igtf_monto = paymentLines
            .filter((p) => p.isForeignExchange)
            .map(({ amount, payment_method_id }) => {
                const percentage = payment_method_id?.x_igtf_percentage || 0;
                return amount * (percentage / 100);
            })
            .reduce((prev, current) => prev + current, 0);

        const total = (this.lines || [])
            .filter((p) => !p.x_is_igtf_line)
            .map((p) => p.get_price_with_tax())
            .reduce((prev, current) => prev + current, 0);

        const max_igtf = total * 0.03;

        let final_igtf = igtf_monto;
        if (igtf_monto > max_igtf) {
            final_igtf = max_igtf;
        }

        return roundDecimals(parseFloat(final_igtf) || 0, 2);
    },
    set x_igtf_amount(val) {
        // Allow assignment from server data
    },

    removeIGTF() {
        const linesToRemove = (this.lines || []).filter(({ x_is_igtf_line }) => x_is_igtf_line);
        linesToRemove.forEach((line) => this.removeOrderline(line));
    },

    add_product(product, options) {
        return super.add_product(product, options);
    }
});
