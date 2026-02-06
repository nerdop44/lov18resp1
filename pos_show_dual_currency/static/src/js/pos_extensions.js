/** @odoo-module **/

import { ProductCard } from "@point_of_sale/app/generic_components/product_card/product_card";
import { Orderline } from "@point_of_sale/app/generic_components/orderline/orderline";
import { OrderWidget } from "@point_of_sale/app/generic_components/order_widget/order_widget";
import { patch } from "@web/core/utils/patch";
import { usePos } from "@point_of_sale/app/store/pos_hook";

patch(ProductCard.prototype, {
    setup() {
        super.setup();
        this.pos = usePos();
    }
});

patch(Orderline.prototype, {
    setup() {
        super.setup();
        this.pos = usePos();
    }
});

patch(OrderWidget.prototype, {
    setup() {
        super.setup();
        this.pos = usePos();
    }
});
