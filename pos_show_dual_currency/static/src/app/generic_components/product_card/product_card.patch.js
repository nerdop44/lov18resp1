/** @odoo-module */

import { ProductCard } from "@point_of_sale/app/generic_components/product_card/product_card";
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";

patch(ProductCard.prototype, {
    setup() {
        if (super.setup) {
            super.setup();
        }
        try {
            this.pos = useService("pos");
        } catch (e) {
            console.error("Failed to load 'pos' service in ProductCard:", e);
        }
    },

    get priceInRefCurrency() {
        if (!this.pos.config.show_dual_currency && !this.pos.res_currency_ref) {
            return "";
        }
        // Direct read from product.lst_price (the MASTER USD price in this DB)
        return this.pos.format_currency_ref(this.props.product.lst_price || 0);
    },

    get mainPrice() {
        return this.pos.getProductPriceFormatted(this.props.product, false);
    }
});
