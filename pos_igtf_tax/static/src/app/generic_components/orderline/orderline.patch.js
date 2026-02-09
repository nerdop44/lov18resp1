/** @odoo-module */

import { Orderline } from "@point_of_sale/app/generic_components/orderline/orderline";
import { patch } from "@web/core/utils/patch";
import { onMounted } from "@odoo/owl";

patch(Orderline.prototype, {
    setup() {
        super.setup();

        onMounted(() => {
            // Check if line (from props) is IGTF line
            // In Odoo 18 Orderline props usually contains `line` (the model).
            if (this.props.line.x_is_igtf_line) {
                // this.el is the component execution context element? 
                // Owl Components have `this.el` after mount? 
                // Often we reference `this.root` or useRef.
                // Standard Odoo `setup` with `onMounted` allows accessing `this.el` if template has single root.
                if (this.el) {
                    this.el.classList.add("igtf-line");
                }
            }
        });
    }
});
