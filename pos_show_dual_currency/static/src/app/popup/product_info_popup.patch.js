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
        if (!this.pos.config.show_dual_currency && !this.pos.res_currency_ref) {
            return "";
        }
        // Direct read from product.lst_price (the MASTER USD price in this DB)
        return this.pos.format_currency_ref(this.props.product.lst_price || 0);
    }
});
