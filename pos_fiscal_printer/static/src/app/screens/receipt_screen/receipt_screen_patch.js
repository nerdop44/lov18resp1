/** @odoo-module */

import { ReceiptScreen } from "@point_of_sale/app/screens/receipt_screen/receipt_screen";
import { FiscalPrinterMixin } from "@pos_fiscal_printer/app/utils/printing_mixin";
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { NotaCreditoPopUp } from "@pos_fiscal_printer/app/popup/nota_credito_popup";

const patchConfig = {
    setup() {
        super.setup();
        this.orm = useService("orm");
        this.dialog = useService("dialog");

        // Initialize mixin properties on the instance
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

// Properly merge the mixin into patchConfig
Object.assign(patchConfig, FiscalPrinterMixin);

patch(ReceiptScreen.prototype, patchConfig);
