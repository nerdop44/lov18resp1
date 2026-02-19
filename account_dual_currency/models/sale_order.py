from odoo import api, fields, models, _
import logging

_logger = logging.getLogger(__name__)

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    currency_id_dif = fields.Many2one("res.currency",
                                      string="Moneda Dual Ref.",
                                      default=lambda self: self.env['res.currency'].search([('name', '=', 'USD')], limit=1),
                                      readonly=True)
    
    tasa_referencial = fields.Float(string="Tasa Referencial", digits=(16, 4), compute='_compute_tasa_referencial', store=True)

    amount_total_dif = fields.Monetary(string='Total Ref.', store=True, readonly=True, compute='_compute_amount_total_dif', currency_field='currency_id_dif')

    amount_untaxed_dif = fields.Monetary(string='Base Ref.', store=True, readonly=True, compute='_compute_amount_total_dif', currency_field='currency_id_dif')

    amount_tax_dif = fields.Monetary(string='Impuesto Ref.', store=True, readonly=True, compute='_compute_amount_total_dif', currency_field='currency_id_dif')

    intervalo_tasa = fields.Selection([('diario', 'Diario'), ('semanal', 'Semanal'), ('mensual', 'Mensual')], string='Intervalo de Tasa', default='diario')
    
    @api.depends('company_id')
    def _compute_tasa_referencial(self):
        for record in self:
            # Lógica básica: obtener tasa inversa de la moneda de referencia de la compañía
            # Asumiendo que currency_id_dif es la moneda secundaria configurada en la compañía
            if record.currency_id_dif:
                 record.tasa_referencial = record.currency_id_dif.inverse_rate
            else:
                 record.tasa_referencial = 1.0

    @api.depends('amount_total', 'tasa_referencial', 'currency_id')
    def _compute_amount_total_dif(self):
        for record in self:
            if record.tasa_referencial and record.tasa_referencial > 0:
                 # Si la moneda del pedido es la misma que la ref, es 1:1 (no debería pasar mucho si la ref es diff)
                 if record.currency_id == record.currency_id_dif:
                     record.amount_total_dif = record.amount_total
                     record.amount_untaxed_dif = record.amount_untaxed
                     record.amount_tax_dif = record.amount_tax
                 else:
                     # Si la moneda del pedido es Bs, dividimos por tasa para tener Ref (USD)
                     # OJO: La logica de conversion depende de como esté tasa_referencial.
                     # Si tasa_referencial = Bs/USD (ej 40), y Amount es Bs.
                     # Amount Ref = Amount Bs / Tasa
                     record.amount_total_dif = record.amount_total / record.tasa_referencial
                     record.amount_untaxed_dif = record.amount_untaxed / record.tasa_referencial
                     record.amount_tax_dif = record.amount_tax / record.tasa_referencial
            else:
                 record.amount_total_dif = 0
                 record.amount_untaxed_dif = 0
                 record.amount_tax_dif = 0

    @api.onchange('currency_id')
    def _onchange_currency_id(self):
        # Al cambiar la moneda del pedido, recalcular precios unitarios de lineas
        if not self.currency_id:
            return
        if not self.pricelist_id:
             return
        
        # Simplemente forzar recálculo de lista de precios si cambia moneda
        self.order_line._compute_price_unit()
