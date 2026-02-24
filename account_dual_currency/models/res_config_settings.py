from odoo import api, fields, models, _


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    currency_id_dif = fields.Many2one("res.currency",  string="Moneda Dual Ref.", readonly=False)

