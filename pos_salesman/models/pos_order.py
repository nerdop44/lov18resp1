from odoo import models, fields, api, tools, _
from odoo.exceptions import UserError

class PosOrder(models.Model):
    _inherit = 'pos.order'

    salesman_id = fields.Many2one('hr.employee', string='Vendedor', readonly="1", force_save="1")


    def _order_fields(self, ui_order):
        order_fields = super(PosOrder, self)._order_fields(ui_order)
        order_fields['salesman_id'] = ui_order.get('salesman_id')
        return order_fields

    def _export_for_ui(self, order):
        result = super(PosOrder, self)._export_for_ui(order)
        result.update({
            'salesman_id': order.salesman_id.id,
        })
        return result


class PosOrderLine(models.Model):
    _inherit = 'pos.order.line'

    salesman_id = fields.Many2one('hr.employee', string='Vendedor', related='order_id.salesman_id')
