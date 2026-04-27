
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

class Productos(models.Model):
    _inherit = 'product.template'

    currency_id_dif = fields.Many2one('res.currency', string='Moneda Diferente', default=lambda self: self.env.company.currency_id_dif.id)

    list_price_usd = fields.Monetary(string="Precio de venta $", currency_field='currency_id_dif')
    standard_price_usd = fields.Float(string="Costo $", inverse='_set_standard_price_usd', compute='_compute_standard_price_usd')
    costo_reposicion_usd = fields.Monetary(string="Costo Reposición $", currency_field='currency_id_dif')

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
        for rec in self:
            if rec.list_price_usd:
                if rec.list_price_usd >0:
                    tasa = self.env.company.currency_id_dif
                    if tasa:
                        rec.list_price = rec.list_price_usd * tasa.inverse_rate

    @api.onchange('standard_price_usd')
    def _onchange_standard_price_usd(self):
        for rec in self:
            if len(rec.product_variant_ids) == 1:
                rec.product_variant_ids[0].standard_price_usd = rec.standard_price_usd

            if rec.standard_price_usd and rec.categ_id.property_valuation == 'manual_periodic':
                if rec.standard_price_usd > 0:
                    tasa = self.env.company.currency_id_dif
                    if tasa:
                        rec.standard_price = rec.standard_price_usd * tasa.inverse_rate

    @api.depends('taxes_id', 'list_price', 'list_price_usd')
    def _compute_tax_string(self):
        super()._compute_tax_string()
        for template in self:
            if template.tax_string and template.list_price_usd:
                # Obtenemos la tasa actual
                tasa_obj = self.env.company.currency_id_dif
                if not tasa_obj:
                    continue
                
                # Calculamos el precio con impuestos en Bs (usando list_price_usd que es el base en Bs)
                taxes = template.taxes_id.compute_all(template.list_price_usd, tasa_obj, 1, product=template, partner=self.env.user.partner_id)
                total_bs = taxes['total_included']
                
                # Formateamos el monto en Bs
                formatted_bs = "{:,.2f}".format(total_bs).replace(",", "X").replace(".", ",").replace("X", ".")
                
                # Inyectamos en la cadena original
                # Odoo 18 suele usar: "(= $ 1.363,00 impuestos incluidos)"
                if 'impuestos incluidos' in template.tax_string:
                    new_val = f" / Bs. {formatted_bs} impuestos incluidos"
                    template.tax_string = template.tax_string.replace(" impuestos incluidos", new_val)
