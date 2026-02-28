import { patch } from "@web/core/utils/patch";
import { PosStore } from "@point_of_sale/app/store/pos_store";
import { Order } from "@point_of_sale/app/store/models";

patch(PosStore.prototype, {
    async _processData(loadedData) {
        await super._processData(...arguments);
        this.salesman_ids = loadedData['hr_salesmen'] || [];
    },
});

patch(Order.prototype, {
    setup(_attr, options) {
        super.setup(...arguments);
        this.salesman_id = this.salesman_id || null;
    },
    init_from_JSON(json) {
        super.init_from_JSON(...arguments);
        if (json.salesman_id) {
            // Find salesman in global list
            this.salesman_id = this.pos.salesman_ids.find(s => s.id === json.salesman_id) || null;
        }
    },
    export_as_JSON() {
        const json = super.export_as_JSON(...arguments);
        json.salesman_id = this.salesman_id ? this.salesman_id.id : false;
        return json;
    },
    set_salesman_id(salesman) {
        this.salesman_id = salesman;
    },
    get_salesman_id() {
        return this.salesman_id;
    },
    get_salesman_name() {
        return this.salesman_id ? this.salesman_id.name : "";
    },
});
