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
        return this.pos.getProductPriceFormatted(this.props.product, true);
    },

    get mainPrice() {
        return this.pos.getProductPriceFormatted(this.props.product, false);
    }
});
