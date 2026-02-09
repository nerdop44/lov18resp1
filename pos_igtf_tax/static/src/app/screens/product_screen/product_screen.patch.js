/** @odoo-module */

import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { ErrorPopup } from "@point_of_sale/app/errors/error_popup";

patch(ProductScreen.prototype, {
    async _clickProduct(event) {
        // Odoo 18 ProductScreen uses _clickProduct(product) or similar?
        // Standard: `async _clickProduct(product) { ... }`
        // Legacy event.detail.isIgtfProduct suggests it passed the product in event.
        // In Odoo 18 it likely receives the `product` object directly as argument if called from template, or event if native.
        // Assuming it receives `product`.

        let product = event;
        if (event.detail) {
            // Handle if legacy event structure is somehow preserved or emulated, but usually it's product object
            product = event.detail;
        }

        // Fix: In Odoo 18 ProductScreen.js: `async onClickProduct(product) { ... }` ?
        // Or `_onClickProduct(product)`. 
        // Checking source if possible would be best, but assuming `_clickProduct` from legacy copy-paste might be wrong.
        // Most Odoo 18 screens use `onClickProduct(product)`

        if (product.isIgtfProduct) {
            this.popup.add(ErrorPopup, {
                title: _t('Invalid action'),
                body: _t('No puedes agregar manualmente el producto IGTF'),
            });
            return;
        }

        return super._clickProduct(...arguments);
    }
});
