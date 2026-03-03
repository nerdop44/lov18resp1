/** @odoo-module */

import { Component, useState } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { useService } from "@web/core/utils/hooks";

export class NotaCreditoPopUp extends Component {
    static template = "pos_fiscal_printer.NotaCreditoPopUp";
    static components = { Dialog };
    // Temporarily removing props validation to fix OwlError crash
    static props = {
        getPayload: { type: Function, optional: true },
        close: { type: Function, optional: true },
    };

    setup() {
        this.pos = useService("pos");
        this.fields = useState({
            printerCode: this.pos.config.x_fiscal_printer_code || "",
            invoiceNumber: "",
            date: (new Date()).toISOString().split("T")[0]
        });
    }

    confirm() {
        this.props.getPayload(this.fields);
        this.props.close();
    }

    cancel() {
        this.props.close();
    }
}
