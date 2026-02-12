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

        // Ensure state is initialized correctly
        this.state = useState({
            ...(this.state || {}),
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

    // Define accessors manually to link with global POS state
    get port() {
        return this.pos.serialPort;
    },
    set port(serialPort) {
        this.pos.serialPort = serialPort;
    },

    get readerStream() {
        return this.port?.readable?.getReader();
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

// Explicitly assign mixin methods to avoid descriptor/getter issues with Owl
Object.assign(patchConfig, {
    setPort: FiscalPrinterMixin.setPort,
    actionPrint: FiscalPrinterMixin.actionPrint,
    printViaUSB: FiscalPrinterMixin.printViaUSB,
    printViaApi: FiscalPrinterMixin.printViaApi,
    printZViaApi: FiscalPrinterMixin.printZViaApi,
    printXViaApi: FiscalPrinterMixin.printXViaApi,
    write: FiscalPrinterMixin.write,
    write_s2: FiscalPrinterMixin.write_s2,
    write_Z: FiscalPrinterMixin.write_Z,
    escribe_leer: FiscalPrinterMixin.escribe_leer,
    setHeader: FiscalPrinterMixin.setHeader,
    setLines: FiscalPrinterMixin.setLines,
    setTotal: FiscalPrinterMixin.setTotal,
    printFiscal: FiscalPrinterMixin.printFiscal,
    printNoFiscal: FiscalPrinterMixin.printNoFiscal,
    showPopup: FiscalPrinterMixin.showPopup,
});

patch(ClosePosPopup.prototype, patchConfig);
