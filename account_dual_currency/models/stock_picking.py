from odoo import models, fields
from datetime import datetime
from odoo.exceptions import UserError

class StockPicking(models.Model):
    _inherit = "stock.picking"

    date_of_transfer = fields.Date(string="Effective Date", default=False)
