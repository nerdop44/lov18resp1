
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

class Productos(models.Model):
    _inherit = 'product.template'

    currency_id_dif = fields.Many2one('res.currency', string='Moneda Diferente', compute='_compute_currency_id_dif')

    def _compute_currency_id_dif(self):
        for rec in self:
            rec.currency_id_dif = self.env.company.currency_id_dif.id


    list_price = fields.Float(string="Precio de Venta en $")
    list_price_usd = fields.Monetary(string="Precio Alterno", currency_field='currency_id_dif')
    standard_price_usd = fields.Float(string="Costo Alterno", inverse='_set_standard_price_usd', compute='_compute_standard_price_usd')
    costo_reposicion_usd = fields.Monetary(string="Costo Reposición Alterno", currency_field='currency_id_dif')

    def _set_standard_price_usd(self):
        for template in self:
            if len(template.product_variant_ids) == 1:
                template.product_variant_ids.standard_price_usd = template.standard_price_usd

    @api.depends_context('company')
    @api.depends('product_variant_ids', 'product_variant_ids.standard_price_usd')
    def _compute_standard_price_usd(self):
        # Depends on force_company context because standard_price is company_dependent
        # on the product_product
        unique_variants = self.filtered(lambda template: len(template.product_variant_ids) == 1)
        for template in unique_variants:
            template.standard_price_usd = template.product_variant_ids.standard_price_usd
        for template in (self - unique_variants):
            template.standard_price_usd = 0.0

    @api.onchange('list_price_usd')
    def _onchange_list_price_usd(self):
        pass

    @api.onchange('list_price')
    def _onchange_list_price_sync_bs(self):
        for rec in self:
            company = self.env.company
            tasa = company.currency_id_dif.get_trm_systray() if company.currency_id_dif else 0.0
            if tasa > 0:
                rec.list_price_usd = rec.list_price * tasa
            else:
                rec.list_price_usd = 0.0

    @api.onchange('standard_price_usd')
    def _onchange_standard_price_usd(self):
        for rec in self:
            if len(rec.product_variant_ids) == 1:
                rec.product_variant_ids[0].standard_price_usd = rec.standard_price_usd

    @api.onchange('standard_price')
    def _onchange_standard_price_sync_bs(self):
        for rec in self:
            company = self.env.company
            tasa = company.currency_id_dif.get_trm_systray() if company.currency_id_dif else 0.0
            if tasa > 0:
                # Assuming standard_price is the base (Bs) and standard_price_usd is the alternate ($)
                rec.standard_price_usd = rec.standard_price / tasa
            else:
                rec.standard_price_usd = 0.0



