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
        return this.payment_method_id?.x_is_foreign_exchange || false;
    },

    set isForeignExchange(val) {
        // Allow assignment from server data
    },

    set_amount(value) {
        const config = this.models?.["pos.config"]?.getFirst();
        const order = this.pos_order_id;
        let amount = value;

        // Pachacutec: Odoo auto-fills the remaining balance (due) in Bs when clicking the payment method.
        // We only multiply if the value being set is NOT the exact due balance, meaning the user 
        // typed a specific USD amount on the keypad.
        if (this.isForeignExchange) {
            const due = order.getTotalDue();
            if (Math.abs(value - due) > 0.01) {
                amount = value * (config.show_currency_rate || 1.0);
            }
        }
        super.set_amount(amount);
        order.refreshIGTF();
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

    get igtf_base_bs() {
        return (this.payment_ids || [])
            .filter((p) => p.isForeignExchange)
            .reduce((sum, p) => sum + p.amount, 0);
    },

    get igtf_base_divisa() {
        const config = this.models["pos.config"].getFirst();
        const rate = config?.show_currency_rate || 1.0;
        return this.igtf_base_bs / (rate > 0 ? rate : 1.0);
    },

    get sale_total_without_igtf() {
        return (this.lines || [])
            .filter((p) => !p.x_is_igtf_line)
            .map((p) => p.get_price_with_tax())
            .reduce((prev, current) => prev + current, 0);
    },

    get total_with_igtf() {
        return roundDecimals(this.sale_total_without_igtf + this.x_igtf_amount, 2);
    },

    export_for_printing() {
        const result = super.export_for_printing(...arguments);
        result.x_igtf_amount = this.x_igtf_amount;
        result.total_with_igtf = this.total_with_igtf;
        result.sale_total_without_igtf = this.sale_total_without_igtf;
        return result;
    },

    update(vals, opts) {
        super.update(vals, opts);
        if (vals.payment_ids) {
            this.refreshIGTF();
        }
    },

    remove_paymentline(line) {
        super.remove_paymentline(line);
        this.refreshIGTF();
    },

    refreshIGTF() {
        if (this.finalized) return;
        this.removeIGTF();
        
        const price = this.x_igtf_amount;
        const config = this.models["pos.config"].getFirst();
        const igtfProduct = config?.x_igtf_product_id;
        
        if (igtfProduct && igtfProduct.length > 0 && price > 0) {
            const product = this.models["product.product"].get(igtfProduct[0]);
            if (product) {
                // Pachacutec: Use update to ensure reactivity and total synchronization
                this.update({
                    lines: [["create", {
                        product_id: product,
                        order_id: this,
                        price_unit: price,
                        qty: 1,
                        price_type: "original",
                        x_is_igtf_line: true
                    }]]
                });
                this.recomputeOrderData();
            }
        }
    },

    removeIGTF() {
        const linesToRemove = (this.lines || []).filter(({ x_is_igtf_line }) => x_is_igtf_line);
        linesToRemove.forEach((line) => line.delete());
    }
});
