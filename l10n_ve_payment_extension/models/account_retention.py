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
        default=lambda self: self.env.company.currency_id == self.env.ref("base.VEF"),
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
        compute="_compute_allowed_lines_move_ids",
        help=(
            "Technical field to store the allowed move types for the ISLR retention lines. This is"
            " used to filter the moves that can be selected in the ISLR retention lines."
        ),
    )

    retention_line_ids = fields.One2many(
        "account.retention.line",
        "retention_id",
        "retention line",
        help="Retentions",
    )

    code_visible = fields.Boolean(related="company_id.code_visible")

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

    @api.depends("type", "partner_id")
    def _compute_allowed_lines_move_ids(self):
        """
        Computes the allowed move types for the moves of the retention lines.

        If the retention is of type "in_invoice", the allowed move types are "in_invoice" and
        "in_refund". If the retention is of type "out_invoice", the allowed move types are
        "out_invoice" and "out_refund".

        This is used to filter the moves that can be selected in the retention lines for each type
        of retention (ISLR and municipal).
        """
        for retention in self:
            allowed_types = (
                ("in_invoice", "in_refund")
                if retention.type == "in_invoice"
                else ("out_invoice", "out_refund")
            )

            domain = [
                ("company_id", "=", self.env.company.id),
                ("state", "=", "posted"),
                ("partner_id", "=", retention.partner_id.id),
                ("move_type", "in", allowed_types),
            ]

            retention.allowed_lines_move_ids = self.env["account.move"].search(domain)

    @api.depends(
        "retention_line_ids.invoice_amount",
        "retention_line_ids.iva_amount",
        "retention_line_ids.retention_amount",
        "retention_line_ids.foreign_invoice_amount",
        "retention_line_ids.foreign_iva_amount",
        "retention_line_ids.foreign_retention_amount",
    )
    def _compute_totals(self):
        for retention in self:
            retention.total_invoice_amount = 0
            retention.total_iva_amount = 0
            retention.total_retention_amount = 0
            retention.foreign_total_invoice_amount = 0
            retention.foreign_total_iva_amount = 0
            retention.foreign_total_retention_amount = 0

            for line in retention.retention_line_ids:
                if line.move_id.move_type in ("in_refund", "out_refund"):
                    retention.total_invoice_amount -= float_round(
                        line.invoice_amount,
                        precision_digits=retention.company_currency_id.decimal_places,
                    )
                    retention.total_iva_amount -= float_round(
                        line.iva_amount,
                        precision_digits=retention.company_currency_id.decimal_places,
                    )
                    retention.total_retention_amount -= float_round(
                        line.retention_amount,
                        precision_digits=retention.company_currency_id.decimal_places,
                    )
                    retention.foreign_total_invoice_amount -= float_round(
                        line.foreign_invoice_amount,
                        precision_digits=retention.foreign_currency_id.decimal_places,
                    )
                    retention.foreign_total_iva_amount -= float_round(
                        line.foreign_iva_amount,
                        precision_digits=retention.foreign_currency_id.decimal_places,
                    )
                    retention.foreign_total_retention_amount -= float_round(
                        line.foreign_retention_amount,
                        precision_digits=retention.foreign_currency_id.decimal_places,
                    )
                else:
                    retention.total_invoice_amount += float_round(
                        line.invoice_amount,
                        precision_digits=retention.company_currency_id.decimal_places,
                    )
                    retention.total_iva_amount += float_round(
                        line.iva_amount,
                        precision_digits=retention.company_currency_id.decimal_places,
                    )
                    retention.total_retention_amount += float_round(
                        line.retention_amount,
                        precision_digits=retention.company_currency_id.decimal_places,
                    )
                    retention.foreign_total_invoice_amount += float_round(
                        line.foreign_invoice_amount,
                        precision_digits=retention.foreign_currency_id.decimal_places,
                    )
                    retention.foreign_total_iva_amount += float_round(
                        line.foreign_iva_amount,
                        precision_digits=retention.foreign_currency_id.decimal_places,
                    )
                    retention.foreign_total_retention_amount += float_round(
                        line.foreign_retention_amount,
                        precision_digits=retention.foreign_currency_id.decimal_places,
                    )

    @api.onchange("partner_id")
    def onchange_partner_id(self):
        """
        Load retention lines from invoices with taxes when the partner changes for IVA retentions
        that are not posted.
        """
        self._validate_retention_journals()
        for retention in self.filtered(
            lambda r: (r.state, r.type_retention) == ("draft", "iva") and r.partner_id
        ):
            if retention.type == "in_invoice":
                result = retention._load_retention_lines_for_iva_supplier_retention()
            else:
                result = retention._load_retention_lines_for_iva_customer_retention()
            return result

    def _load_retention_lines_for_iva_supplier_retention(self):
        self.ensure_one()
        self.date_accounting = fields.Date.today()
        search_domain = [
            ("company_id", "=", self.company_id.id),
            ("partner_id", "=", self.partner_id.id),
            ("state", "=", "posted"),
            ("move_type", "in", ("in_refund", "in_invoice")),
            ("amount_residual", ">", 0),
        ]
        invoices_with_taxes = search_invoices_with_taxes(
            self.env["account.move"], search_domain
        ).filtered(
            lambda i: not any(
                i.retention_iva_line_ids.filtered(
                    lambda l: l.state in ("draft", "emitted")
                )
            )
        )
        if not any(invoices_with_taxes):
            raise UserError(
                _("There are no invoices with taxes to be retained for the supplier.")
            )
        self.clear_retention()
        lines = load_retention_lines(invoices_with_taxes, self.env["account.retention"])

        lines_per_invoice_counter = defaultdict(int)
        for line in lines:
            lines_per_invoice_counter[str(line[2]["move_id"])] += 1

        return {
            "value": {
                "retention_line_ids": lines,
                "original_lines_per_invoice_counter": json.dumps(
                    lines_per_invoice_counter
                ),
            }
        }

    def _load_retention_lines_for_iva_customer_retention(self):
        self.ensure_one()
        search_domain = [
            ("company_id", "=", self.company_id.id),
            ("partner_id", "=", self.partner_id.id),
            ("state", "=", "posted"),
            ("move_type", "in", ("out_refund", "out_invoice")),
            ("amount_residual", ">", 0),
            ("name", "!=", False),  # Añadir esta línea
        ]
        invoices_with_taxes = search_invoices_with_taxes(
            self.env["account.move"], search_domain
        ).filtered(
            lambda i: not any(
                i.retention_iva_line_ids.filtered(
                    lambda l: l.state in ("draft", "emitted")
                )
            )
        )
        if not any(invoices_with_taxes):
            raise UserError(
                _("There are no invoices with taxes to be retained for the customer.")
            )
        self.clear_retention()
        lines = load_retention_lines(invoices_with_taxes, self.env["account.retention"])

        lines_per_invoice_counter = defaultdict(int)
        for line in lines:
            lines_per_invoice_counter[str(line[2]["move_id"])] += 1

        return {
            "value": {
                "retention_line_ids": lines,
                "original_lines_per_invoice_counter": json.dumps(
                    lines_per_invoice_counter
                ),
            }
        }

    def _validate_retention_journals(self):
        """
        Validate that the company has the journals configured for the retention type.
        """
        for retention in self:
            # IVA
            if (retention.type_retention, retention.type) == (
                "iva",
                "in_invoice",
            ) and not self.env.company.iva_supplier_retention_journal_id:
                raise UserError(
                    _(
                        "The company must have a supplier IVA retention journal configured."
                    )
                )
            if (retention.type_retention, retention.type) == (
                "iva",
                "out_invoice",
            ) and not self.env.company.iva_customer_retention_journal_id:
                raise UserError(
                    _(
                        "The company must have a customer IVA retention journal configured."
                    )
                )
            # ISLR
            if (retention.type_retention, retention.type) == (
                "islr",
                "in_invoice",
            ) and not self.env.company.islr_supplier_retention_journal_id:
                raise UserError(
                    _(
                        "The company must have a supplier ISLR retention journal configured."
                    )
                )
            if (retention.type_retention, retention.type) == (
                "islr",
                "out_invoice",
            ) and not self.env.company.islr_customer_retention_journal_id:
                raise UserError(
                    _(
                        "The company must have a customer ISLR retention journal configured."
                    )
                )
            # Municipal
            if (retention.type_retention, retention.type) == (
                "municipal",
                "in_invoice",
            ) and not self.env.company.municipal_supplier_retention_journal_id:
                raise UserError(
                    _(
                        "The company must have a supplier municipal retention journal configured."
                    )
                )
            if (retention.type_retention, retention.type) == (
                "municipal",
                "out_invoice",
            ) and not self.env.company.municipal_customer_retention_journal_id:
                raise UserError(
                    _(
                        "The company must have a customer municipal retention journal configured."
                    )
                )

    def clear_retention(self):
        """
        Clear retention lines and payments.
        """
        self.ensure_one()
        self.update(
            {
                "retention_line_ids": (
                    Command.clear()
                    if any(
                        isinstance(id, models.NewId)
                        for id in self.retention_line_ids.ids
                    )
                    else False
                ),
            }
        )



    @api.onchange("retention_line_ids")
    def onchange_retention_line_ids(self):
        """
        On the IVA supplier retention when a line is deleted, delete all the others lines that have
        the same invoice.
        """
        for retention in self.filtered(
            lambda r: (r.type_retention, r.state) == ("iva", "draft") and r.partner_id
        ):
            # Cargar original_lines_per_invoice_counter, asegurando que sea un diccionario,
            # y si está vacío o es None, inicializarlo como un defaultdict.
            original_lines_per_invoice_counter_raw = retention.original_lines_per_invoice_counter
            if original_lines_per_invoice_counter_raw:
                original_lines_per_invoice_counter = defaultdict(int, json.loads(original_lines_per_invoice_counter_raw))
            else:
                original_lines_per_invoice_counter = defaultdict(int)

            lines_per_invoice_counter = defaultdict(int)
            for line in retention.retention_line_ids:
                # Nos aseguramos de que line.move_id sea un registro válido antes de intentar acceder a su .id
                if line.move_id:
                    lines_per_invoice_counter[str(line.move_id.id)] += 1

            # Almacenar las líneas a eliminar en un recordset separado para evitar
            # modificar el recordset mientras se itera sobre él, lo que puede causar problemas.
            lines_to_remove = self.env['account.retention.line'] # Inicializar un recordset vacío

            for line in retention.retention_line_ids:
                # Solo procesamos líneas que tienen un move_id válido
                if line.move_id:
                    # Obtener la cuenta original para esta factura, por defecto 0 si no se encuentra
                    original_count = original_lines_per_invoice_counter.get(str(line.move_id.id), 0)
                    # Obtener la cuenta actual para esta factura
                    current_count = lines_per_invoice_counter[str(line.move_id.id)]

                    # === MODIFICACIÓN CLAVE AQUÍ ===
                    # Solo eliminamos líneas si la cuenta actual es *menor que* la cuenta original.
                    # Esto indica una eliminación.
                    if current_count < original_count:
                        lines_to_remove |= line # Añadir la línea al conjunto de líneas a eliminar

            # Eliminar todas las líneas identificadas de una vez después del bucle
            retention.retention_line_ids -= lines_to_remove

            return {
                "value": {
                    "original_lines_per_invoice_counter": json.dumps(
                        lines_per_invoice_counter
                    )
                }
            }

    @api.model_create_multi
    def create(self, vals_list):
        res = super().create(vals_list)
        res._safe_create_payments()
        return res

    def write(self, vals):
        res = super().write(vals)
        if vals.get("retention_line_ids", False):
            self._safe_create_payments()
        return res

    def unlink(self):
        for record in self:
            if record.state == "emitted":
                raise ValidationError(
                    _(
                        "You cannot delete a hold linked to a posted entry. It is necessary to cancel the retention before being deleted"
                    )
                )
        return super().unlink()

    def _safe_create_payments(self):
        """
        Versión segura para crear pagos que no modifica movimientos publicados
        """
        journal = journals.get((self.type_retention, self.type))
        if not journal:
            raise UserError(_(f"No journal configured for retention type '{self.type_retention}' and invoice type '{self.type}'."))
        journal_id = journal.id
        for retention in self:
            if any(retention.payment_ids) or retention.type_retention != "iva":
                continue
            
            payment_vals = {
                "state": "draft", # <--- Confirma que esté aquí
                "retention_id": retention.id,
                "partner_id": retention.partner_id.id,
                "payment_type_retention": "iva",
                "is_retention": True,
                "currency_id": self.env.user.company_id.currency_id.id,
            }        

            def account_retention_line_empty_recordset():
                return self.env["account.retention.line"]

            if retention.type == "in_invoice":
                self._create_payments_for_iva_supplier(
                    payment_vals, account_retention_line_empty_recordset
                )
            if retention.type == "out_invoice":
                self._create_payments_for_iva_customer(
                    payment_vals, account_retention_line_empty_recordset
                )

    def _create_payments_for_iva_supplier(
        self, payment_vals, account_retention_line_empty_recordset
    ):
        Payment = self.env["account.payment"]
        Rate = self.env["res.currency.rate"]
        payment_vals["partner_type"] = "supplier"
        payment_vals[
            "journal_id"
        ] = self.env.company.iva_supplier_retention_journal_id.id
        in_refund_lines = self.retention_line_ids.filtered(
            lambda l: l.move_id.move_type == "in_refund"
        )
        in_invoice_lines = self.retention_line_ids.filtered(
            lambda l: l.move_id.move_type == "in_invoice"
        )

        in_refunds_dict = defaultdict(account_retention_line_empty_recordset)
        in_invoices_dict = defaultdict(account_retention_line_empty_recordset)

        for line in in_refund_lines:
            in_refunds_dict[line.move_id] += line
        for line in in_invoice_lines:
            in_invoices_dict[line.move_id] += line

        for lines in in_refunds_dict.values():
            payment_vals["payment_method_id"] = (
                self.env.ref("account.account_payment_method_manual_in").id,
            )
            payment_vals["payment_type"] = "inbound"
            payment_vals["foreign_rate"] = lines[0].foreign_currency_rate
            payment = Payment.create(payment_vals)
            payment.update(
                {
                    "foreign_inverse_rate": Rate.compute_inverse_rate(
                        payment.foreign_rate
                    )
                }
            )
            lines.write({"payment_id": payment.id})
            payment.compute_retention_amount_from_retention_lines()
        for lines in in_invoices_dict.values():
            payment_vals["payment_method_id"] = (
                self.env.ref("account.account_payment_method_manual_out").id,
            )
            payment_vals["payment_type"] = "outbound"
            payment_vals["foreign_rate"] = lines[0].foreign_currency_rate
            payment = Payment.create(payment_vals)
            payment.update(
                {
                    "foreign_inverse_rate": Rate.compute_inverse_rate(
                        payment.foreign_rate
                    )
                }
            )
            lines.write({"payment_id": payment.id})
            payment.compute_retention_amount_from_retention_lines()

    def _create_payments_for_iva_customer(
        self, payment_vals, account_retention_line_empty_recordset
    ):
        Payment = self.env["account.payment"]
        Rate = self.env["res.currency.rate"]
        payment_vals["partner_type"] = "customer"
        payment_vals[
            "journal_id"
        ] = self.env.company.iva_customer_retention_journal_id.id
        out_refund_lines = self.retention_line_ids.filtered(
            lambda l: l.move_id.move_type == "out_refund"
        )
        out_invoice_lines = self.retention_line_ids.filtered(
            lambda l: l.move_id.move_type == "out_invoice"
        )

        out_refunds_dict = defaultdict(account_retention_line_empty_recordset)
        out_invoices_dict = defaultdict(account_retention_line_empty_recordset)

        for line in out_refund_lines:
            out_refunds_dict[line.move_id] += line
        for line in out_invoice_lines:
            out_invoices_dict[line.move_id] += line

        for lines in out_refunds_dict.values():
            payment_vals["payment_method_id"] = (
                self.env.ref("account.account_payment_method_manual_out").id,
            )
            payment_vals["payment_type"] = "outbound"
            payment_vals["foreign_rate"] = lines[0].foreign_currency_rate
            payment = Payment.create(payment_vals)
            payment.update(
                {
                    "foreign_inverse_rate": Rate.compute_inverse_rate(
                        payment.foreign_rate
                    )
                }
            )
            lines.write({"payment_id": payment.id})
            payment.compute_retention_amount_from_retention_lines()
        for lines in out_invoices_dict.values():
            payment_vals["payment_method_id"] = (
                self.env.ref("account.account_payment_method_manual_in").id,
            )
            payment_vals["payment_type"] = "inbound"
            payment_vals["foreign_rate"] = lines[0].foreign_currency_rate
            payment = Payment.create(payment_vals)
            payment.update(
                {
                    "foreign_inverse_rate": Rate.compute_inverse_rate(
                        payment.foreign_rate
                    )
                }
            )
            lines.write({"payment_id": payment.id})
            payment.compute_retention_amount_from_retention_lines()

    def action_draft(self):
        self.write({"state": "draft"})

    def action_post(self):
        today = fields.Date.context_today(self) # Usar fields.Date.context_today para compatibilidad con Odoo
        for retention in self:
            try:
                # Validaciones iniciales (se mantienen igual)
                if retention.state == 'emitted':
                    _logger.info(f"Retención {retention.id} ya está en estado 'emitted', omitiendo")
                    continue

                _logger.info(f"Iniciando publicación de retención {retention.id}")

                # Asignar número de secuencia si no existe
                if not retention.number:
                    _logger.info(f"Asignando número de secuencia a retención {retention.id}")
                    retention._set_sequence()
                    _logger.info(f"Número asignado: {retention.number}")
            
                if retention.type in ["out_invoice", "out_refund", "out_debit"] and not retention.number:
                    error_msg = f"Retención {retention.id} no tiene número asignado"
                    _logger.error(error_msg)
                    raise UserError(_("Debe ingresar un número para la retención"))
        
                # Establecer fechas si no están definidas
                #today = fields.Date.context_today(self)
                if not retention.date_accounting:
                    retention.date_accounting = today
                    _logger.info(f"Fecha contable establecida: {retention.date_accounting}")
                if not retention.date:
                    retention.date = today
                    _logger.info(f"Fecha de retención establecida: {retention.date}")

                # 4. Crear y Contabilizar Pagos
                # Necesitamos decidir qué método de creación de pagos usar según type_retention
                if not retention.payment_ids: # <--- IMPORTANTE: Solo crear pagos si no existen
                    _logger.info(f"Creando pagos para la retención {retention.id} (tipo: {retention.type_retention}).")
                    if retention.type_retention == 'islr':
                        payments = retention._create_islr_payments()
                    else: # Para IVA y Municipal, usar la lógica existente
                        payments = retention.create_payment_from_retention_form()

                    # Vincular los pagos creados a la retención
                    retention.payment_ids = [(6, 0, payments.ids)]

                           # Asegurarse de que todos los pagos estén contabilizados si aún no lo están
                for payment in retention.payment_ids.filtered(lambda p: p.state != 'posted'): # <--- IMPORTANTE: Solo contabilizar los que no estén ya en 'posted'
                    _logger.info(f"Publicando pago {payment.id} (estado: {payment.state}).")
                    try:
                        payment.action_post()
                        _logger.info(f"Pago {payment.id} publicado exitosamente.")
                    except Exception as payment_e:
                        _logger.error(f"Error al publicar pago {payment.id} para retención {retention.id}: {str(payment_e)}")
                        raise UserError(_("Error al publicar el pago %s: %s") % (payment.name, str(payment_e)))

                            # 5. Reconciliar Pagos
                # El método _reconcile_all_payments asume que los pagos ya están contabilizados
                _logger.info(f"Iniciando reconciliación de pagos para retención {retention.id}.")
                retention._reconcile_all_payments()
                _logger.info(f"Reconciliación de pagos completada para retención {retention.id}.")



                # # VALIDACIONES ESPECÍFICAS PARA ISLR (NUEVO)
                # if retention.type_retention == 'islr':
                #     if not retention.partner_id.type_person_id:
                #         raise UserError(_("Para retenciones ISLR, el partner debe tener tipo de persona configurado"))
                
                #     if not all(line.payment_concept_id for line in retention.retention_line_ids):
                #         raise UserError(_("Todas las líneas de retención ISLR deben tener un concepto de pago asignado"))

                # # Crear pagos si no existen (modificado para ISLR)
                # if not retention.payment_ids:
                #     _logger.info("Creando pagos para la retención")
                #     if retention.type_retention == 'islr':
                #         retention._create_islr_payments()  # Nuevo método para ISLR
                #     else:
                #         retention._create_payments_from_retention_lines()  # Método existente para IVA/municipal

                # # Procesar cada pago con contexto seguro (se mantiene igual)
                # for payment in retention.payment_ids.with_context(skip_manually_modified_check=True):
                #     _logger.info(f"Procesando pago {payment.id}")
                #     if not payment.move_id:
                #         if hasattr(payment, 'action_create'):
                #             _logger.info("Creando asiento contable para el pago")
                #             payment.action_create()
                #         else:
                #             _logger.info("Publicando pago (versión moderna)")
                #         payment.with_context(skip_manually_modified_check=True).action_post()
                #     elif payment.state != 'posted':
                #         _logger.info("Publicando pago pendiente")
                #         payment.with_context(skip_manually_modified_check=True).action_post()

                # Asignar número de comprobante a facturas (se mantiene igual)
                move_ids = retention.mapped("retention_line_ids.move_id")
                if move_ids:
                    _logger.info(f"Asignando número de comprobante a {len(move_ids)} facturas")
                    retention.set_voucher_number_in_invoice(move_ids, retention)
                    _logger.info(f"Números de comprobante asignados para retención {retention.id}.")


                # Actualizar estado de la retención (se mantiene igual)
                retention.write({'state': 'emitted'})
                _logger.info(f"Retención {retention.id} marcada como emitida")

            except UserError as ue:
                _logger.error(f"Error de usuario al publicar retención {retention.id}: {str(ue)}", exc_info=True)
                raise ue
            except Exception as e:
                _logger.error(f"Error inesperado al publicar retención {retention.id}: {str(e)}", exc_info=True)
                raise UserError(_("Ocurrió un error inesperado al publicar la retención: %s") % str(e))
        
            # except Exception as e:
            #     _logger.error("Error al publicar retención %s: %s", retention.id, str(e), exc_info=True)
            #     raise UserError(_("Error al publicar la retención: %s") % str(e))

    def _create_islr_payments(self):
        """
        Nuevo método para crear pagos de ISLR agrupados por concepto
        """
        Payment = self.env['account.payment']
        journal_id = (
            self.env.company.islr_supplier_retention_journal_id.id 
            if self.type == 'in_invoice' 
            else self.env.company.islr_customer_retention_journal_id.id
        )
    
        # Agrupar líneas por concepto de pago
        lines_by_concept = defaultdict(lambda: self.env['account.retention.line'])
        for line in self.retention_line_ids:
            lines_by_concept[line.payment_concept_id] += line
    
        payments = self.env['account.payment']
        for concept, lines in lines_by_concept.items():
            payment_vals = {
                'retention_id': self.id,
                'partner_id': self.partner_id.id,
                'payment_type_retention': 'islr',
                'is_retention': True,
                'journal_id': journal_id,
                'partner_type': 'supplier' if self.type == 'in_invoice' else 'customer',
                'payment_type': 'outbound' if self.type == 'in_invoice' else 'inbound',
                'payment_concept_id': concept.id,
                'foreign_rate': lines[0].foreign_currency_rate,
                'retention_line_ids': [(6, 0, lines.ids)],
                'amount': sum(lines.mapped('retention_amount')),
                'currency_id': self.env.company.currency_id.id,
                'date': self.date_accounting,
             }
        
            payment = Payment.create(payment_vals)
            payments += payment
    
        return payments   


    def set_voucher_number_in_invoice(self, move, retention):
        try:
            _logger.info(f"Asignando número de comprobante a facturas para retención {retention.id}")
        
            if retention.type_retention == "iva":
                _logger.info(f"Asignando iva_voucher_number: {retention.number}")
                move.write({"iva_voucher_number": retention.number})
            elif retention.type_retention == "islr":
                _logger.info(f"Asignando islr_voucher_number: {retention.number}")
                move.write({"islr_voucher_number": retention.number})
            elif retention.type_retention == "municipal":
                _logger.info(f"Asignando municipal_voucher_number: {retention.number}")
                move.write({"municipal_voucher_number": retention.number})
            
            _logger.info(f"Números de comprobante asignados correctamente a {len(move)} facturas")
        
        except Exception as e:
            _logger.error(f"Error asignando número de comprobante: {str(e)}")
            raise
    
    def _safe_set_voucher_number(self, moves, retention):
        """Asigna número de comprobante sin modificar campos protegidos"""
        for move in moves:
            if move.state == 'posted':  # Solo para facturas publicadas
                vals = {}
                if retention.type_retention == "iva":
                    vals['iva_voucher_number'] = retention.number
                elif retention.type_retention == "islr":
                    vals['islr_voucher_number'] = retention.number
                elif retention.type_retention == "municipal":
                    vals['municipal_voucher_number'] = retention.number
            
                if vals:
                    move.write(vals)
    
    def action_print_municipal_retention_xlsx(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_url",
            "url": f"/web/get_xlsx_municipal_retention?&retention_id={self.id}",
            "target": "self",
        }

    def _set_sequence(self):
        for retention in self.filtered(lambda r: not r.number):
            try:
                _logger.info(f"Asignando secuencia a retención {retention.id}")
            
                sequence_number = ""
                if retention.type_retention == "iva":
                    sequence = retention.get_sequence_iva_retention()
                    _logger.info(f"Secuencia IVA encontrada: {sequence.id}")
                    sequence_number = sequence.next_by_id()
                elif retention.type_retention == "islr":
                    sequence = retention.get_sequence_islr_retention()
                    _logger.info(f"Secuencia ISLR encontrada: {sequence.id}")
                    sequence_number = sequence.next_by_id()
                else:
                    sequence = retention.get_sequence_municipal_retention()
                    _logger.info(f"Secuencia Municipal encontrada: {sequence.id}")
                    sequence_number = sequence.next_by_id()
            
                correlative = f"{retention.date_accounting.year}{retention.date_accounting.month:02d}{sequence_number}"
                retention.name = correlative
                retention.number = correlative
            
                _logger.info(f"Retención {retention.id} - Número asignado: {retention.number}")
            
            except Exception as e:
                _logger.error(f"Error asignando secuencia a retención {retention.id}: {str(e)}")
                raise UserError(_("Error al asignar número de secuencia: %s") % str(e))


    @api.model
    def get_sequence_iva_retention(self):
        _logger.info("Buscando secuencia para retenciones IVA")
        sequence = self.env["ir.sequence"].search(
            [
                ("code", "=", "retention.iva.control.number"),
                ("company_id", "=", self.env.company.id),
            ], limit=1
        )
        if not sequence:
            _logger.info("Secuencia para retenciones IVA no encontrada, creando nueva")
            sequence = self.env["ir.sequence"].create(
                {
                    "name": "Numero de control retenciones IVA",
                    "code": "retention.iva.control.number",
                    "padding": 5,
                    "company_id": self.env.company.id,
                }
            )
            _logger.info(f"Nueva secuencia IVA creada con ID {sequence.id}")

        _logger.info(f"Retornando secuencia IVA: {sequence.id}")
        return sequence

    @api.model
    def get_sequence_islr_retention(self):
        _logger.info("Buscando secuencia para retenciones ISLR")
        sequence = self.env["ir.sequence"].search(
            [
                ("code", "=", "retention.islr.control.number"),
                ("company_id", "=", self.env.company.id),
            ], limit=1
        )
        if not sequence:
            _logger.info("Secuencia para retenciones ISLR no encontrada, creando nueva")
            sequence = self.env["ir.sequence"].create(
                {
                    "name": "Numero de control retenciones ISLR",
                    "code": "retention.islr.control.number",
                    "padding": 5,
                    "company_id": self.env.company.id,
                }
            )
            _logger.info(f"Nueva secuencia ISLR creada con ID {sequence.id}")

        _logger.info(f"Retornando secuencia ISLR: {sequence.id}")
        return sequence

    def get_sequence_municipal_retention(self):
        _logger.info("Buscando secuencia para retenciones Municipales")
        sequence = self.env["ir.sequence"].search(
            [
                ("code", "=", "retention.municipal.control.number"),
                ("company_id", "=", self.env.company.id),
            ], limit=1
        )
        if not sequence:
            _logger.info("Secuencia para retenciones Municipales no encontrada, creando nueva")
            sequence = self.env["ir.sequence"].create(
                {
                    "name": "Numero de control retenciones Municipales",
                    "code": "retention.municipal.control.number",
                    "padding": 5,
                    "company_id": self.env.company.id,
                }
            )
            _logger.info(f"Nueva secuencia Municipal creada con ID {sequence.id}")

        _logger.info(f"Retornando secuencia Municipal: {sequence.id}")
        return sequence

    def clear_islr_retention_number(self):
        for line in self.retention_line_ids:
            if line.move_id.islr_voucher_number:
                line.move_id.islr_voucher_number = False

    def action_cancel(self):
        self.payment_ids.mapped("move_id.line_ids").remove_move_reconcile()
        self.payment_ids.action_cancel()
        self.write({"state": "cancel"})
        self.clear_islr_retention_number()

    def create_payment_from_retention_form(self):
        _logger.info("Entrando en create_payment_from_retention_form (VERSION DE LOGGING)")
        # ... (el resto del código de la función) ...
        """
        Create the corresponding payments for the retention based on the fields of the retention.

        This is meant to create the payment for the ISLR and municipal retentions and it is
        triggered on the action_post method of the retention if it still doesn't have payments at
        that point.

        Returns
        -------
        account.payment recordset
            The payments created for the retention.
        """
        self.ensure_one()
        Payment = self.env["account.payment"]
        journals = {
            ("islr", "in_invoice"): self.env.company.islr_supplier_retention_journal_id,
            (
                "islr",
                "out_invoice",
            ): self.env.company.islr_customer_retention_journal_id,
            (
                "municipal",
                "in_invoice",
            ): self.env.company.municipal_supplier_retention_journal_id,
            (
                "municipal",
                "out_invoice",
            ): self.env.company.municipal_customer_retention_journal_id,
        }
        journal_id = journals[(self.type_retention, self.type)].id

        if self.type_retention == "islr":
            self._validate_islr_retention_fields()

        payment_type = "outbound" if self.type == "in_invoice" else "inbound"
        partner_type = "supplier" if self.type == "in_invoice" else "customer"
        payment_vals = []

        for line in self.retention_line_ids:
            if line.move_id.move_type == "in_refund":
                payment_type = "inbound" if self.type == "in_invoice" else "outbound"
            if line.move_id.move_type == "out_refund":
                payment_type = "outbound" if self.type == "out_invoice" else "inbound"

            payment_method_ref = (
                "account.account_payment_method_manual_in"
                if payment_type == "inbound"
                else "account.account_payment_method_manual_out"
            )

            payment_vals.append(
                {
                    "state": "draft",
                    "payment_type": payment_type,
                    "partner_type": partner_type,
                    "partner_id": line.move_id.partner_id.id,
                    "journal_id": journal_id,
                    "payment_type_retention": self.type_retention,
                    "payment_method_id": self.env.ref(payment_method_ref).id,
                    "is_retention": True,
                    "foreign_rate": line.move_id.foreign_rate,
                    "foreign_inverse_rate": line.move_id.foreign_inverse_rate,
                    "retention_line_ids": [(4, line.id)],
                    "currency_id": self.env.user.company_id.currency_id.id,
                    'amount': line.retention_amount, # <--- AÑADE ESTA LÍNEA
                    'payment_concept_id': line.payment_concept_id.id if line.payment_concept_id else False, # <--- AÑADE ESTA LÍNEA
                    'date': self.date_accounting, # <--- AÑADE ESTA LÍNEA
                    # "retention_line_ids": line,
                    # "currency_id": self.env.user.company_id.currency_id.id,
                }
            )

        # payments = Payment.create(payment_vals)
        payments = self.env["account.payment"]
        for vals in payment_vals:
            payments += Payment.create(vals)
        payments.compute_retention_amount_from_retention_lines()

        # >>>>>>>>>>>> AGREGAR ESTA LÍNEA <<<<<<<<<<<<<<<<
        #####payments.action_post()
        _logger.warning(f"Payments IDs after action_post: {payments.ids}, Move IDs after action_post: {[p.move_id for p in payments]}")  # <---- LÍNEA AGREGADA AQUÍ

        for payment in payments:
            _logger.warning(f"Payment ID: {payment.id}, Move ID after action_post: {payment.move_id}")


        return payments

    def _validate_islr_retention_fields(self):
        """
        Validates the partner has a type person and all the retention lines have a payment concept.
        """
        self.ensure_one()
        if not self.partner_id.type_person_id:
            raise UserError(_("Select a type person"))
        if not any(self.retention_line_ids.filtered(lambda l: l.payment_concept_id)):
            raise UserError(_("Select a payment concept"))

    def _reconcile_all_payments(self):
        for payment in self.mapped("payment_ids"):
            try:
                if payment.partner_type == "supplier":
                    self._reconcile_supplier_payment(payment)
                elif payment.partner_type == "customer":
                    self._reconcile_customer_payment(payment)
            except UserError as e:
                _logger.error(f"Error reconciliando pago {payment.id}: {str(e)}")
                raise

            except Exception as e:
                _logger.error(f"Error inesperado reconciliando pago {payment.id}: {str(e)}")
                raise UserError(_("Ocurrió un error inesperado al reconciliar los pagos."))


    def _reconcile_supplier_payment(self, payment):
        """
        Reconciliación de pagos a proveedores para retenciones
        Args:
            payment (account.payment): Pago a reconciliar
        Raises:
            UserError: Si hay problemas con la reconciliación
        """
        _logger.info(f"Reconciliando pago a proveedor ID: {payment.id}")
    
        # Validación básica del pago
        if not payment.move_id:
            error_msg = f"El pago {payment.id} no tiene asiento contable asociado"
            _logger.error(error_msg)
            raise UserError(_("El pago no tiene asiento contable. Por favor valide la configuración."))
    
        # Identificar líneas a reconciliar según tipo de pago
        if payment.payment_type == "outbound":
            line_filter = lambda l: (
                l.account_id.account_type == "liability_payable" and 
                l.debit > 0
            )
        else:  # inbound (reembolsos/notas de crédito)
            line_filter = lambda l: (
                l.account_id.account_type == "liability_payable" and 
                l.credit > 0
            )
    
        lineas_a_reconciliar = payment.move_id.line_ids.filtered(line_filter)
    
        if not lineas_a_reconciliar:
            error_msg = f"No hay líneas a reconciliar en pago {payment.id}"
            _logger.error(error_msg)
            raise UserError(_("""
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

    @api.model
    def compute_retention_lines_data(self, invoice_id, payment=None):
        """
        Computes the retention lines data for the given invoice.

        Params
        ------
        invoice_id: account.move
            The invoice for which the retention lines are computed.
        type_retention: tuple[str,str]
            The type of retention and the type of invoice.
        payment: account.payment
            The payment for which the retention lines are computed.

        Returns
        -------
        list[dict]
            The retention lines data.
        """
        _logger.warning(f"compute_retention_lines_data: Procesando factura con ID {invoice_id.id}")
        _logger.warning(f"compute_retention_lines_data: Atributos de la factura: {invoice_id._fields.keys()}")
        if hasattr(invoice_id, 'number'):
            _logger.warning(f"compute_retention_lines_data: El atributo 'number' EXISTE: {invoice_id.number}")
        else:
            _logger.warning(f"compute_retention_lines_data: El atributo 'number' NO EXISTE.")
        if hasattr(invoice_id, 'name'):
            _logger.warning(f"compute_retention_lines_data: El atributo 'name' EXISTE: {invoice_id.name}")
        else:
            _logger.warning(f"compute_retention_lines_data: El atributo 'name' NO EXISTE.")

        # --- INICIO DE LA VALIDACIÓN CRÍTICA ---
        if invoice_id.currency_id != self.env.company.currency_id and (not foreign_rate or foreign_rate == 0.0):
            _logger.error(
                f"Tasa de cambio extranjera (foreign_rate) es cero o nula para la factura {invoice_id.display_name} "
                f"({invoice_id.id}) con moneda {invoice_id.currency_id.name} para la fecha {invoice_id.date}. "
                "Verifique las tasas de cambio configuradas en Finanzas -> Configuración -> Monedas -> Tasas."
            )
            raise UserError(_(
                "No se pudo crear la línea de retención. La tasa de cambio para la factura '%s' (moneda %s) "
                "es cero o no está definida para la fecha %s. Por favor, configure la tasa de cambio "
                "en Configuración > Monedas > Tasas."
            ) % (invoice_id.display_name, invoice_id.currency_id.name, invoice_id.date))
        # --- FIN DE LA VALIDACIÓN CRÍTICA ---


        tax_ids = invoice_id.invoice_line_ids.filtered(
            lambda l: l.tax_ids and l.tax_ids[0].amount > 0
        ).mapped("tax_ids")
        _logger.warning(f"compute_retention_lines_data: Impuestos encontrados en las líneas de factura: {tax_ids.ids}")

        if not any(tax_ids):
            _logger.warning(f"compute_retention_lines_data: La factura {invoice_id.number} no tiene impuestos.")

            raise UserError(_("The invoice %s has no tax."), invoice_id.number)

        withholding_amount = invoice_id.partner_id.withholding_type_id.value
        _logger.warning(f"compute_retention_lines_data: Tasa de retención del socio {invoice_id.partner_id.id}: {withholding_amount * 100}%")

        lines_data = []
        if "subtotals" in invoice_id.tax_totals and invoice_id.tax_totals["subtotals"]:
            _logger.warning(f"Tax Totals for invoice ID {invoice_id.id}: {invoice_id.tax_totals}")
            for subtotal in invoice_id.tax_totals["subtotals"]:
                subtotal_name = subtotal.get("name", "Subtotal")  # Default name
                for tax_group_data in subtotal.get("tax_groups", []):
                    tax = tax_ids.filtered(lambda t: t.tax_group_id.id == tax_group_data.get("id"))
                    if not tax:
                        _logger.warning(f"compute_retention_lines_data: No se encontró impuesto para el grupo de impuestos con ID {tax_group_data.get('id')}.")

                        continue
                    tax = tax[0]
                    _logger.warning(f"compute_retention_lines_data: Impuesto encontrado: ID {tax.id}, Nombre {tax.name}, Grupo de Impuestos ID {tax.tax_group_id.id}")

                    retention_amount = tax_group_data["tax_amount"] * (withholding_amount / 100)
                    retention_amount = float_round(
                        retention_amount,
                        precision_digits=invoice_id.company_currency_id.decimal_places,
                    )
                    # --- INICIO DE CAMBIOS ---
                    # Ensure foreign_rate is not zero to prevent division by zero errors
                    foreign_rate = invoice_id.foreign_rate
                    if not foreign_rate or foreign_rate == 0.0:
                        _logger.error(
                            f"Tasa de cambio extranjera (foreign_rate) es cero o nula para la factura {invoice_id.display_name} "
                            f"({invoice_id.id}) con moneda {invoice_id.currency_id.name} para la fecha {invoice_id.date}. "
                            "Verifique las tasas de cambio configuradas en Finanzas -> Configuración -> Monedas -> Tasas."
                        )
                        raise UserError(_(
                            "No se pudo crear la línea de retención. La tasa de cambio para la factura '%s' (moneda %s) "
                            "es cero o no está definida para la fecha %s. Por favor, configure la tasa de cambio "
                            "en Configuración > Monedas > Tasas."
                        ) % (invoice_id.display_name, invoice_id.currency_id.name, invoice_id.date))

                    # Calculate foreign_inverse_rate
                    foreign_inverse_rate = 1 / foreign_rate if foreign_rate else 0.0
                    # --- FIN DE CAMBIOS ---
                    foreign_retention_amount = float_round(
                        (tax_group_data.get("tax_amount_currency", 0.0) * (withholding_amount / 100)),
                        precision_digits=invoice_id.foreign_currency_id.decimal_places,
                    )
                    line_data = {
                        "name": _("Iva Retention"),
                        "invoice_type": invoice_id.move_type,
                        "move_id": invoice_id.id,
                        "payment_id": payment.id if payment else None,
                        "aliquot": tax.amount,
                        "iva_amount": tax_group_data["tax_amount"],
                        "invoice_total": invoice_id.tax_totals["total_amount"],
                        "related_percentage_tax_base": withholding_amount,
                        "invoice_amount": tax_group_data["base_amount"],
                        "foreign_currency_rate": foreign_rate, ###invoice_id.foreign_rate,
                        "foreign_currency_inverse_rate": foreign_inverse_rate, # <--- AÑADE ESTA LÍNEA
                        "foreign_iva_amount": tax_group_data.get("tax_amount_currency", 0.0),
                        "foreign_invoice_total": invoice_id.tax_totals.get("total_amount_currency", 0.0),
                        "retention_amount": retention_amount,  # ¡Añade esta línea!
                        "foreign_retention_amount": foreign_retention_amount,  # ¡Y esta!
                    }
                    # Agrega esta condición para evitar líneas con monto cero
                    if line_data.get("retention_amount") != 0.0 or line_data.get("foreign_retention_amount") != 0.0:

                        lines_data.append(line_data)
        _logger.warning(f"compute_retention_lines_data: Datos de las líneas de retención calculadas: {lines_data}")

        return lines_data
        

    def get_signature(self):
        config = self.env["signature.config"].search(
            [("active", "=", True), ("company_id", "=", self.company_id.id)],
            limit=1,
        )
        if config and config.signature:
            return config.signature.decode()
        else:
            return False
