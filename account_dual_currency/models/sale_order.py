from odoo import api, fields, models, _
import logging

_logger = logging.getLogger(__name__)

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    currency_id_dif = fields.Many2one("res.currency",
                                      string="Moneda Dual Ref.",
                                      related="company_id.currency_id_dif",
                                      store=False, readonly=True)
    
    tasa_referencial = fields.Float(string="Tasa Referencial", digits=(16, 4),  store=False)

    amount_total_dif = fields.Monetary(string='Total Ref.', store=False, readonly=True,  currency_field='currency_id_dif')

    amount_untaxed_dif = fields.Monetary(string='Base Ref.', store=False, readonly=True,  currency_field='currency_id_dif')

    amount_tax_dif = fields.Monetary(string='Impuesto Ref.', store=False, readonly=True,  currency_field='currency_id_dif')

    intervalo_tasa = fields.Selection([('diario', 'Diario'), ('semanal', 'Semanal'), ('mensual', 'Mensual')], string='Intervalo de Tasa', default='diario', store=False)
    
#     @api.depends('company_id', 'currency_id_dif')
#     def _compute_tasa_referencial(self):
#         for record in self:
#             dif = record.currency_id_dif or record.company_id.currency_id_dif
#             if dif and dif.inverse_rate:
#                 record.tasa_referencial = dif.inverse_rate
#             else:
#                 record.tasa_referencial = 1.0
# 
#     @api.depends('amount_total', 'amount_untaxed', 'amount_tax', 'tasa_referencial', 'currency_id', 'company_id')
#     def _compute_amount_total_dif(self):
#         today = fields.Date.today()
#         for record in self:
#             dif = record.currency_id_dif or record.company_id.currency_id_dif
#             if not dif:
#                 record.amount_total_dif = 0
#                 record.amount_untaxed_dif = 0
#                 record.amount_tax_dif = 0
#                 continue
#             src = record.currency_id
#             company = record.company_id
#             if src == dif:
#                 record.amount_total_dif = record.amount_total
#                 record.amount_untaxed_dif = record.amount_untaxed
#                 record.amount_tax_dif = record.amount_tax
#             else:
#                 record.amount_total_dif = src._convert(record.amount_total, dif, company, today, round=True)
#                 record.amount_untaxed_dif = src._convert(record.amount_untaxed, dif, company, today, round=True)
#                 record.amount_tax_dif = src._convert(record.amount_tax, dif, company, today, round=True)
# 
# 
#     @api.onchange('currency_id')
#     def _onchange_currency_id(self):
#         # Al cambiar la moneda del pedido, recalcular precios unitarios de lineas
#         if not self.currency_id:
#             return
#         if not self.pricelist_id:
#              return
#         
#         # Simplemente forzar recálculo de lista de precios si cambia moneda
#         self.order_line._compute_price_unit()
