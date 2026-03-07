/** @odoo-module */

import { PaymentScreenStatus } from "@point_of_sale/app/screens/payment_screen/payment_status/payment_status";
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";

patch(PaymentScreenStatus.prototype, {
    setup() {
        super.setup();
        this.pos = useService("pos");
    },
    get totalWithIgtf() {
        return this.env.utils.formatCurrency(this.props.order.total_with_igtf);
    },
    get totalWithIgtfDivisa() {
        return this.pos.getAmountInRefCurrency(this.props.order.total_with_igtf, true);
    }
});
