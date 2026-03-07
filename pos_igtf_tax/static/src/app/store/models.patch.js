/** @odoo-module */

import { ProductProduct } from "@point_of_sale/app/models/product_product";
import { PosPayment } from "@point_of_sale/app/models/pos_payment";
import { PosOrder } from "@point_of_sale/app/models/pos_order";
import { PosOrderline } from "@point_of_sale/app/models/pos_order_line";
import { PosData } from "@point_of_sale/app/models/data_service";
import DevicesSynchronisation from "@point_of_sale/app/store/devices_synchronisation";
import { patch } from "@web/core/utils/patch";
import { roundDecimals } from "@web/core/utils/numbers";

// Pachacutec: Global lock to prevent IGTF reactivity during order deletion or synchronization.
// This is critical to ensure synchronous operations don't collide with the reactive model.
window.__pachacutec_global_lock = false;

patch(ProductProduct.prototype, {
    get isIgtfProduct() {
        const config = this.models?.["pos.config"]?.getFirst();
        return config?.x_igtf_product_id ? config.x_igtf_product_id[0] === this.id : false;
    }
});

patch(PosData.prototype, {
    localDeleteCascade(record, removeFromServer = false) {
        // Pachacutec: Activate global lock before any cascade cleanup.
        window.__pachacutec_global_lock = true;
        try {
            const result = super.localDeleteCascade(...arguments);
            return result;
        } catch (e) {
            console.error("Pachacutec: localDeleteCascade crash suppressed:", e);
            return true;
        } finally {
            // Restore lock only after the entire cascade (and its side effects) finished.
            window.__pachacutec_global_lock = false;
        }
    }
});

patch(DevicesSynchronisation.prototype, {
    processDeletedRecords(deletedRecords) {
        // Pachacutec: Activate global lock during whole synchronization cleanup.
        // This prevents IGTF from reacting while multiple records are being purged.
        window.__pachacutec_global_lock = true;
        try {
            return super.processDeletedRecords(...arguments);
        } catch (e) {
            console.error("Pachacutec: processDeletedRecords crash suppressed during sync:", e);
            return true;
        } finally {
            window.__pachacutec_global_lock = false;
        }
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
        if (window.__pachacutec_global_lock) {
            super.set_amount(value);
            return;
        }
        const config = this.models?.["pos.config"]?.getFirst();
        const order = this.pos_order_id;
        let amount = value;

        if (this.isForeignExchange && order && config) {
            const due = typeof order.getTotalDue === "function" ? order.getTotalDue() : 0;
            if (Math.abs(value - due) > 0.01) {
                amount = value * (config.show_currency_rate || 1.0);
            }
        }
        super.set_amount(amount);
        if (order && !window.__pachacutec_global_lock && typeof order.refreshIGTF === "function") {
            try {
                order.refreshIGTF();
            } catch (e) {
                console.warn("Pachacutec: refreshIGTF failed during set_amount", e);
            }
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
        if (window.__pachacutec_global_lock || !this.models) return 0;
        
        try {
            const paymentLines = (this.payment_ids || []).filter(p => p && p.payment_method_id);

            const igtf_monto = paymentLines
                .filter((p) => p.isForeignExchange)
                .map(({ amount, payment_method_id }) => {
                    const percentage = payment_method_id?.x_igtf_percentage || 0;
                    return (amount || 0) * (percentage / 100);
                })
                .reduce((prev, current) => prev + current, 0);

            const total = (this.lines || [])
                .filter((p) => p && !p.x_is_igtf_line)
                .map((p) => typeof p.get_price_with_tax === "function" ? p.get_price_with_tax() : 0)
                .reduce((prev, current) => prev + current, 0);

            const max_igtf = total * 0.03;

            let final_igtf = igtf_monto;
            if (igtf_monto > max_igtf) {
                final_igtf = max_igtf;
            }

            return roundDecimals(parseFloat(final_igtf) || 0, 2);
        } catch (e) {
            return 0;
        }
    },
    set x_igtf_amount(val) {
        // Allow assignment from server data
    },

    get igtf_base_bs() {
        if (window.__pachacutec_global_lock || !this.models) return 0;
        return (this.payment_ids || [])
            .filter((p) => p && p.isForeignExchange)
            .reduce((sum, p) => sum + (p.amount || 0), 0);
    },

    get igtf_base_divisa() {
        if (window.__pachacutec_global_lock || !this.models) return 0;
        const config = this.models["pos.config"]?.getFirst();
        const rate = config?.show_currency_rate || 1.0;
        return this.igtf_base_bs / (rate > 0 ? rate : 1.0);
    },

    get sale_total_without_igtf() {
        if (window.__pachacutec_global_lock || !this.models) return 0;
        return (this.lines || [])
            .filter((p) => p && !p.x_is_igtf_line)
            .map((p) => typeof p.get_price_with_tax === "function" ? p.get_price_with_tax() : 0)
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
        if (window.__pachacutec_global_lock) {
            super.update(vals, opts);
            return;
        }
        super.update(vals, opts);
        if (vals.payment_ids && !window.__pachacutec_global_lock) {
            try {
                this.refreshIGTF();
            } catch (e) {
                console.warn("Pachacutec: refreshIGTF failed during update", e);
            }
        }
    },

    delete() {
        // Extra safety: set lock if called directly (though usually it goes to PosData)
        window.__pachacutec_global_lock = true;
        try {
            return super.delete(...arguments);
        } finally {
            // Note: we don't unset it here if it was set by localDeleteCascade or sync
        }
    },

    remove_paymentline(line) {
        super.remove_paymentline(line);
        if (!window.__pachacutec_global_lock) {
            try {
                this.refreshIGTF();
            } catch (e) {
                console.warn("Pachacutec: refreshIGTF failed during remove_paymentline", e);
            }
        }
    },

    refreshIGTF() {
        if (!this.models || this.finalized || window.__pachacutec_global_lock) return;
        
        try {
            this.removeIGTF();
            const config = this.config;
            const igtfPercentage = this.x_igtf_percentage || 0;
            const igtfProduct = config?.x_igtf_product_id;

            if (igtfPercentage > 0 && igtfProduct) {
                const product = this.models["product.product"]?.get(igtfProduct[0]);
                const price = this.get_total_with_tax() * (igtfPercentage / 100);

                if (product && Math.abs(price) > 0.001) {
                    this.update({
                        lines: [["create", {
                            product_id: product,
                            price_unit: price,
                            qty: 1,
                            price_type: "original",
                            x_is_igtf_line: true
                        }]]
                    });
                    this.recomputeOrderData();
                }
            }
        } catch (e) {
            console.error("Error refreshing IGTF:", e);
        }
    },

    removeIGTF() {
        if (window.__pachacutec_global_lock || !this.models) return;
        const linesToRemove = (this.lines || []).filter((l) => l && l.x_is_igtf_line);
        for (const line of linesToRemove) {
            if (line && typeof line.delete === "function") {
                try {
                    line.delete();
                } catch (e) {
                    console.warn("Pachacutec: Error deleting IGTF line", e);
                }
            }
        }
    }
});
