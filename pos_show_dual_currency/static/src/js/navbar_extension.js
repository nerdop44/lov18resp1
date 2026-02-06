/** @odoo-module **/

import { Navbar } from "@point_of_sale/app/navbar/navbar";
import { TRM } from "./ChromeWidgets/TRM";
import { CashMoveButtonRefCurrency } from "./ChromeWidgets/CashMoveButton";
import { patch } from "@web/core/utils/patch";

patch(Navbar.prototype, {
    // Add sub-components
});

Object.assign(Navbar.components, { TRM, CashMoveButtonRefCurrency });
