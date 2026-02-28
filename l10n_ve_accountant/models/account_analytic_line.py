from odoo import fields, models


class AccountAnalyticLine(models.Model):
    _inherit = "account.analytic.line"

    foreign_amount = fields.Monetary(
        string="Foreign Amount",
        currency_field="foreign_currency_id",
        help="The amount expressed in the foreign currency.",
    )
    foreign_currency_id = fields.Many2one(
        "res.currency", string="Foreign Currency", help="The foreign currency."
    )
