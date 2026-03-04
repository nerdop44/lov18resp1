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

    @api.model
    def _load_pos_data(self, data):
        result = super()._load_pos_data(data)
        
        # En Odoo 18, `_load_pos_data` puede llamarse como @api.model, por tanto `self` puede estar vacío.
        # Extraemos la sesión y configuración desde el diccionario `result` inyectado por `super()`.
        salesman_ids = []
        if 'pos.config' in result and result['pos.config']['data']:
             config_data = result['pos.config']['data'][0]
             salesman_ids = config_data.get('salesman_ids', [])
             
        # Cargar todos los empleados si no hay vendedores restringidos a esta tienda,
        # o solo los vendedores configurados.
        domain = [('id', 'in', salesman_ids)] if salesman_ids else []
        salesmen = self.env['hr.employee'].search_read(
            domain,
            ['name', 'id']
        )
        
        # Force injection into root and into config just in case
        result['hr_salesmen'] = salesmen
        
        if 'pos.config' in result and result['pos.config']['data']:
            result['pos.config']['data'][0]['hr_salesmen'] = salesmen
            
        return result