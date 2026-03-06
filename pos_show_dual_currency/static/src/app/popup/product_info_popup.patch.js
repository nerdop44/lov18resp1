/** @odoo-module */

import { ProductInfoPopup } from "@point_of_sale/app/screens/product_screen/product_info_popup/product_info_popup";
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";

patch(ProductInfoPopup.prototype, {
    setup() {
        if (super.setup) {
            super.setup();
        }
        try {
            this.pos = useService("pos");
        } catch (e) {
            console.error("Failed to load 'pos' service in ProductInfoPopup:", e);
        }
    },

    get priceInRefCurrency() {
        return this.pos.getProductPriceFormatted(this.props.product, true);
    },

    get mainPrice() {
        return this.pos.getProductPriceFormatted(this.props.product, false);
    }
});
