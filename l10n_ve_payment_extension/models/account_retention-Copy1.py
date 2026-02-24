from odoo import api, models, fields, Command, _
from datetime import datetime
from odoo.exceptions import UserError, ValidationError
from ..utils.utils_retention import load_retention_lines, search_invoices_with_taxes
from collections import defaultdict
import json
from odoo.tools.float_utils import float_round
import logging

_logger = logging.getLogger(__name__)


class AccountRetention(models.Model):
    _name = "account.retention"
    _description = "Retention"
    _check_company_auto = True

    company_currency_id = fields.Many2one(
        "res.currency",
        default=lambda self: self.env.company.currency_id.id,
    )
    foreign_currency_id = fields.Many2one(
        "res.currency",
        default=lambda self: self.env.company.currency_foreign_id.id,
    )
    base_currency_is_vef = fields.Boolean(
        compute="_compute_currency_fields",
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        readonly=True,
        default=lambda self: self.env.company,
    )
    name = fields.Char(
        "Description",
        size=64,
        help="Description of the withholding voucher",
    )
    code = fields.Char(
        size=32,
        help="Code of the withholding voucher",
    )
    state = fields.Selection(
        [("draft", "Draft"), ("emitted", "Emitted"), ("cancel", "Cancelled")],
        index=True,
        default="draft",
        help="Status of the withholding voucher",
    )
    type_retention = fields.Selection(
        [
            ("iva", "IVA"),
            ("islr", "ISLR"),
            ("municipal", "Municipal"),
        ],
        required=True,
    )
    type = fields.Selection(
        [
            ("out_invoice", "Out invoice"),
            ("in_invoice", "In invoice"),
            ("out_refund", "Out refund"),
            ("in_refund", "In refund"),
            ("out_debit", "Out debit"),
            ("in_debit", "In debit"),
            ("out_contingence", "Out contingence"),
            ("in_contingence", "In contingence"),
        ],
        "Type retention",
        help="Tipo del Comprobante",
        required=True,
        readonly=True,
    )
    partner_id = fields.Many2one(
        "res.partner",
        "Social reason",
        required=True,
        help="Social reason",
    )
    number = fields.Char("Voucher Number")
    correlative = fields.Char(readonly=True)
    date = fields.Date(
        "Voucher Date",
        help="Date of issuance of the withholding voucher by the external party.",
    )
    date_accounting = fields.Date(
        "Accounting Date",
        help=(
            "Date of arrival of the document and date to be used to make the accounting record."
            " Keep blank to use current date."
        ),
    )
    allowed_lines_move_ids = fields.Many2many(
        "account.move",
        string="Invoices to Retain",
        domain=[
            ("move_type", "=", "in_invoice"),
            ("state", "=", "posted"),
            ("partner_id", "!=", False),
        ],
        context={"active_test": False},
    )
#    allowed_lines_move_ids = fields.Many2many(
#        "account.move",
#       compute="_compute_allowed_lines_move_ids",
#        help=(
#            "Technical field to store the allowed move types for the ISLR retention lines. This is"
#            " used to filter the moves that can be selected in the ISLR retention lines."
#        ),
#    )
    retention_line_ids = fields.One2many(
        "account.retention.line",
        "retention_id",
        "retention line",
        help="Retentions",
    )
    code_visible = fields.Boolean()
    payment_ids = fields.One2many(
        "account.payment",
        "retention_id",
        help="Payments",
    )
    total_invoice_amount = fields.Float(
        string="Taxable Income",
        compute="_compute_totals",
        help="Taxable Income Total",
        store=True,
    )
    invoice_amount = fields.Monetary(
        string="Base Imponible",
        currency_field='company_currency_id',
        readonly=True,
    )
    total_iva_amount = fields.Float(
        string="Total IVA", compute="_compute_totals", store=True
    )
    total_retention_amount = fields.Float(
        compute="_compute_totals",
        store=True,
        help="Retained Amount Total",
    )
    foreign_total_invoice_amount = fields.Float(
        string="Foreign StateTaxable Income",
        compute="_compute_totals",
        help="Taxable Income Total",
        store=True,
    )
    foreign_total_iva_amount = fields.Float(
        string="Foreign Total IVA", compute="_compute_totals", store=True
    )
    foreign_total_retention_amount = fields.Float(
        compute="_compute_totals",
        store=True,
        help="Retained Amount Total",
    )
    original_lines_per_invoice_counter = fields.Char(
        help=(
            "Technical field to store the quantity of retention lines per invoice before the user"
            " changes them. This is used to know if the user has deleted the retention lines when"
            " the invoice is changed, in order to delete all the other lines of the same invoice"
            " that the one that just has been deleted."
        )
    )

