from odoo import api, fields, models


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    currency_id_dif = fields.Many2one(
        "res.currency",
        string="Moneda Ref.",
        related="order_id.currency_id_dif",
        store=False, readonly=True
    )

    price_unit_dif = fields.Monetary(
        string='P. Unit. Ref.',
        currency_field='currency_id_dif',
        compute='_compute_price_dif_pol',
        store=False
    )

    price_subtotal_dif = fields.Monetary(
        string='Subtotal Ref.',
        currency_field='currency_id_dif',
        compute='_compute_price_dif_pol',
        store=False
    )

    @api.depends('price_unit', 'price_subtotal', 'order_id.tasa_referencial', 'order_id.currency_id', 'order_id.company_id')
    def _compute_price_dif_pol(self):
        for line in self:
            tasa = line.order_id.tasa_referencial
            if tasa and tasa > 0:
                if line.order_id.currency_id == line.order_id.currency_id_dif:
                    line.price_unit_dif = line.price_unit
                    line.price_subtotal_dif = line.price_subtotal
                else:
                    company = line.order_id.company_id or self.env.company
                    if company.currency_id.name == 'USD':
                        line.price_unit_dif = line.price_unit * tasa
                        line.price_subtotal_dif = line.price_subtotal * tasa
                    else:
                        line.price_unit_dif = line.price_unit / tasa
                        line.price_subtotal_dif = line.price_subtotal / tasa
            else:
                line.price_unit_dif = 0.0
                line.price_subtotal_dif = 0.0

    @api.onchange('date_planned')
    def _onchange_date_planned(self):
        price = self.price_unit
        res = super()._onchange_date_planned() if hasattr(super(PurchaseOrderLine, self), '_onchange_date_planned') else {}
        if self.price_unit != price and price > 0:
            self.price_unit = price
        return res
