/** @odoo-module */

import { ProductProduct } from "@point_of_sale/app/models/product_product";
import { PosPayment } from "@point_of_sale/app/models/pos_payment";
import { PosOrder } from "@point_of_sale/app/models/pos_order";
import { PosOrderline } from "@point_of_sale/app/models/pos_order_line";
import { patch } from "@web/core/utils/patch";
import { roundDecimals } from "@web/core/utils/numbers";

patch(ProductProduct.prototype, {
    get isIgtfProduct() {
        const config = this.models?.["pos.config"]?.getFirst();
        return config?.x_igtf_product_id ? config.x_igtf_product_id[0] === this.id : false;
    }
});

patch(PosPayment.prototype, {
    get isForeignExchange() {
        const currency_ref = this.pos?.res_currency_ref;
        if (currency_ref && this.payment_method_id && this.payment_method_id.currency_id) {
            return this.payment_method_id.currency_id.id === currency_ref.id;
        }
        return false;
    },
    set isForeignExchange(val) {
        // Allow assignment from server data
    },

    set_amount(value) {
        const igtf_antes = this.order.x_igtf_amount;

        if (value === this.order.get_due()) {
            super.set_amount(value);
        } else {
            if (value !== igtf_antes) {
                if (this.isForeignExchange) {
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
        const product = this.pos.db.product_by_id[igtfProduct[0]];

        if (product) {
            this.order.add_product(product, {
                quantity: 1,
                price: price,
                lst_price: price,
                merge: false,
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