#     @api.depends('company_id')
#     def _compute_currency_fields(self):
#         for retention in self:
#             retention.base_currency_is_vef = retention.company_id.currency_id == retention.env.ref("base.VEF")
# 
#     @api.depends("type", "partner_id")
#     def _compute_allowed_lines_move_ids(self):
#         for retention in self:
#             if not retention.partner_id or not retention.type:
#                 retention.allowed_lines_move_ids = [(5, 0, 0)]  # Limpia todo
#                 continue
# 
#             # Define tipos según dirección
#             allowed_types = ("in_invoice", "in_refund") if retention.type == "in_invoice" else ("out_invoice", "out_refund")
# 
#             # Busca facturas publicadas con saldo pendiente
#             domain = [
#                 ("company_id", "=", self.env.company.id),
#                 ("state", "=", "posted"),
#                 ("partner_id", "=", retention.partner_id.id),
#                 ("move_type", "in", allowed_types),
#                 ("amount_residual", ">", 0),
#                 ("name", "!=", False),
#             ]
#             invoices = self.env["account.move"].search(domain)
# 
#             # Filtra facturas que YA TIENEN retención ISLR no cancelada
#             eligible_invoices = invoices.filtered(
#                 lambda inv: not inv.retention_islr_line_ids.filtered(lambda l: l.state not in ["cancel"])
#         )
# 
#         # Asigna las facturas
#         retention.allowed_lines_move_ids = [(6, 0, eligible_invoices.ids)]
#             #retention.allowed_lines_move_ids = self.env["account.move"].search(domain)
# 
#     @api.depends(
#         "retention_line_ids.invoice_amount",
#         "retention_line_ids.iva_amount",
#         "retention_line_ids.retention_amount",
#         "retention_line_ids.foreign_invoice_amount",
#         "retention_line_ids.foreign_iva_amount",
#         "retention_line_ids.foreign_retention_amount",
    )
#     def _compute_totals(self):
#         for retention in self:
#             retention.total_invoice_amount = 0
#             retention.total_iva_amount = 0
#             retention.total_retention_amount = 0
#             retention.foreign_total_invoice_amount = 0
#             retention.foreign_total_iva_amount = 0
#             retention.foreign_total_retention_amount = 0
#             for line in retention.retention_line_ids:
#                 if line.move_id.move_type in ("in_refund", "out_refund"):
#                     retention.total_invoice_amount -= float_round(
#                         line.invoice_amount,
#                         precision_digits=retention.company_currency_id.decimal_places,
#                     )
#                     retention.total_iva_amount -= float_round(
#                         line.iva_amount,
#                         precision_digits=retention.company_currency_id.decimal_places,
#                     )
#                     retention.total_retention_amount -= float_round(
#                         line.retention_amount,
#                         precision_digits=retention.company_currency_id.decimal_places,
#                     )
#                     retention.foreign_total_invoice_amount -= float_round(
#                         line.foreign_invoice_amount,
#                         precision_digits=retention.foreign_currency_id.decimal_places,
#                     )
#                     retention.foreign_total_iva_amount -= float_round(
#                         line.foreign_iva_amount,
#                         precision_digits=retention.foreign_currency_id.decimal_places,
#                     )
#                     retention.foreign_total_retention_amount -= float_round(
#                         line.foreign_retention_amount,
#                         precision_digits=retention.foreign_currency_id.decimal_places,
#                     )
#                 else:
#                     retention.total_invoice_amount += float_round(
#                         line.invoice_amount,
#                         precision_digits=retention.company_currency_id.decimal_places,
#                     )
#                     retention.total_iva_amount += float_round(
#                         line.iva_amount,
#                         precision_digits=retention.company_currency_id.decimal_places,
#                     )
#                     retention.total_retention_amount += float_round(
#                         line.retention_amount,
#                         precision_digits=retention.company_currency_id.decimal_places,
#                     )
#                     retention.foreign_total_invoice_amount += float_round(
#                         line.foreign_invoice_amount,
#                         precision_digits=retention.foreign_currency_id.decimal_places,
#                     )
#                     retention.foreign_total_iva_amount += float_round(
#                         line.foreign_iva_amount,
#                         precision_digits=retention.foreign_currency_id.decimal_places,
#                     )
#                     retention.foreign_total_retention_amount += float_round(
#                         line.foreign_retention_amount,
#                         precision_digits=retention.foreign_currency_id.decimal_places,
#                     )
# 
    # === CAMBIO: Implementar onchange_partner_id para cargar facturas automáticamente ===
#     @api.onchange("partner_id")
#     def onchange_partner_id(self):
#         if self.partner_id and self.state == 'draft':
#             # Esto activará el @api.depends
#             pass  # El compute hace el trabajo
#        if not self.partner_id or self.state != 'draft':
 #           return
        if self.type_retention == "iva":
            if self.type == "in_invoice":
                return self._load_retention_lines_for_iva_supplier_retention()
            else:
                return self._load_retention_lines_for_iva_customer_retention()
        elif self.type_retention == "islr":
            if self.type == "in_invoice":
                return self._load_retention_lines_for_islr_supplier_retention()
            else:
                return self._load_retention_lines_for_islr_customer_retention()

