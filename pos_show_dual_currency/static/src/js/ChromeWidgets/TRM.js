/** @odoo-module **/

import { Component } from "@odoo/owl";
import { usePos } from "@point_of_sale/app/store/pos_hook";

export class TRM extends Component {
    static template = "pos_show_dual_currency.TRM";

    setup() {
        this.pos = usePos();
    }

    get trm() {
        const rate = this.pos.config.show_currency_rate || 1;
        return this.pos.env.utils.formatCurrency(1 / rate, false, this.pos.currency);
    }
}
