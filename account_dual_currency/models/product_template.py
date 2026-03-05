
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
        ves = self.env['res.currency'].search([('name', 'in', ['VES', 'VEF'])], limit=1)
        if not ves:
            # Fallback a buscar por símbolo si el nombre falló
            ves = self.env['res.currency'].search([('symbol', 'ilike', 'Bs')], limit=1)
        for rec in self:
            rec.cost_currency_id = ves.id if ves else rec.env.company.currency_id.id


    list_price_usd = fields.Float(string="Precio Venta ($)")
    standard_price_bs = fields.Monetary(string="Costo en Bs.", compute='_compute_standard_price_bs', currency_field='cost_currency_id')
    list_price_bs = fields.Monetary(string="Venta en Bs.", compute='_compute_list_price_bs', currency_field='cost_currency_id')
    
    list_price = fields.Float(
        'Sales Price', default=1.0,
        digits='Product Price',
        help="Price at which the product is sold to customers.",
        compute='_compute_list_price', store=True, readonly=True
    )
    price_with_tax_info = fields.Char(compute='_compute_price_with_tax_info')

    @api.depends('list_price_usd', 'taxes_id')
    def _compute_list_price(self):
        for rec in self:
            company = rec.env.company
            tasa = company.currency_id_dif.get_trm_systray() if company.currency_id_dif else 0.0
            price_ex_tax = rec.list_price_usd * tasa if tasa > 0 else 0.0
            
            # El usuario solicitó que list_price sea list_price_usd * tasa * taxes_id
            if rec.taxes_id:
                res = rec.taxes_id.compute_all(price_ex_tax, quantity=1, product=rec)
                rec.list_price = res['total_included']
            else:
                rec.list_price = price_ex_tax

    @api.depends('list_price')
    def _compute_list_price_bs(self):
        for rec in self:
            rec.list_price_bs = rec.list_price

    @api.depends('standard_price', 'currency_id_dif')
    def _compute_standard_price_bs(self):
        for rec in self:
            company = rec.env.company
            tasa = company.currency_id_dif.get_trm_systray() if company.currency_id_dif else 0.0
            rec.standard_price_bs = rec.standard_price * tasa if tasa > 0 else 0.0

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
    @api.depends('product_variant_ids', 'product_variant_ids.standard_price')
    def _compute_standard_price_usd(self):
        # Este método ya no es necesario para standard_price_usd (ahora standard_price_bs)
        # pero mantenemos la firma si es referenciada en otros lados, vacía.
        pass

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