#     def _load_retention_lines_for_iva_supplier_retention(self):
#         self.ensure_one()
#         search_domain = [
#             ("company_id", "=", self.company_id.id),
#             ("partner_id", "=", self.partner_id.id),
#             ("state", "=", "posted"),
#             ("move_type", "in", ("in_refund", "in_invoice")),
#             ("amount_residual", ">", 0),
#             ("name", "!=", False),
#         ]
#         invoices_with_taxes = search_invoices_with_taxes(self.env["account.move"], search_domain).filtered(
#             lambda i: not any(i.retention_iva_line_ids.filtered(lambda l: l.state in ("draft", "emitted")))
#         )
#         if not any(invoices_with_taxes):
#             raise UserError(_("There are no invoices with taxes to be retained for the supplier."))
#         self.clear_retention()
#         lines = load_retention_lines(invoices_with_taxes, self.env["account.retention"])
#         lines_per_invoice_counter = defaultdict(int)
#         for line in lines:
#             lines_per_invoice_counter[str(line[2]["move_id"])] += 1
#         return {"value": {
#             "retention_line_ids": lines,
#             "original_lines_per_invoice_counter": json.dumps(lines_per_invoice_counter),
#         }}
# 
#     def _load_retention_lines_for_iva_customer_retention(self):
#         self.ensure_one()
#         search_domain = [
#             ("company_id", "=", self.company_id.id),
#             ("partner_id", "=", self.partner_id.id),
#             ("state", "=", "posted"),
#             ("move_type", "in", ("out_refund", "out_invoice")),
#             ("amount_residual", ">", 0),
#             ("name", "!=", False),
#         ]
#         invoices_with_taxes = search_invoices_with_taxes(self.env["account.move"], search_domain).filtered(
#             lambda i: not any(i.retention_iva_line_ids.filtered(lambda l: l.state in ("draft", "emitted")))
#         )
#         if not any(invoices_with_taxes):
#             raise UserError(_("There are no invoices with taxes to be retained for the customer."))
#         self.clear_retention()
#         lines = load_retention_lines(invoices_with_taxes, self.env["account.retention"])
#         lines_per_invoice_counter = defaultdict(int)
#         for line in lines:
#             lines_per_invoice_counter[str(line[2]["move_id"])] += 1
#         return {"value": {
#             "retention_line_ids": lines,
#             "original_lines_per_invoice_counter": json.dumps(lines_per_invoice_counter),
#         }}
# 
#     def _load_retention_lines_for_islr_supplier_retention(self):
#         """Carga las líneas de retención ISLR para proveedor.
#         Usa las facturas seleccionadas en allowed_lines_move_ids."""
#         self.ensure_one()
#         lines = []
# 
#         for move in self.allowed_lines_move_ids:
#             # === 1. VALIDAR FACTURA ===
#             if move.state != 'posted' or move.move_type != 'in_invoice':
#                 _logger.warning(f"Factura {move.name} no es válida (estado: {move.state}, tipo: {move.move_type}), omitiendo.")
#                 continue
# 
#             # === 2. EXTRAER BASE IMPONIBLE ===
#             tax_totals = move.tax_totals or {}
#             base_imponible = tax_totals.get("amount_untaxed", 0.0)
# 
#             if float_is_zero(base_imponible, precision_rounding=move.currency_id.rounding):
#                 _logger.warning(f"Factura {move.name} tiene base imponible cero, omitiendo.")
#                 continue
# 
#             # === 3. CALCULAR IVA ===
#             iva_lines = move.line_ids.filtered(
#                 lambda line: line.tax_group_id.name == 'IVA'
#                 and line.account_type == 'liability_current'
#             )
#             iva_amount = sum(iva_lines.mapped('price_subtotal'))
# 
#             # === 4. CREAR LÍNEA ===
#             lines.append(Command.create({
#                 "move_id": move.id,
#                 "invoice_amount": base_imponible,
#                 "iva_amount": iva_amount,
#                 "retention_amount": 0.0,
#                 "foreign_invoice_amount": tax_totals.get("foreign_amount_untaxed", base_imponible),
#                 "foreign_currency_rate": move.foreign_rate or 1.0,
#                 "payment_concept_id": False,
#             }))
#             _logger.info(f"Línea ISLR creada para factura {move.name}: Base={base_imponible}, IVA={iva_amount}")
# 
#         if not lines:
#             _logger.warning("No se generaron líneas de retención ISLR para proveedor.")
#             return {}
# 
#         return {"value": {"retention_line_ids": lines}}
# 
#     def _load_retention_lines_for_islr_customer_retention(self):
#         self.ensure_one()
#         search_domain = [
#             ("company_id", "=", self.company_id.id),
#             ("partner_id", "=", self.partner_id.id),
#             ("state", "=", "posted"),
#             ("move_type", "in", ("out_invoice", "out_refund")),
#             ("amount_residual", ">", 0),
#             ("name", "!=", False),
#         ]
#         eligible_invoices = self.env["account.move"].search(search_domain).filtered(
#             lambda inv: not inv.retention_islr_line_ids.filtered(lambda l: l.state in ("draft", "emitted"))
#         )
#         if not eligible_invoices:
#             raise UserError(_("There are no invoices available for ISLR customer retention."))
#         self.clear_retention()
#         lines = []
#         lines_per_invoice_counter = defaultdict(int)
#         for inv in eligible_invoices:
#         # === OBTENER BASE IMPONIBLE desde tax_totals ===
#             base_imponible = 0.0
#             if inv.tax_totals and inv.tax_totals.get("subtotals"):
#                 for subtotal in inv.tax_totals["subtotals"]:
#                 # Buscar el subtotal sin impuestos
#                     base_imponible = inv.tax_totals.get("amount_untaxed", 0.0)
#                     if float_is_zero(base_imponible, precision_rounding=inv.currency_id.rounding):
#                         continue
#                     #if subtotal.get("label") == _("Untaxed Amount") or subtotal.get("name") == "Untaxed Amount":
#                         base_imponible = subtotal["amount"]
#                         break
#             else:
#                 base_imponible = inv.amount_untaxed
# 
#             # === OBTENER IVA desde line_ids (no tax_line_ids) ===
#             iva_lines = inv.line_ids.filtered(
#                 lambda line: line.tax_group_id.name == 'IVA'
#                 and line.account_id.account_type == 'liability_current'
#             )
#             iva_amount = sum(iva_lines.mapped('price_subtotal'))
# 
#             # === CREAR LÍNEA DE RETENCIÓN ===
#             lines.append(Command.create({
#                 "move_id": inv.id,
#                 "invoice_amount": base_imponible,  # ← Base imponible correcta
#                 "iva_amount": iva_amount,
#                 "retention_amount": 0.0,  # El usuario lo define después
#                 "payment_concept_id": False,  # Requerido más tarde
#             }))
#             lines_per_invoice_counter[str(inv.id)] += 1
#         return {
#             "value": {
#                 "retention_line_ids": lines,
#                 "original_lines_per_invoice_counter": json.dumps(lines_per_invoice_counter),
#             }
#         }
# 
#     def clear_retention(self):
#         self.ensure_one()
#         self.update({
#             "retention_line_ids": (
#                 Command.clear() if any(isinstance(id, models.NewId) for id in self.retention_line_ids.ids) else False
#             ),
#         })
# 
#     @api.onchange("retention_line_ids")
#     def onchange_retention_line_ids(self):
#         for retention in self.filtered(lambda r: (r.type_retention, r.state) == ("iva", "draft") and r.partner_id):
#             original_lines_per_invoice_counter = json.loads(retention.original_lines_per_invoice_counter or "{}")
#             lines_per_invoice_counter = defaultdict(int)
#             for line in retention.retention_line_ids:
#                 lines_per_invoice_counter[str(line.move_id.id)] += 1
#             for line in retention.retention_line_ids:
#                 if (line.move_id.id and
#                         lines_per_invoice_counter.get(str(line.move_id.id), 0) !=
#                         original_lines_per_invoice_counter.get(str(line.move_id.id), 0)):
#                     retention.retention_line_ids -= line
#             return {
#                 "value": {
#                     "original_lines_per_invoice_counter": json.dumps(lines_per_invoice_counter)
#                 }
#             }
# 
#     @api.model_create_multi
#     def create(self, vals_list):
#         res = super().create(vals_list)
#         res._safe_create_payments()
#         return res
# 
#     def write(self, vals):
#         res = super().write(vals)
#         if vals.get("retention_line_ids", False):
#             self._safe_create_payments()
#         return res
# 
#     def unlink(self):
#         for record in self:
#             if record.state == "emitted":
#                 raise ValidationError(_("You cannot delete a hold linked to a posted entry. It is necessary to cancel the retention before being deleted"))
#         return super().unlink()
# 
#     def _safe_create_payments(self):
#         """Versión segura para crear pagos que no modifica movimientos publicados"""
#         for retention in self:
#             if any(retention.payment_ids) or retention.type_retention != "iva":
#                 continue
#             payment_vals = {
#                 "retention_id": retention.id,
#                 "partner_id": retention.partner_id.id,
#                 "payment_type_retention": "iva",
#                 "is_retention": True,
#                 "currency_id": self.env.user.company_id.currency_id.id,
#             }
#             if retention.type == "in_invoice":
#                 self._create_payments_for_iva_supplier(payment_vals, lambda: self.env['account.retention.line'])
#             if retention.type == "out_invoice":
#                 self._create_payments_for_iva_customer(payment_vals, lambda: self.env['account.retention.line'])
# 
#     def _create_payments_for_iva_supplier(self, payment_vals, account_retention_line_empty_recordset):
#         Payment = self.env["account.payment"]
#         Rate = self.env["res.currency.rate"]
#         payment_vals["partner_type"] = "supplier"
#         payment_vals["journal_id"] = self.env.company.iva_supplier_retention_journal_id.id
#         in_refund_lines = self.retention_line_ids.filtered(lambda l: l.move_id.move_type == "in_refund")
#         in_invoice_lines = self.retention_line_ids.filtered(lambda l: l.move_id.move_type == "in_invoice")
#         in_refunds_dict = defaultdict(account_retention_line_empty_recordset)
#         in_invoices_dict = defaultdict(account_retention_line_empty_recordset)
#         for line in in_refund_lines:
#             in_refunds_dict[line.move_id] += line
#         for line in in_invoice_lines:
#             in_invoices_dict[line.move_id] += line
#         for lines in in_refunds_dict.values():
#             payment_vals["payment_method_id"] = (self.env.ref("account.account_payment_method_manual_in").id,)
#             payment_vals["payment_type"] = "inbound"
#             payment_vals["foreign_rate"] = lines[0].foreign_currency_rate
#             payment = Payment.create(payment_vals)
#             payment.update({"foreign_inverse_rate": Rate.compute_inverse_rate(payment.foreign_rate)})
#             lines.write({"payment_id": payment.id})
#             payment.compute_retention_amount_from_retention_lines()
#         for lines in in_invoices_dict.values():
#             payment_vals["payment_method_id"] = (self.env.ref("account.account_payment_method_manual_out").id,)
#             payment_vals["payment_type"] = "outbound"
#             payment_vals["foreign_rate"] = lines[0].foreign_currency_rate
#             payment = Payment.create(payment_vals)
#             payment.update({"foreign_inverse_rate": Rate.compute_inverse_rate(payment.foreign_rate)})
#             lines.write({"payment_id": payment.id})
#             payment.compute_retention_amount_from_retention_lines()
# 
#     def _create_payments_for_iva_customer(self, payment_vals, account_retention_line_empty_recordset):
#         Payment = self.env["account.payment"]
#         Rate = self.env["res.currency.rate"]
#         payment_vals["partner_type"] = "customer"
#         payment_vals["journal_id"] = self.env.company.iva_customer_retention_journal_id.id
#         out_refund_lines = self.retention_line_ids.filtered(lambda l: l.move_id.move_type == "out_refund")
#         out_invoice_lines = self.retention_line_ids.filtered(lambda l: l.move_id.move_type == "out_invoice")
#         out_refunds_dict = defaultdict(account_retention_line_empty_recordset)
#         out_invoices_dict = defaultdict(account_retention_line_empty_recordset)
#         for line in out_refund_lines:
#             out_refunds_dict[line.move_id] += line
#         for line in out_invoice_lines:
#             out_invoices_dict[line.move_id] += line
#         for lines in out_refunds_dict.values():
#             payment_vals["payment_method_id"] = (self.env.ref("account.account_payment_method_manual_out").id,)
#             payment_vals["payment_type"] = "outbound"
#             payment_vals["foreign_rate"] = lines[0].foreign_currency_rate
#             payment = Payment.create(payment_vals)
#             payment.update({"foreign_inverse_rate": Rate.compute_inverse_rate(payment.foreign_rate)})
#             lines.write({"payment_id": payment.id})
#             payment.compute_retention_amount_from_retention_lines()
#         for lines in out_invoices_dict.values():
#             payment_vals["payment_method_id"] = (self.env.ref("account.account_payment_method_manual_in").id,)
#             payment_vals["payment_type"] = "inbound"
#             payment_vals["foreign_rate"] = lines[0].foreign_currency_rate
#             payment = Payment.create(payment_vals)
#             payment.update({"foreign_inverse_rate": Rate.compute_inverse_rate(payment.foreign_rate)})
#             lines.write({"payment_id": payment.id})
#             payment.compute_retention_amount_from_retention_lines()
# 
#     def action_post(self):
#         for retention in self:
#             try:
#                 _logger.info(f"Iniciando publicación de retención {retention.id}")
# 
#                 # Asignar número de secuencia si no existe
#                 if not retention.number:
#                     _logger.info(f"Asignando número de secuencia a retención {retention.id}")
#                     retention._set_sequence()
#                     _logger.info(f"Número asignado: {retention.number}")
# 
#                 if retention.type in ["out_invoice", "out_refund", "out_debit"] and not retention.number:
#                     error_msg = f"Retención {retention.id} no tiene número asignado"
#                     _logger.error(error_msg)
#                     raise UserError(_("Debe ingresar un número para la retención"))
# 
#                 # Establecer fechas si no están definidas
#                 today = fields.Date.context_today(self)
#                 if not retention.date_accounting:
#                     retention.date_accounting = today
#                     _logger.info(f"Fecha contable establecida: {retention.date_accounting}")
#                 if not retention.date:
#                     retention.date = today
#                     _logger.info(f"Fecha de retención establecida: {retention.date}")
# 
#                 # Validaciones específicas
#                 if retention.type_retention == 'islr':
#                     if not retention.partner_id.type_person_id:
#                         raise UserError(_("Partner must have a person type for ISLR"))
#                     if not all(line.payment_concept_id for line in retention.retention_line_ids):
#                         raise UserError(_("Todas las líneas de retención ISLR deben tener un concepto de pago asignado"))
# 
#                 # Crear pagos si no existen (modificado para ISLR)
#                 if not retention.payment_ids:
#                     _logger.info("Creando pagos para la retención")
#                     if retention.type_retention == 'islr':
#                         retention._create_islr_payments()  # Nuevo método para ISLR
#                     else:
#                         retention._create_payments_from_retention_lines()  # Método existente para IVA/municipal
# 
#                 # Procesar cada pago con contexto seguro
#                 for payment in retention.payment_ids.with_context(skip_manually_modified_check=True):
#                     _logger.info(f"Procesando pago {payment.id}")
#                     if not payment.move_id:
#                         if hasattr(payment, 'action_create'):
#                             _logger.info("Creando asiento contable para el pago")
#                             payment.action_create()
#                         else:
#                             _logger.info("Publicando pago (versión moderna)")
#                             payment.with_context(skip_manually_modified_check=True).action_post()
#                     elif payment.state != 'posted':
#                         _logger.info("Publicando pago pendiente")
#                         payment.with_context(skip_manually_modified_check=True).action_post()
# 
#                     # Validar que el pago tenga asiento contable
#                     if not payment.move_id:
#                         error_msg = f"El pago {payment.id} no tiene asiento contable asociado"
#                         _logger.error(error_msg)
#                         raise UserError(_("El pago no tiene asiento contable. Por favor valide la configuración."))
# 
#                     # Identificar líneas a reconciliar según tipo de pago
#                     if payment.payment_type == "outbound":
#                         line_filter = lambda l: (l.account_id.account_type == "liability_payable" and l.debit > 0)
#                     else:  # inbound (reembolsos/notas de crédito)
#                         line_filter = lambda l: (l.account_id.account_type == "liability_payable" and l.credit > 0)
#                     lineas_a_reconciliar = payment.move_id.line_ids.filtered(line_filter)
#                     if not lineas_a_reconciliar:
#                         error_msg = f"No hay líneas a reconciliar en pago {payment.id}"
#                         _logger.error(error_msg)
#                         raise UserError(_("""
No se encontraron líneas contables para reconciliar.
Verifique:
1. La configuración de cuentas por pagar
2. Que el pago esté correctamente contabilizado
"""))

                    # Proceso de reconciliación
                    try:
                        linea_reconciliar = lineas_a_reconciliar[0]
                        facturas = payment.retention_line_ids.mapped('move_id')
                        if not facturas:
                            raise UserError(_("No hay facturas asociadas a este pago"))
                        for factura in facturas:
                            if not factura.exists():
                                _logger.warning(f"Factura {factura.id} no existe, omitiendo")
                                continue
                            factura.js_assign_outstanding_line(linea_reconciliar.id)
                        _logger.info(f"Pago {payment.id} reconciliado exitosamente con facturas {facturas.ids}")
                    except Exception as e:
                        error_msg = f"Error reconciliando pago {payment.id}: {str(e)}"
                        _logger.error(error_msg)
                        raise UserError(_("""
