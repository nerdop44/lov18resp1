/** @odoo-module */

import { ReceiptScreen } from "@point_of_sale/app/screens/receipt_screen/receipt_screen";
import { FiscalPrinterMixin } from "@pos_fiscal_printer/app/utils/printing_mixin";
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
// Removing unused import if NotaCreditoPopUp is not used here directly or check usage.
// It is not used in the code block provided in previous step! 
// Wait, step 3674 imports it but doesn't use it in setup or orderDone.
// It might be used by the mixin methods if they were copied?
// But mixin methods run in context of 'this'.
// If printNotaCredito is called, it uses 'NotaCreditoPopUp'.
// Where does 'printNotaCredito' get 'NotaCreditoPopUp' from?
// In mixin file (restored), it uses it as a variable.
// But mixin file DOES NOT IMPORT IT. 
// This means 'printNotaCredito' in mixin is BROKEN unless 'NotaCreditoPopUp' is global.
// I should import it here and make it available to the instance?
// Or import it in mixin file?
// The mixin is an object. It captures variables from its module scope.
// If mixin module doesn't import it, it fails.
// I MUST FIX MIXIN IMPORT TOO.

// For now, let's fix ReceiptScreen patch to be safe.
import { NotaCreditoPopUp } from "@pos_fiscal_printer/app/popup/nota_credito_popup";

const patchConfig = {
    setup() {
        super.setup();
        this.orm = useService("orm");
        this.dialog = useService("dialog");
        this.pos = useService("pos"); // Needed for port getter

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

    // Define accessors manually
    get port() {
        return this.pos.serialPort;
    },
    set port(serialPort) {
        this.pos.serialPort = serialPort;
    },

    get readerStream() {
        return this.port?.readable?.getReader();
    },

    orderDone() {
        if (this.currentOrder.impresa) {
            super.orderDone();
        } else {
            this.dialog.add(ConfirmationDialog, {
                title: _t("Confirmación"),
                body: _t("Debe imprimir el documento fiscal. ¿Desea continuar sin imprimir?"),
                confirm: () => super.orderDone(),
                cancel: () => { },
            });
        }
    }
};

// Explicitly assign mixin methods.
const mixinMethods = [
    'setPort', 'actionPrint', 'printViaUSB',
    'printViaApi', 'printZViaApi', 'printXViaApi',
    'write', 'write_s2', 'write_Z', 'escribe_leer',
    'setHeader', 'setLines', 'setTotal',
    'printFiscal', 'printNoFiscal', 'printNotaCredito',
    'doPrinting' // Added doPrinting as it is key for ReceiptScreen
];

for (const method of mixinMethods) {
    if (FiscalPrinterMixin[method]) {
        patchConfig[method] = FiscalPrinterMixin[method];
    }
}

// patch(ReceiptScreen.prototype, patchConfig);
