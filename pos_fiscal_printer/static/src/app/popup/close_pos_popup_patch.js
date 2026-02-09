/** @odoo-module */

import { ClosePosPopup } from "@point_of_sale/app/navbar/closing_popup/closing_popup";
import { FiscalPrinterMixin } from "@pos_fiscal_printer/app/utils/printing_mixin";
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";
import { onMounted, useState } from "@odoo/owl";

const patchConfig = {
    setup() {
        super.setup();
        this.orm = useService("orm");
        this.pos = useService("pos");
        this.state = useState({
            ...this.state,
            zReport: "",
        });

        // Initialize mixin properties
        Object.assign(this, {
            printerCommands: [],
            printing: false,
            read_s2: false,
            read_Z: false,
            writer: false,
            reader: false,
            verificar_desconexion: false,
        });
    },

    openDetailsPopup() {
        this.state.zReport = ""
        return super.openDetailsPopup();
    },

    async closeSession() {
        if (this.state.zReport === "" || !this.state.zReport) {
            console.log("closeSession sin reporte Z");
        } else {
            console.log("closeSession con reporte Z");
            await this.orm.call("pos.session", "set_z_report", [this.pos.pos_session.id, this.state.zReport]);
        }
        return super.closeSession();
    },

    async printZReport() {
        if (this.pos.config.connection_type === "api") {
            this.printZViaApi();
        } else {
            this.printerCommands = [];
            this.read_Z = false;
            this.printerCommands.push("I0Z");
            await this.actionPrint();
        }
    },

    async printXReport() {
        if (this.pos.config.connection_type === "api") {
            this.printXViaApi();
        } else {
            this.printerCommands = [];
            this.read_Z = false;
            this.printerCommands.push("I0X");
            await this.actionPrint();
        }
    }
};

// Manually merge FiscalPrinterMixin to avoid spread operator invoking getters
const descriptors = Object.getOwnPropertyDescriptors(FiscalPrinterMixin);
for (const [key, desc] of Object.entries(descriptors)) {
    if (!patchConfig.hasOwnProperty(key)) {
        Object.defineProperty(patchConfig, key, desc);
    }
}

patch(ClosePosPopup.prototype, patchConfig);
