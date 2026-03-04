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
        if 'salesman_ids' not in result['search_params']['fields']:
            result['search_params']['fields'].append('salesman_ids')
        return result

    def load_data(self, models_to_load, only_data=False):
        response = super().load_data(models_to_load, only_data)
        
        # Odoo 18: Inyectar hr_salesmen en los datos de configuración para evitar TypeError en el loop de modelos del frontend
        salesman_ids = self.config_id.salesman_ids.ids if self.config_id else []
        
        domain = [('id', 'in', salesman_ids)] if salesman_ids else []
        salesmen = self.env['hr.employee'].search_read(
            domain,
            ['name', 'id']
        )
        
        # Inject into config
        if 'pos.config' in response and response['pos.config'].get('data'):
            response['pos.config']['data'][0]['hr_salesmen'] = salesmen
            
        return response