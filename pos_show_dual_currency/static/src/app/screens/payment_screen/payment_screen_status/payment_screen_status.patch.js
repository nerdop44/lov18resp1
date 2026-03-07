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
    },
    get saleTotal() {
        return this.env.utils.formatCurrency(this.props.order.sale_total_without_igtf);
    },
    get saleTotalDivisa() {
        return this.pos.getAmountInRefCurrency(this.props.order.sale_total_without_igtf, true);
    },
    get igtfAmount() {
        return this.env.utils.formatCurrency(this.props.order.x_igtf_amount);
    },
    get igtfAmountDivisa() {
        return this.pos.getAmountInRefCurrency(this.props.order.x_igtf_amount, true);
    },
    get remainingWithIgtf() {
        // order.get_due() returns (taxTotals.order_remaining) which is (total - paid)
        // Since IGTF is added as an orderline, it's already in total_with_tax and thus in get_due().
        return this.env.utils.formatCurrency(this.props.order.get_due());
    },
    get remainingWithIgtfDivisa() {
        return this.pos.getAmountInRefCurrency(this.props.order.get_due(), true);
    }
});
