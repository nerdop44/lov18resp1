
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # pos.config fields
    pos_salesman_ids = fields.Many2many(related='pos_config_id.salesman_ids', readonly=False)
