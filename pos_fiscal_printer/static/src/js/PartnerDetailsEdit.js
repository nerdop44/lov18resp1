odoo.define('pos_fiscal_printer.PartnerDetailsEditExtra', function(require) {
    'use strict';

    const { _t } = require('web.core');
    const PartnerDetailsEdit = require('point_of_sale.PartnerDetailsEdit');
    const Registries = require('point_of_sale.Registries');
    const { onMounted, useState, onWillUnmount } = owl;
    const PartnerDetailsEditExtra = (PartnerDetailsEdit) => class PartnerDetailsEditExtra extends PartnerDetailsEdit {

        setup() {
            super.setup();
        }

        captureChange(event) {
            console.log(event.target.name);
            console.log(event.target.value);

            this.changes[event.target.name] = event.target.value;

            console.log(this.changes);
            if(event.target.name === 'company_type'){
                this.props.partner.company_type = event.target.value;
            }

        }

        saveChanges() {
            let processedChanges = {};
            console.log(this.changes);
            for (let [key, value] of Object.entries(this.changes)) {
                if (this.intFields.includes(key)) {
                    processedChanges[key] = parseInt(value) || false;
                } else {
                    processedChanges[key] = value;
                }
            }
            console.log(processedChanges);
            if(!processedChanges.company_type){
                processedChanges.company_type = this.props.partner.company_type || 'person';
            }
            processedChanges.id = this.props.partner.id || false;
            console.log(processedChanges);
            this.trigger('save-changes', { processedChanges });
        }

    }
    Registries.Component.extend(PartnerDetailsEdit, PartnerDetailsEditExtra);

    return PartnerDetailsEdit;
});