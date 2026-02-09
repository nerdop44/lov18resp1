/** @odoo-module */

import { ProductInfoPopup } from "@point_of_sale/app/screens/product_screen/product_info_popup/product_info_popup";
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";

patch(ProductInfoPopup.prototype, {
    setup() {
        super.setup();
        this.pos = useService("pos");
    },

    get priceInRefCurrency() {
        if (!this.pos.config.show_dual_currency && !this.pos.res_currency_ref) {
            return "";
        }
        return this.pos.getProductPriceFormatted(this.props.product, true);
    }
});
