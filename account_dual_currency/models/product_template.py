
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

class Productos(models.Model):
    _inherit = 'product.template'

    currency_id_dif = fields.Many2one('res.currency', string='Moneda Diferente', compute='_compute_currency_id_dif')

    def _compute_currency_id_dif(self):
        for rec in self:
            rec.currency_id_dif = self.env.company.currency_id_dif.id

    cost_currency_id = fields.Many2one('res.currency', string="Moneda de Costo", compute='_compute_cost_currency_id')

    def _compute_cost_currency_id(self):
        for rec in self:
            # En Venezuela, si el maestro es USD, el costo alterno/precio alterno es Bs.
            ves = self.env['res.currency'].search([('name', 'in', ['VES', 'VEF'])], limit=1)
            rec.cost_currency_id = ves.id if ves else self.env.company.currency_id.id


    list_price_usd = fields.Float(string="Precio de Venta en $")
    standard_price_usd = fields.Float(string="Costo en Bs.", compute='_compute_standard_price_usd')
    list_price = fields.Float(
        'Sales Price', default=1.0,
        digits='Product Price',
        help="Price at which the product is sold to customers.",
        compute='_compute_list_price', store=True, readonly=True
    )
    price_with_tax_info = fields.Char(compute='_compute_price_with_tax_info')

    @api.depends('list_price_usd')
    def _compute_list_price(self):
        for rec in self:
            company = rec.env.company
            tasa = company.currency_id_dif.get_trm_systray() if company.currency_id_dif else 0.0
            rec.list_price = rec.list_price_usd * tasa if tasa > 0 else 0.0

    @api.depends('list_price_usd', 'list_price', 'taxes_id')
    def _compute_price_with_tax_info(self):
        for rec in self:
            total_usd = rec.list_price_usd
            total_bs = rec.list_price
            if rec.taxes_id:
                try:
                    res_usd = rec.taxes_id.compute_all(rec.list_price_usd, quantity=1, product=rec)
                    total_usd = res_usd['total_included']
                    res_bs = rec.taxes_id.compute_all(rec.list_price, quantity=1, product=rec)
                    total_bs = res_bs['total_included']
                except Exception:
                    pass
            rec.price_with_tax_info = f"(= $ {total_usd:,.2f} / Bs. {total_bs:,.2f} impuestos incluidos)".replace(',', 'X').replace('.', ',').replace('X', '.')
    costo_reposicion_usd = fields.Monetary(string="Costo Reposición Alterno", currency_field='currency_id_dif')

    def _set_standard_price_usd(self):
        pass # Inhabilitado porque ahora standard_price (USD) es el maestro

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

    # Removed old compute for list_price_usd as it is now the master field

    def _inverse_list_price_usd(self):
        # Inhabilitado para evitar bucles. El precio base en USD es el maestro.
        pass

    @api.onchange('standard_price_usd')
    def _onchange_standard_price_usd(self):
        pass

    @api.onchange('standard_price')
    def _onchange_standard_price_sync_bs(self):
        # Inhabilitado para evitar bucles.
        pass




