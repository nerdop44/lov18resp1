# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, api


class PosSession(models.Model):
    _inherit = 'pos.session'

    def _loader_params_hr_employee(self):
        result = super()._loader_params_hr_employee()
        # Ensure we can search by the IDs in the config
        return result

    def _get_pos_ui_hr_salesmen(self, params):
        return self.env['hr.employee'].search_read(
            [('id', 'in', self.config_id.salesman_ids.ids)],
            ['name', 'id']
        )

    def _pos_data_process(self, loaded_data):
        super()._pos_data_process(loaded_data)
        loaded_data['hr_salesmen'] = self._get_pos_ui_hr_salesmen(None)