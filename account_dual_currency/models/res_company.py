from odoo import api, fields, models, _, Command

class ResCompany(models.Model):
    _inherit = "res.company"

    currency_id_dif = fields.Many2one("res.currency",
                                      string="Moneda Dual Ref.",
                                      default=lambda self: self.env['res.currency'].search([('name', '=', 'USD')],
                                                                                           limit=1), )
    igtf_divisa_porcentage = fields.Float(string='Porcentaje IGTF', default=3.0)