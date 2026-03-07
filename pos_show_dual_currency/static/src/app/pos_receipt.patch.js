/** @odoo-module */

import { OrderReceipt } from "@point_of_sale/app/screens/receipt_screen/receipt/order_receipt";
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";

patch(OrderReceipt.prototype, {
    setup() {
        super.setup();
        this.pos = useService("pos");
    }
});
