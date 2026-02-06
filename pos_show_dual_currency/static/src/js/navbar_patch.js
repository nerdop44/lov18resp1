/** @odoo-module **/

import { Navbar } from "@point_of_sale/app/navbar/navbar";
import { patch } from "@web/core/utils/patch";
import { TRM } from "./ChromeWidgets/TRM";
import { CashMoveButtonRefCurrency } from "./ChromeWidgets/CashMoveButton";

patch(Navbar, {
    components: { ...Navbar.components, TRM, CashMoveButtonRefCurrency },
});
