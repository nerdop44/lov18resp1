/** @odoo-module */

import { _t } from "@web/core/l10n/translation";

import { usePos } from "@point_of_sale/app/store/pos_hook";
import { useService } from "@web/core/utils/hooks";
import { Component } from "@odoo/owl";
import { SalesManPos } from "@pos_salesman/app/popups/SalesManPos";

import { registry } from "@web/core/registry";

export class BtnSalesMan extends Component {
    static template = "pos_salesman.BtnSalesMan";
    setup() {
        this.pos = usePos();
        this.dialog = useService("dialog");
        this.notification = useService("notification");
    }
    async onClick() {
        const order = this.pos.get_order();
        if (!order) return;

        console.log("BtnSalesMan: this.pos.data keys:", Object.keys(this.pos.data));

        let salesman_list = (this.pos.data && this.pos.data.hr_salesmen) || [];

        // Fallback 1: Try from PosStore's direct property (if we patched it there)
        if (salesman_list.length === 0 && this.pos.hr_salesmen) {
            salesman_list = this.pos.hr_salesmen;
        }

        // Fallback 2: Try from the actual hr.employee model records in Odoo 18
        if (salesman_list.length === 0 && this.pos.models && this.pos.models['hr.employee']) {
            const employeeModel = this.pos.models['hr.employee'];
            const allEmployees = typeof employeeModel.getAll === 'function' ? employeeModel.getAll() : (employeeModel.data || []);

            // Filter by the IDs in config if available
            const allowedIds = this.pos.config.salesman_ids || [];
            if (allowedIds.length > 0) {
                salesman_list = allEmployees.filter(e => allowedIds.includes(e.id));
            } else {
                salesman_list = allEmployees;
            }
        }

        console.log("BtnSalesMan: Final salesman_list count:", salesman_list.length);

        if (salesman_list.length === 0) {
            this.notification.add(_t("No hay vendedores configurados para este punto de venta."), {
                title: _t("Sin Vendedores"),
                type: "danger",
            });
            return;
        }

        const salesmen = salesman_list.map(s => ({
            ...s,
            image_url: `/web/image/hr.employee/${s.id}/image_128`
        }));

        this.dialog.add(SalesManPos, {
            title: _t("Seleccionar Vendedor"),
            salesmen: salesmen,
            getPayload: (salesmanId) => {
                order.set_salesman_id(salesmanId);
            },
        });
    }
    get salesmanName() {
        const order = this.pos.get_order();
        return (order && order.salesman_id) ? order.salesman_id.name : "";
    }
}

import { ActionpadWidget } from "@point_of_sale/app/screens/product_screen/action_pad/action_pad";
import { patch } from "@web/core/utils/patch";

patch(ActionpadWidget.components, {
    BtnSalesMan,
});
