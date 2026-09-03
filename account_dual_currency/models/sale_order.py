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

        company = self.company_id
        usd_curr = self.env.ref('base.USD', raise_if_not_found=False) or self.env['res.currency'].search([('name', '=', 'USD')], limit=1)
        vef_curr = self.currency_id_dif or company.currency_id_dif

        # 1. Buscar primero en USD donde se guardan los factores odoo (ej. 0.00127377)
        if usd_curr:
            rate_rec_usd = self.env['res.currency.rate'].search([
                ('currency_id', '=', usd_curr.id),
                ('company_id', '=', company.id),
                ('name', '<=', target_date)
            ], order='name desc, id desc', limit=1)

            if rate_rec_usd and rate_rec_usd.rate > 0 and rate_rec_usd.rate != 1.0:
                rate_val = rate_rec_usd.rate
                return rate_val if rate_val >= 1.0 else (1.0 / rate_val)

        # 2. Si USD no tiene factor o es 1.0, buscar en VEF donde se guarda la tasa directa (ej. 804.8109)
        if vef_curr:
            rate_rec_vef = self.env['res.currency.rate'].search([
                ('currency_id', '=', vef_curr.id),
                ('company_id', '=', company.id),
                ('name', '<=', target_date)
            ], order='name desc, id desc', limit=1)

            if rate_rec_vef and rate_rec_vef.rate > 0:
                rate_val = rate_rec_vef.rate
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

    def _recompute_prices(self):
        """Proteger precios unitarios contra recálculo automático por pricelist.
        Solo recalcular si se fuerza explícitamente con context force_pricelist_recalc."""
        if not self.env.context.get('force_pricelist_recalc'):
            current_prices = {line.id: line.price_unit for line in self.order_line if line.id}
            res = super()._recompute_prices()
            for line in self.order_line:
                if line.id in current_prices:
                    line.price_unit = current_prices[line.id]
            return res
        return super()._recompute_prices()

    @api.onchange('pricelist_id', 'partner_id')
    def _onchange_pricelist_partner_force(self):
        self = self.with_context(force_pricelist_recalc=True)
        return super(SaleOrder, self)._onchange_pricelist_id() if hasattr(super(SaleOrder, self), '_onchange_pricelist_id') else {}

    def _prepare_invoice(self):
        invoice_vals = super(SaleOrder, self)._prepare_invoice()
        company = self.company_id or self.env.company

        tasa_a_usar = self.tasa_referencial or 0.0
        if not tasa_a_usar or tasa_a_usar <= 0:
            currency_dif = company.currency_id_dif
            if currency_dif:
                tasa_a_usar = currency_dif.rate if company.currency_id.name == 'USD' else currency_dif.inverse_rate
            else:
                tasa_a_usar = 1.0

        # Garantizar tasa >= 1.0
        if 0.0 < tasa_a_usar < 1.0:
            tasa_a_usar = 1.0 / tasa_a_usar

        invoice_vals['tax_today'] = tasa_a_usar
        invoice_vals['tax_today_edited'] = True
        invoice_vals['foreign_rate'] = tasa_a_usar
        if company.currency_id.name == 'USD':
            invoice_vals['foreign_inverse_rate'] = tasa_a_usar
        else:
            invoice_vals['foreign_inverse_rate'] = 1.0 / tasa_a_usar if tasa_a_usar > 0 else 1.0

        return invoice_vals
