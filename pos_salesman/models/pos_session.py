# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, api


class PosSession(models.Model):
    _inherit = 'pos.session'

    def _loader_params_hr_employee(self):
        result = super()._loader_params_hr_employee()
        # Add basic fields for salesmen
        result['search_params']['fields'].extend(['name', 'id'])
        return result

    def _get_pos_ui_hr_salesmen(self, params):
        # Filter employees by config salesman_ids
        return self.env['hr.employee'].search_read(
            [('id', 'in', self.config_id.salesman_ids.ids)],
            ['name', 'id']
        )

    def _loader_params_pos_config(self):
        result = super()._loader_params_pos_config()
        result['search_params']['fields'].append('salesman_ids')
        return result

    @api.model
    def _load_pos_data(self, data):
        result = super()._load_pos_data(data)
        # Force injection into root and into config just in case
        salesmen = self._get_pos_ui_hr_salesmen(None)
        result['hr_salesmen'] = salesmen
        
        if 'pos.config' in result and result['pos.config']['data']:
            result['pos.config']['data'][0]['hr_salesmen'] = salesmen
            
        return result