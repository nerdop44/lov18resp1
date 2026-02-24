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
        
        store=False
    )

    price_subtotal_dif = fields.Monetary(
        string='Subtotal Ref.',
        currency_field='currency_id_dif',
        
        store=False
    )

#     @api.depends('price_unit', 'price_subtotal', 'order_id.tasa_referencial', 'order_id.currency_id')
#     def _compute_price_dif_pol(self):
#         for line in self:
#             tasa = line.order_id.tasa_referencial
#             if tasa and tasa > 0:
#                 if line.order_id.currency_id == line.order_id.currency_id_dif:
#                     line.price_unit_dif = line.price_unit
#                     line.price_subtotal_dif = line.price_subtotal
#                 else:
#                     line.price_unit_dif = line.price_unit / tasa
#                     line.price_subtotal_dif = line.price_subtotal / tasa
#             else:
#                 line.price_unit_dif = 0.0
#                 line.price_subtotal_dif = 0.0