Error al reconciliar el pago: %s
Detalles técnicos: %s
""") % (payment.name, str(e)))

                # Asignar número de comprobante a facturas
                move_ids = retention.mapped("retention_line_ids.move_id")
                if move_ids:
                    _logger.info(f"Asignando número de comprobante a {len(move_ids)} facturas")
                    retention.set_voucher_number_in_invoice(move_ids, retention)

                # Actualizar estado de la retención
                retention.write({'state': 'emitted'})
                _logger.info(f"Retención {retention.id} marcada como emitida")

            except Exception as e:
                _logger.error("Error al publicar retención %s: %s", retention.id, str(e), exc_info=True)
                raise UserError(_("Error al publicar la retención: %s") % str(e))

#     def _create_islr_payments(self):
#         """Nuevo método para crear pagos de ISLR agrupados por concepto"""
#         Payment = self.env['account.payment']
#         journal_id = (
#             self.env.company.islr_supplier_retention_journal_id.id
#             if self.type == 'in_invoice'
#             else self.env.company.islr_customer_retention_journal_id.id
#         )
#         lines_by_concept = defaultdict(lambda: self.env['account.retention.line'])
#         for line in self.retention_line_ids:
#             lines_by_concept[line.payment_concept_id] += line
#         payments = self.env['account.payment']
#         for concept, lines in lines_by_concept.items():
#             payment_vals = {
#                 'retention_id': self.id,
#                 'partner_id': self.partner_id.id,
#                 'payment_type_retention': 'islr',
#                 'is_retention': True,
#                 'journal_id': journal_id,
#                 'partner_type': 'supplier' if self.type == 'in_invoice' else 'customer',
#                 'payment_type': 'outbound' if self.type == 'in_invoice' else 'inbound',
#                 'payment_concept_id': concept.id,
#                 'foreign_rate': lines[0].foreign_currency_rate,
#                 'retention_line_ids': [(6, 0, lines.ids)],
#                 'amount': sum(lines.mapped('retention_amount')),
#                 'currency_id': self.env.company.currency_id.id,
#                 'date': self.date_accounting,
#             }
#             payment = Payment.create(payment_vals)
#             payments |= payment
#         # >>>>>>>>>>>> AGREGAR ESTA LÍNEA <<<<<<<<<<<<<<<<
#         payments.compute_retention_amount_from_retention_lines()
#         payments.action_post()
#         _logger.warning(f"Payments IDs after action_post: {payments.ids}, Move IDs after action_post: {[p.move_id for p in payments]}")
#         for payment in payments:
#             _logger.warning(f"Payment ID: {payment.id}, Move ID after action_post: {payment.move_id}")
#         return payments
# 
#     def set_voucher_number_in_invoice(self, move, retention):
#         """Asigna número de comprobante a las facturas relacionadas"""
#         try:
#             _logger.info(f"Asignando número de comprobante a facturas de la retención {retention.id}")
#             if retention.type_retention == "iva":
#                 move.write({"iva_voucher_number": retention.number})
#             elif retention.type_retention == "islr":
#                 move.write({"islr_voucher_number": retention.number})
#             elif retention.type_retention == "municipal":
#                 move.write({"municipal_voucher_number": retention.number})
#             _logger.info(f"Números de comprobante asignados correctamente a {len(move)} facturas")
#         except Exception as e:
#             _logger.error(f"Error asignando número de comprobante: {str(e)}")
#             raise
# 
#     def _safe_set_voucher_number(self, moves, retention):
#         """Asigna número de comprobante sin modificar campos protegidos"""
#         for move in moves:
#             if move.state == 'posted':  # Solo para facturas publicadas
#                 vals = {}
#                 if retention.type_retention == "iva":
#                     vals['iva_voucher_number'] = retention.number
#                 elif retention.type_retention == "islr":
#                     vals['islr_voucher_number'] = retention.number
#                 elif retention.type_retention == "municipal":
#                     vals['municipal_voucher_number'] = retention.number
#                 if vals:
#                     move.write(vals)
# 
#     @api.model
#     def compute_retention_lines_data(self, invoice_id, payment=None):
#         """Computes the retention lines data for the given invoice.
#         Params
#         ------
#         invoice_id: account.move
#             The invoice for which the retention lines are computed.
#         type_retention: tuple[str,str]
#             The type of retention and the type of invoice.
#         payment: account.payment
#             The payment for which the retention lines are computed.
#         Returns
#         -------
#         list[dict]
#             The retention lines data.
#         """
#         _logger.warning(f"compute_retention_lines_data: Procesando factura con ID {invoice_id.id}")
#         _logger.warning(f"compute_retention_lines_data: Atributos de la factura: {invoice_id._fields.keys()}")
#         if hasattr(invoice_id, 'number'):
#             _logger.warning(f"compute_retention_lines_data: El atributo 'number' EXISTE:{invoice_id.number}")
#         else:
#             _logger.warning(f"compute_retention_lines_data: El atributo 'number' NO EXISTE.")
#             
#         if hasattr(invoice_id, 'name'):
#             _logger.warning(f"compute_retention_lines_data: El atributo 'name' EXISTE: {invoice_id.name}")
#         else:
#             _logger.warning(f"compute_retention_lines_data: El atributo 'name' NO EXISTE.")
# 
#         tax_ids = invoice_id.invoice_line_ids.filtered(lambda l: l.tax_ids and l.tax_ids[0].amount > 0).mapped("tax_ids")
#         _logger.warning(f"compute_retention_lines_data: Impuestos encontrados en las líneas de factura: {tax_ids.ids}")
#         if not any(tax_ids):
#             _logger.warning(f"compute_retention_lines_data: La factura {invoice_id.number} no tiene impuestos.")
#             raise UserError(_("The invoice %s has no tax."), invoice_id.number)
# 
#         withholding_amount = invoice_id.partner_id.withholding_type_id.value
#         _logger.warning(f"compute_retention_lines_data: Tasa de retención del socio {invoice_id.partner_id.id}: {withholding_amount * 100}%")
# 
#         lines_data = []
#         if "subtotals" in invoice_id.tax_totals and invoice_id.tax_totals["subtotals"]:
#             _logger.warning(f"Tax Totals for invoice ID {invoice_id.id}: {invoice_id.tax_totals}")
#             for subtotal in invoice_id.tax_totals["subtotals"]:
#                 for tax_group_data in subtotal["tax_groups"]:
#                     tax = tax_ids.filtered(lambda t: t.tax_group_id.id == tax_group_data.get("id"))
#                     if not tax:
#                         _logger.warning(f"compute_retention_lines_data: No se encontró impuesto para el grupo de impuestos con ID {tax_group_data.get('id')}.")
#                         continue
#                     tax = tax[0]
#                     _logger.warning(f"compute_retention_lines_data: Impuesto encontrado: ID {tax.id}, Nombre {tax.name}, Grupo de Impuestos ID {tax.tax_group_id.id}")
# 
#                     retention_amount = tax_group_data["tax_amount"] * (withholding_amount / 100)
#                     retention_amount = float_round(retention_amount, precision_digits=invoice_id.company_currency_id.decimal_places)
#                     foreign_retention_amount = tax_group_data.get("tax_amount_currency", 0.0) * (withholding_amount / 100)
#                     foreign_retention_amount = float_round(foreign_retention_amount, precision_digits=invoice_id.foreign_currency_id.decimal_places)
# 
#                     line_data = {
#                         "move_id": invoice_id.id,
#                         "correlative": invoice_id.correlative or "--",
#                        
#                         "foreign_currency_rate": invoice_id.foreign_rate,
#                         "related_percentage_tax_base": withholding_amount,
#                         "invoice_amount": tax_group_data["base_amount"],
#                         "foreign_invoice_amount": tax_group_data.get("base_amount_currency", 0.0),
#                         "iva_amount": tax_group_data["tax_amount"],
#                         "foreign_iva_amount": tax_group_data.get("tax_amount_currency", 0.0),
#                         "foreign_invoice_total": invoice_id.tax_totals.get("total_amount_currency", 0.0),
#                         "retention_amount": retention_amount,
#                         "foreign_retention_amount": foreign_retention_amount,
#                     }
#                     if line_data.get("retention_amount") != 0.0 or line_data.get("foreign_retention_amount") != 0.0:
#                         lines_data.append(line_data)
#         _logger.warning(f"compute_retention_lines_data: Datos de las líneas de retención calculadas: {lines_data}")
#         return lines_data
# 
#     def _set_sequence(self):
#         for retention in self.filtered(lambda r: not r.number):
#             sequence_number = ""
#             if retention.type_retention == "iva":
#                 sequence = retention.get_sequence_iva_retention()
#                 sequence_number = sequence.next_by_id()
#                 _logger.info(f"Nueva secuencia IVA creada con ID {sequence.id}")
#             elif retention.type_retention == "islr":
#                 sequence = retention.get_sequence_islr_retention()
#                 sequence_number = sequence.next_by_id()
#                 _logger.info(f"Nueva secuencia ISLR creada con ID {sequence.id}")
#             else:
#                 sequence = retention.get_sequence_municipal_retention()
#                 sequence_number = sequence.next_by_id()
#                 _logger.info(f"Nueva secuencia Municipal creada con ID {sequence.id}")
#             correlative = f"{retention.date_accounting.year}{retention.date_accounting.month:02d}{sequence_number}"
#             retention.name = correlative
#             retention.number = correlative
# 
#     @api.model
#     def get_sequence_iva_retention(self):
#         _logger.info("Buscando secuencia para retenciones IVA")
#         sequence = self.env["ir.sequence"].search([
#             ("code", "=", "retention.iva.control.number"),
#             ("company_id", "=", self.env.company.id),
#         ], limit=1)
#         if not sequence:
#             _logger.info("Secuencia para retenciones IVA no encontrada, creando nueva")
#             sequence = self.env["ir.sequence"].create({
#                 "name": "Numero de control retenciones IVA",
#                 "code": "retention.iva.control.number",
#                 "padding": 5,
#                 "company_id": self.env.company.id,
#             })
#             _logger.info(f"Nueva secuencia IVA creada con ID {sequence.id}")
#         return sequence
# 
#     @api.model
#     def get_sequence_islr_retention(self):
#         _logger.info("Buscando secuencia para retenciones ISLR")
#         sequence = self.env["ir.sequence"].search([
#             ("code", "=", "retention.islr.control.number"),
#             ("company_id", "=", self.env.company.id),
#         ], limit=1)
#         if not sequence:
#             _logger.info("Secuencia para retenciones ISLR no encontrada, creando nueva")
#             sequence = self.env["ir.sequence"].create({
#                 "name": "Numero de control retenciones ISLR",
#                 "code": "retention.islr.control.number",
#                 "padding": 5,
#                 "company_id": self.env.company.id,
#             })
#             _logger.info(f"Nueva secuencia ISLR creada con ID {sequence.id}")
#         return sequence
# 
#     def get_sequence_municipal_retention(self):
#         _logger.info("Buscando secuencia para retenciones Municipales")
#         sequence = self.env["ir.sequence"].search([
#             ("code", "=", "retention.municipal.control.number"),
#             ("company_id", "=", self.env.company.id),
#         ], limit=1)
#         if not sequence:
#             _logger.info("Secuencia para retenciones Municipales no encontrada, creando nueva")
#             sequence = self.env["ir.sequence"].create({
#                 "name": "Numero de control retenciones Municipales",
#                 "code": "retention.municipal.control.number",
#                 "padding": 5,
#                 "company_id": self.env.company.id,
#             })
#             _logger.info(f"Nueva secuencia Municipal creada con ID {sequence.id}")
#         return sequence
# 
#     def clear_islr_retention_number(self):
#         for line in self.retention_line_ids:
#             if line.move_id.islr_voucher_number:
#                 line.move_id.islr_voucher_number = False
# 
#     def action_cancel(self):
#         self.payment_ids.mapped("move_id.line_ids").remove_move_reconcile()
#         self.payment_ids.action_cancel()
#         self.write({"state": "cancel"})
#         self.clear_islr_retention_number()
# 
#     def action_draft(self):
#         """
#         Cambia el estado de la retención de 'cancel' a 'draft'.
#         Este botón solo está disponible cuando la retención está cancelada.
#         """
#         self.ensure_one()
#         self.write({"state": "draft"})
# 
#     def action_print_municipal_retention_xlsx(self):
#         """
#         Placeholder para impresión de retención municipal en formato XLSX.
#         Actualmente no hace nada, pero evita errores de vista.
#         Puedes implementarlo más adelante con lógica real.
#         """
#         return self.env["ir.actions.actions"]._for_xml_id("l10n_ve_payment_extension.action_municipal_retention_report")
# 
#     def create_payment_from_retention_form(self):
#         _logger.info("Entrando en create_payment_from_retention_form (VERSION DE LOGGING)")
#         pass
# 
#     def _validate_islr_retention_fields(self):
#         self.ensure_one()
#         if not self.partner_id.type_person_id:
#             raise UserError(_("Select a type person"))
#         if not any(self.retention_line_ids.filtered(lambda l: l.payment_concept_id)):
#             raise UserError(_("Select a payment concept"))
# 
#     def get_signature(self):
#         config = self.env["signature.config"].search([
#             ("active", "=", True),
#             ("company_id", "=", self.company_id.id)
#         ], limit=1)
#         if config and config.signature:
#             return config.signature.decode()
#         else:
#             return False