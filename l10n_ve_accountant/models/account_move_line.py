import inspect
from odoo import api, fields, models, Command, _
from odoo.tools import float_compare
from odoo.exceptions import UserError, ValidationError
from odoo.tools import frozendict, formatLang, format_date, float_compare, Query
from datetime import date, timedelta
import traceback

import logging

_logger = logging.getLogger(__name__)


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    not_foreign_recalculate = fields.Boolean()
    foreign_currency_id = fields.Many2one(
        related="move_id.foreign_currency_id", store=True
    )
    foreign_rate = fields.Float( store=True)
    foreign_inverse_rate = fields.Float(
        related="move_id.foreign_inverse_rate", store=True, index=True
    )

    foreign_price = fields.Float(
        help="Foreign Price of the line",
        
        digits="Foreign Product Price",
        store=True,
        readonly=False,
    )
    foreign_subtotal = fields.Monetary(
        help="Foreign Subtotal of the line",
        
        currency_field="foreign_currency_id",
        store=True,
    )
    foreign_price_total = fields.Monetary(
        help="Foreign Total of the line",
        
        currency_field="foreign_currency_id",
        store=True,
    )
    amount_currency = fields.Monetary(pre)

    # Report fields
    foreign_debit = fields.Monetary(
        currency_field="foreign_currency_id",
        
        store=True,
    )
    foreign_credit = fields.Monetary(
        currency_field="foreign_currency_id",
        
        store=True,
    )
    foreign_balance = fields.Monetary(
        currency_field="foreign_currency_id",
        
        inverse="_inverse_foreign_balance",
        store=True,
    )

    foreign_debit_adjustment = fields.Monetary(
        currency_field="foreign_currency_id",
        help="When setted, this field will be used to fill the foreign debit field",
    )
    foreign_credit_adjustment = fields.Monetary(
        currency_field="foreign_currency_id",
        help="When setted, this field will be used to fill the foreign credit field",
    )

#     @api.onchange("amount_currency", "currency_id")
#     def _inverse_amount_currency(self):
#         for line in self:
#             if (
#                 line.currency_id == line.company_id.currency_id
#                 and line.balance != line.amount_currency
#             ):
#                 line.balance = line.amount_currency
#             elif (
#                 line.currency_id != line.company_id.currency_id
#                 and not line.move_id.is_invoice(True)
#                 and not self.env.is_protected(self._fields["balance"], line)
#             ):
#                 rate = (
#                     line.foreign_inverse_rate
#                     if line.currency_id
#                     in (self.env.ref("base.VEF"), self.env.ref("base.USD"))
#                     else line.currency_rate
#                 )
#                 line.balance = line.company_id.currency_id.round(
#                     line.amount_currency / rate
#                 )
#             elif (
#                 line.currency_id != line.company_id.currency_id
#                 and not line.move_id.is_invoice(True)
#                 and line.move_id.payment_id
#             ):
#                 if (
#                     line.move_id.payment_id.foreign_inverse_rate != 0
#                     and line.amount_currency != 0
#                 ):
#                     line.balance = line.company_id.currency_id.round(
#                         line.amount_currency
#                         / line.move_id.payment_id.foreign_inverse_rate
#                     )
#                 else:
#                     raise UserError(_("The rate should be greater than zero"))
# 
#     @api.depends("product_id", "move_id.name")
#     def _compute_name(self):
#         lines_without_name = self.filtered(lambda l: not l.name)
#         res = super(AccountMoveLine, lines_without_name)._compute_name()
#         for line in self.filtered(
#             lambda l: l.move_type in ("out_invoice", "out_receipt")
#             and l.account_id.account_type == "asset_receivable"
#         ):
#             line.name = line.move_id.name
#         return res
# 
#     @api.depends("price_unit", "foreign_inverse_rate")
#     def _compute_foreign_price(self):
#         for line in self:
#             line.foreign_price = line.price_unit * line.foreign_inverse_rate
# 
#     @api.depends("foreign_price", "quantity", "discount", "tax_ids", "price_unit")
#     def _compute_foreign_subtotal(self):
#         for line in self:
#             line_discount_price_unit = line.foreign_price * (
#                 1 - (line.discount / 100.0)
#             )
#             foreign_subtotal = line_discount_price_unit * line.quantity
# 
#             if line.tax_ids:
#                 taxes_res = line.tax_ids.compute_all(
#                     line_discount_price_unit,
#                     quantity=line.quantity,
#                     currency=line.foreign_currency_id,
#                     product=line.product_id,
#                     partner=line.partner_id,
#                     is_refund=line.is_refund,
#                 )
#                 line.foreign_subtotal = taxes_res["total_excluded"]
#                 line.foreign_price_total = taxes_res["total_included"]
#             else:
#                 line.foreign_price_total = line.foreign_subtotal = foreign_subtotal
# 
#     @api.depends(
#         "debit",
#         "credit",
#         "foreign_subtotal",
#         "foreign_balance",
#         "amount_currency",
#         "not_foreign_recalculate",
#         "foreign_debit_adjustment",
#         "foreign_credit_adjustment",
#     )
#     def _compute_foreign_debit_credit(self):
#         for line in self:
#             if line.not_foreign_recalculate:
#                 continue
# 
#             if line.display_type in ("payment_term", "tax"):
#                 line.foreign_debit = (
#                     abs(line.foreign_balance) if line.foreign_balance > 0 else 0.0
#                 )
#                 line.foreign_credit = (
#                     abs(line.foreign_balance) if line.foreign_balance < 0 else 0.0
#                 )
#                 # 1 Case: Payment Term
#                 # In this case, we don't want to calculate the foreign debit and credit
#                 continue
# 
#             if line.display_type in ("line_section", "line_note"):
#                 line.foreign_debit = line.foreign_credit = 0.0
#                 # 2 Case: not Product
#                 # In this case, we don't want to calculate the foreign debit and credit
#                 continue
# 
#             if line.foreign_debit_adjustment:
#                 line.foreign_debit = abs(line.foreign_debit_adjustment)
#                 # 3 Case: Foreign Debit Adjustment
#                 # In this case, we need to set the foreign debit manually
#                 continue
# 
#             if line.foreign_credit_adjustment:
#                 line.foreign_credit = abs(line.foreign_credit_adjustment)
#                 # 4 Case: Foreign Credit Adjustment
#                 # In this case, we need to set the foreign credit manually
#                 continue
# 
#             if (
#                 line.currency_id == line.company_id.currency_foreign_id
#                 and line.amount_currency
#             ):
#                 line.foreign_debit = (
#                     abs(line.amount_currency) if line.amount_currency > 0 else 0.0
#                 )
#                 line.foreign_credit = (
#                     abs(line.amount_currency) if line.amount_currency < 0 else 0.0
#                 )
#                 continue
# 
#             
#                     if not key.get("tax_repartition_line_id", False):
#                         continue
# 
#                     if tax["tax_repartition_line_id"] == key["tax_repartition_line_id"]:
#                         line.compute_all_tax[key]["foreign_balance"] = tax["amount"]
#         return res
# 
#     @api.onchange("quantity")
#     def _onchange_quantity(self):
#         if self.quantity < 0:
#             raise ValidationError(_("The quantity entered cannot be negative"))
# 
#     @api.onchange("price_unit")
#     def _onchange_price_unit(self):
#         if self.price_unit < 0:
#             raise ValidationError(_("The price entered cannot be negative"))
