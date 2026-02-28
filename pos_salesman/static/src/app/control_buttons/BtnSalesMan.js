import { _t } from "@web/core/l10n/translation";
import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { Component } from "@odoo/owl";
import { SalesManPos } from "@pos_salesman/app/popups/SalesManPos";

export class BtnSalesMan extends Component {
    static template = "pos_salesman.BtnSalesMan";
    setup() {
        this.pos = usePos();
    }
    async onClick() {
        const order = this.pos.get_order();
        if (!order) return;

        if (this.pos.salesman_ids.length === 0) {
            this.pos.popup.add("ErrorPopup", {
                title: _t("Sin Vendedores"),
                body: _t("No hay vendedores configurados para este punto de venta."),
            });
            return;
        }

        const salesmen = this.pos.salesman_ids.map(s => ({
            ...s,
            image_url: `/web/image/hr.employee/${s.id}/image_128`
        }));

        const { confirmed, payload } = await this.pos.popup.add(SalesManPos, {
            title: _t("Seleccionar Vendedor"),
            salesmen: salesmen,
        });

        if (confirmed) {
            order.set_salesman_id(payload);
        }
    }
    get salesmanName() {
        const order = this.pos.get_order();
        return (order && order.salesman_id) ? order.salesman_id.name : "";
    }
}

ProductScreen.addControlButton({
    component: BtnSalesMan,
    condition: function () {
        return true;
    },
});
