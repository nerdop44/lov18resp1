from odoo import api, fields, models, _
import logging

_logger = logging.getLogger(__name__)

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    currency_id_dif = fields.Many2one("res.currency",
                                      string="Moneda Dual Ref.",
                                      related="company_id.currency_id_dif",
                                      store=False, readonly=True)
    
    tasa_referencial = fields.Float(string="Tasa Referencial", digits=(16, 4), compute='_compute_tasa_referencial', store=False)

    amount_total_dif = fields.Monetary(string='Total Ref.', store=False, readonly=True, compute='_compute_amount_total_dif', currency_field='currency_id_dif')

    amount_untaxed_dif = fields.Monetary(string='Base Ref.', store=False, readonly=True, compute='_compute_amount_total_dif', currency_field='currency_id_dif')

    amount_tax_dif = fields.Monetary(string='Impuesto Ref.', store=False, readonly=True, compute='_compute_amount_total_dif', currency_field='currency_id_dif')

    intervalo_tasa = fields.Selection([('diario', 'Diario'), ('semanal', 'Semanal'), ('mensual', 'Mensual')], string='Intervalo de Tasa', default='diario', store=False)
    
    def _get_tasa_for_date(self, target_date=None):
        self.ensure_one()
        if not target_date:
            target_date = fields.Date.context_today(self)
        elif hasattr(target_date, 'date'):
            target_date = target_date.date()

        dif = self.currency_id_dif or self.company_id.currency_id_dif
        if not dif:
            return 1.0
        
        # Buscar tasa registrada en la fecha objetivo o fecha anterior más reciente
        rate_rec = self.env['res.currency.rate'].search([
            ('company_id', '=', self.company_id.id),
            ('name', '<=', target_date)
        ], order='name desc, id desc', limit=1)
        
        if rate_rec and rate_rec.rate > 0:
            rate_val = rate_rec.rate
            return rate_val if rate_val >= 1.0 else (1.0 / rate_val)
        return 1.0

    @api.depends('company_id', 'currency_id_dif', 'date_order')
    def _compute_tasa_referencial(self):
        for record in self:
            record.tasa_referencial = record._get_tasa_for_date(record.date_order)

    @api.depends('amount_total', 'amount_untaxed', 'amount_tax', 'tasa_referencial', 'currency_id', 'company_id', 'date_order')
    def _compute_amount_total_dif(self):
        for record in self:
            dif = record.currency_id_dif or record.company_id.currency_id_dif
            if not dif or not record.tasa_referencial:
                record.amount_total_dif = 0
                record.amount_untaxed_dif = 0
                record.amount_tax_dif = 0
                continue
            src = record.currency_id
            if src == dif:
                record.amount_total_dif = record.amount_total
                record.amount_untaxed_dif = record.amount_untaxed
                record.amount_tax_dif = record.amount_tax
            else:
                rate = record.tasa_referencial
                record.amount_untaxed_dif = round(record.amount_untaxed * rate, 2)
                record.amount_tax_dif = round(record.amount_tax * rate, 2)
                record.amount_total_dif = record.amount_untaxed_dif + record.amount_tax_dif

    @api.onchange('date_order', 'currency_id')
    def _onchange_date_order_tasa(self):
        if self.date_order:
            target_date = self.date_order.date()
            self.tasa_referencial = self._get_tasa_for_date(target_date)
            self._compute_amount_total_dif()

    @api.onchange('currency_id')
    def _onchange_currency_id(self):
        # Al cambiar la moneda del pedido, recalcular precios unitarios de lineas
        if not self.currency_id:
            return
        if not self.pricelist_id:
             return
        
        # Simplemente forzar recálculo de lista de precios si cambia moneda
        self.order_line._compute_price_unit()

    def _prepare_invoice(self):
        invoice_vals = super(SaleOrder, self)._prepare_invoice()
        if self.tasa_referencial and self.tasa_referencial > 0:
            invoice_vals['tax_today'] = self.tasa_referencial
            invoice_vals['tax_today_edited'] = True
        return invoice_vals
