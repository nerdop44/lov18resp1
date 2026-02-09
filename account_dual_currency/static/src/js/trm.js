/** @odoo-module **/
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, onWillStart, useState } from "@odoo/owl";

class TRM extends Component {
    static props = { "*": true };
    setup() {
        this.state = useState({ trm: 0 });
        this.orm = useService('orm');

        onWillStart(async () => {
            console.log('TRM: Fetching rate...');
            try {
                // Call the model method without arguments
                var trm = await this.orm.call('res.currency', 'get_trm_systray', []);
                console.log('TRM: Rate received', trm);
                this.state.trm = trm;
            } catch (e) {
                console.error('TRM: Error fetching rate', e);
            }
        });
    }

    get trm() {
        return this.state.trm;
    }
}

TRM.template = "trm_menu";
export const trmItem = { Component: TRM };

registry.category("systray").add("TRM", trmItem, { sequence: 1 });
