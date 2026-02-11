/** @odoo-module */

import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";

patch(ProductScreen.prototype, {
    async addProductToOrder(product) {
        if (product.isIgtfProduct) {
            this.dialog.add(AlertDialog, {
                title: _t('Invalid action'),
                body: _t('No puedes agregar manualmente el producto IGTF'),
            });
            return;
        }

        return super.addProductToOrder(...arguments);
    }
});
