/** @odoo-module */

import { Component } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";

export class SalesManPos extends Component {
    static template = "pos_salesman.SalesManPos";
    static props = {
        title: { type: String, optional: true },
        salesmen: { type: Array, optional: true },
        cancelText: { type: String, optional: true },
        confirmText: { type: String, optional: true },
        getPayload: { type: Function, optional: true },
        close: { type: Function, optional: true },
        keepBehind: { type: Boolean, optional: true },
    };
    static defaultProps = {
        confirmText: _t("Seleccionar"),
        cancelText: _t("Cancelar"),
        title: _t("Asignar Vendedor"),
        salesmen: [],
    };
    selectSalesman(salesman) {
        if (this.props.getPayload) {
            this.props.getPayload(salesman);
        }
        if (this.props.close) {
            this.props.close();
        }
    }
    cancel() {
        if (this.props.close) {
            this.props.close();
        }
    }
}
