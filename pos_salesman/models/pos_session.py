# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, api


class PosSession(models.Model):
    _inherit = 'pos.session'

    @api.model
    def _load_pos_data(self, data):
        loaded_data = super()._load_pos_data(data)
        # En Odoo 18, self es el registro de pos.session
        salesmen = self.env['hr.employee'].search_read(
            [('id', 'in', self.config_id.salesman_ids.ids)],
            ['name', 'id']
        )
        loaded_data['hr_salesmen'] = salesmen
        return loaded_data