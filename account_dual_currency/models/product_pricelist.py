from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools import float_is_zero, float_repr

class ProductPricelist(models.Model):
    _inherit = 'product.pricelist'

    pricelist_bs_id = fields.Many2one('product.pricelist', string='Lista en Bs', help='Lista de precios en Bolivares')