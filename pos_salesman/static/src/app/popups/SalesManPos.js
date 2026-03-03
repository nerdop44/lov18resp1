/** @odoo-module */

import { AbstractAwaitablePopup } from "@point_of_sale/app/popup/popup";
import { _t } from "@web/core/l10n/translation";

export class SalesManPos extends AbstractAwaitablePopup {
    static template = "pos_salesman.SalesManPos";
    static props = {
        ...AbstractAwaitablePopup.props,
        salesmen: { type: Array, optional: true },
    };
    static defaultProps = {
        ...AbstractAwaitablePopup.defaultProps,
        confirmText: _t("Seleccionar"),
        cancelText: _t("Cancelar"),
        title: _t("Asignar Vendedor"),
        salesmen: [],
    };
    selectSalesman(salesman) {
        this.confirm(salesman);
    }
}
