/** @odoo-module */

import { AbstractAwaitablePopup } from "@point_of_sale/app/utils/abstract_awaitable_popup";
import { onMounted, useState } from "@odoo/owl";
import { usePos } from "@point_of_sale/app/store/pos_hook";

export class NotaCreditoPopUp extends AbstractAwaitablePopup {
    static template = "pos_fiscal_printer.NotaCreditoPopUp";

    setup() {
        super.setup();
        this.pos = usePos();
        this.fields = useState({
            printerCode: this.pos.config.x_fiscal_printer_code || "",
            invoiceNumber: "",
            date: (new Date()).toISOString().split("T")[0]
        });
    }

    getPayload() {
        return this.fields;
    }
}
