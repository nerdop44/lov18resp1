/** @odoo-module */

import { patch } from "@web/core/utils/patch";

import { PosStore } from "@point_of_sale/app/store/pos_store";
import { PosOrder } from "@point_of_sale/app/models/pos_order";

import { PosData } from "@point_of_sale/app/models/data_service";

patch(PosData.prototype, {
    async loadInitialData() {
        const response = await super.loadInitialData(...arguments);
        if (response && response.hr_salesmen) {
            this.hr_salesmen = response.hr_salesmen;
        }
        return response;
    }
});

patch(PosStore.prototype, {
    setup() {
        super.setup(...arguments);
        this.salesman_ids = this.salesman_ids || [];
    },
    async processData(loadedData) {
        await super.processData(...arguments);
        this.salesman_ids = loadedData['hr_salesmen'] || this.data.hr_salesmen || [];
    },
});

patch(PosOrder.prototype, {
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
