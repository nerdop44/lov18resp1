import { AbstractPosPopup } from "@point_of_sale/app/utils/abstract_pos_popup";
import { _t } from "@web/core/l10n/translation";

export class SalesManPos extends AbstractPosPopup {
    static template = "pos_salesman.SalesManPos";
    static defaultProps = {
        confirmText: _t("Seleccionar"),
        cancelText: _t("Cancelar"),
        title: _t("Asignar Vendedor"),
        salesmen: [],
    };
    selectSalesman(salesman) {
        this.confirm(salesman);
    }
}
