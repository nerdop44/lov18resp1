
from odoo import models, fields, api
from odoo.exceptions import ValidationError
from odoo.tools import float_round
import logging

_logger = logging.getLogger(__name__)

class PosSession(models.Model):
    _inherit = 'pos.session'

    def _loader_params_pos_payment_method(self):
        result = super()._loader_params_pos_payment_method()
        result['search_params']['fields'].extend([
            "x_igtf_percentage",
            "x_is_foreign_exchange",
        ])
        return result

    def _accumulate_amounts(self, data):
        """
        Override para agregar el monto IGTF de las órdenes POS al diccionario 'sales'.
        El IGTF se cobra como pago recibible (add a los receivables) pero su línea de
        crédito de ventas NO se genera automáticamente por _prepare_tax_base_line_values
        porque el x_igtf_amount es un campo calculado, no una línea de producto real.
        Sin esta corrección, el move de sesión queda con más débitos que créditos por
        el monto IGTF total, causando 'The entry is not balanced'.
        """
        data = super()._accumulate_amounts(data)

        # Solo aplicar si el POS está configurado para IGTF
        igtf_product = self.config_id.x_igtf_product_id
        if not igtf_product or not self.config_id.aplicar_igtf:
            return data

        # Cuenta de ingresos del producto IGTF: buscar via jerarquía template→categoría
        # `property_account_income_id` puede estar vacío aunque la categoría tenga cuenta
        product_accounts = igtf_product._get_product_accounts()
        igtf_account = (
            igtf_product.property_account_income_id
            or product_accounts.get('income')
        )
        if not igtf_account:
            _logger.warning("[IGTF] El producto IGTF '%s' no tiene cuenta de ingresos configurada (ni directa ni por categoría). El IGTF no se acumulará en el cierre de sesión.", igtf_product.name)
            return data
        _logger.warning("[IGTF] Usando cuenta de ingresos IGTF: %s (%s)", igtf_account.code, igtf_account.name)

        sales = data.get('sales')
        currency_rounding = self.currency_id.rounding
        closed_orders = self._get_closed_orders()

        _logger.warning("[IGTF] Acumulando IGTF en sales dict. Ordenes cerradas: %s", len(closed_orders))

        for order in closed_orders:
            if order.is_invoiced:
                continue
            igtf_amount = order.x_igtf_amount
            if not igtf_amount:
                continue
            igtf_amount_rounded = float_round(igtf_amount, precision_rounding=currency_rounding)
            if igtf_amount_rounded == 0.0:
                continue

            _logger.warning("[IGTF] Orden %s: x_igtf_amount=%.6f (redondeado=%.6f)", order.name, igtf_amount, igtf_amount_rounded)

            # Clave para agrupar: (account_id, sign, tax_ids, tax_tag_ids, product_id)
            igtf_key = (
                igtf_account.id,
                1,  # sign positivo (venta)
                tuple(),  # sin impuestos (IGTF es exento)
                tuple(),  # sin tags
                igtf_product.id if self.config_id.is_closing_entry_by_product else False,
            )
            sales[igtf_key] = self._update_amounts(
                sales[igtf_key],
                {
                    'amount': igtf_amount_rounded,
                    'amount_converted': igtf_amount_rounded,
                },
                order.date_order,
            )

        _logger.warning("[IGTF] Acumulación completada. Keys en sales: %s", list(sales.keys()))
        return data


class PosOrder(models.Model):
    _inherit = "pos.order"

    x_igtf_amount = fields.Monetary("Monto IGTF", compute="_compute_x_igtf_amount", store=True)

    @api.depends("lines.x_is_igtf_line", "lines.price_subtotal_incl")
    def _compute_x_igtf_amount(self):
        for rec in self:
            rec.x_igtf_amount = sum(rec.lines.filtered("x_is_igtf_line").mapped("price_subtotal_incl"))

    def _get_fields_for_order_line(self):
        fields = super()._get_fields_for_order_line()

        fields.append('x_is_igtf_line')
        
        return fields
        
class PosOrderLine(models.Model):
    _inherit = "pos.order.line"

    x_is_igtf_line = fields.Boolean("Linea IGTF")

    @api.model
    def _load_pos_data_fields(self, config_id):
        return super()._load_pos_data_fields(config_id) + ['x_is_igtf_line']

    def _order_line_fields(self, line, session_id):
        result = super()._order_line_fields(line, session_id)
        vals = result[2]

        vals["x_is_igtf_line"] = vals.get("x_is_igtf_line", line[2].get("x_is_igtf_line", False))

        return result

    def _export_for_ui(self, orderline):
        res = super()._export_for_ui(orderline)

        res["x_is_igtf_line"] = orderline.x_is_igtf_line

        return res

class PosPaymentMethod(models.Model):
    _inherit = "pos.payment.method"

    x_igtf_percentage = fields.Float("Porcentaje de IGTF", compute="_compute_x_igtf_percentage", store=True, readonly=False)
    x_is_foreign_exchange = fields.Boolean("Pago en divisas")

    @api.depends('x_is_foreign_exchange', 'company_id.igtf_percentage')
    def _compute_x_igtf_percentage(self):
        for rec in self:
            if rec.x_is_foreign_exchange and not rec.x_igtf_percentage:
                rec.x_igtf_percentage = rec.company_id.igtf_percentage or 3.0
            elif not rec.x_is_foreign_exchange:
                rec.x_igtf_percentage = 0.0
            else:
                rec.x_igtf_percentage = rec.x_igtf_percentage

    @api.model
    def _load_pos_data_fields(self, config_id):
        return super()._load_pos_data_fields(config_id) + ['x_igtf_percentage', 'x_is_foreign_exchange']

    @api.constrains("x_igtf_percentage")
    def _check_x_igtf_percentage(self):
        for rec in self:
            if rec.x_igtf_percentage < 0 and rec.x_is_foreign_exchange:
                raise ValidationError("El porcentage IGTF debe ser mayor a cero")

class PosConfig(models.Model):
    _inherit = "pos.config"

    x_igtf_product_id = fields.Many2one("product.product", "Producto IGTF")

    aplicar_igtf = fields.Boolean("Aplicar IGTF", default=False)

class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    pos_x_igtf_product_id = fields.Many2one(
        string="Producto IGTF", 
        related="pos_config_id.x_igtf_product_id",
        readonly=False,
    )

    aplicar_igtf = fields.Boolean(related="pos_config_id.aplicar_igtf", readonly=False)

    @api.constrains("pos_x_igtf_product_id")
    def _check_pos_x_igtf_product_id(self):
        for rec in self.filtered("pos_x_igtf_product_id"):
            if not rec.pos_x_igtf_product_id.property_account_income_id:
                raise ValidationError("El producto IGTF debe tener una cuenta de ingresos configurada")
            if sum(rec.pos_x_igtf_product_id.taxes_id.mapped("amount")) != 0:
                raise ValidationError("El producto IGTF debe ser exento")
