from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import logging

_logger = logging.getLogger(__name__)


class AccountRetentionLine(models.Model):
    _name = "account.retention.line"
    _description = "Retention Line"

    check_company = True

    def _get_vef_currency(self):
        # 1. Moneda de la retención
        if self.foreign_currency_id and self.foreign_currency_id.name in ('VES', 'VEF') and self.foreign_currency_id.active:
            return self.foreign_currency_id
        
        # 2. Moneda de la retención padre
        if self.retention_id:
            parent_curr = self.retention_id._get_vef_currency()
            if parent_curr:
                return parent_curr

        # 3. Moneda dual de la compañía
        company = self.company_id or self.env.company
        if company.currency_id_dif and company.currency_id_dif.name in ('VES', 'VEF') and company.currency_id_dif.active:
            return company.currency_id_dif
        if company.currency_id.name in ('VES', 'VEF') and company.currency_id.active:
            return company.currency_id
        
        # 4. Buscar VES activa en el sistema
        ves = self.env['res.currency'].search([('name', '=', 'VES'), ('active', '=', True)], limit=1)
        if ves:
            return ves
        
        # 5. Buscar VEF activa en el sistema
        vef = self.env['res.currency'].search([('name', '=', 'VEF'), ('active', '=', True)], limit=1)
        if vef:
            return vef
            
        return self.foreign_currency_id or company.currency_id

    name = fields.Char(
        string="Description", required=True, compute="_compute_name", store=True, readonly=False
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
    )
    state = fields.Selection(related="retention_id.state")
    company_currency_id = fields.Many2one(related="retention_id.company_currency_id")
    foreign_currency_id = fields.Many2one(related="retention_id.foreign_currency_id")
    retention_id = fields.Many2one("account.retention", string="Retention", ondelete="cascade")
    invoice_type = fields.Selection(
        selection=[
            ("out_invoice", "Out invoice"),
            ("in_invoice", "In invoice"),
            ("out_refund", "Out refund"),
            ("in_refund", "In refund"),
            ("out_debit", "Out debit"),
            ("in_debit", "In debit"),
        ],
    )
    date_accounting = fields.Date(related="retention_id.date_accounting", store=True)
    # Para campos no monetarios, puedes usar precisiones estándar o personalizadas.
    # Si "Tasa" no es un registro en decimal.precision, puedes usar una estándar como 'Account'
    aliquot = fields.Float() # La precisión por defecto suele ser suficiente
    retention_rate = fields.Float(store=True)

    # Para campos monetarios, Odoo 18 lo gestiona automáticamente
    # Simplemente elimina el parámetro 'digits'
    invoice_amount = fields.Float(
        string="Taxable income",
        compute="_compute_line_amounts",
        store=True,
        readonly=False,
    )
    retention_amount = fields.Float(
        string="Retention amount",
        compute="_compute_line_amounts",
        store=True,
        readonly=False,
    )
#    aliquot = fields.Float(digits=(16, 2))
    amount_tax_ret = fields.Float(string="Retained tax", digits=(16, 2))
    base_ret = fields.Float("Retained base", digits=(16, 2))
    imp_ret = fields.Float(string="tax incurred", digits=(16, 2))
    retention_rate = fields.Float(store=True, digits="Tasa")
    move_id = fields.Many2one("account.move", "move", ondelete="cascade", store=True)
    is_retention_client = fields.Boolean(default=True)
    display_invoice_number = fields.Char(
        string="Invoice Number", compute="_compute_display_invoice_number", store=True
    )
    invoice_total = fields.Float(
        string="Total invoiced",
        compute="_compute_line_amounts",
        store=True,
        readonly=False,
    )
    iva_amount = fields.Float(
        string="IVA",
        compute="_compute_line_amounts",
        store=True,
        readonly=False,
    )
    foreign_retention_amount = fields.Float(
        string="Monto Retenido (Bs.)",
        compute="_compute_line_amounts",
        store=True,
        readonly=False,
    )

    payment_concept_id = fields.Many2one(
        "payment.concept", "Payment concept", ondelete="cascade", index=True
    )
    code = fields.Char(
        related="payment_concept_id.line_payment_concept_ids.code"
    )
    code_visible = fields.Boolean(
        related='company_id.code_visible')
    economic_activity_id = fields.Many2one(
        "economic.activity",
        ondelete="cascade",
        compute="_compute_economic_activity_id",
        readonly=False,
        store=True,
        index=True,
    )

    payment_id = fields.Many2one("account.payment", "Payment", index=True)
    payment_date = fields.Date(related="payment_id.date", store=True)
    payment_journal_id = fields.Many2one(
        "account.journal",
        "Payment journal",
        ondelete="cascade",
        index=True,
        related="payment_id.journal_id",
    )

    related_pay_from = fields.Float(
        string="Pays from",
        compute="_compute_related_fields",
        store=True,
    )
    related_percentage_tax_base = fields.Float(
        string="% tax base",
        compute="_compute_related_fields",
        store=True,
        readonly=False,
    )
    related_percentage_fees = fields.Float(
        string="% tariffs",
        compute="_compute_related_fields",
        store=True,
    )
    related_amount_subtract_fees = fields.Float(
        string="Amount subtract tariffs",
        compute="_compute_related_fields",
        store=True,
    )

    edit_tax_base = fields.Boolean(
        string="Modificar Base",
        default=False,
    )

    # Montos en VEF (Bs.) — Regla universal venezolana
    foreign_invoice_amount = fields.Float(
        string="Base Imponible (Bs.)",
        compute="_compute_line_amounts",
        store=True,
        readonly=False,
    )
    foreign_invoice_total = fields.Float(
        string="Total Factura (Bs.)",
        compute="_compute_line_amounts",
        store=True,
        readonly=False,
    )
    foreign_iva_amount = fields.Float(
        string="IVA (Bs.)",
        compute="_compute_line_amounts",
        store=True,
        readonly=False,
    )
    foreign_currency_rate = fields.Float(
        string="Tasa (Extensión de Pago)",
        compute="_compute_line_amounts",
        store=True,
        readonly=False,
    )
    foreign_currency_inverse_rate = fields.Float(string="Inverse Rate")

    # Después de la definición de tus fields (campos) y antes de tus @api.depends o @api.onchange existentes.
    # Por ejemplo, puedes ponerlo después de 'foreign_currency_rate = fields.Float(string="Rate")'

    @api.onchange('move_id')
    def _onchange_move_id_populate_fields(self):
        """
        Popula los campos de la línea de retención basados en la factura seleccionada (move_id).
        Este método se ejecuta inmediatamente al seleccionar la factura.

        ODOO 18 - Claves correctas de tax_totals:
          Factura VEF: base_amount_currency / tax_amount_currency / total_amount_currency (ya en Bs)
          Factura USD: foreign_amount_untaxed / foreign_amount_total (ya convertido a Bs por l10n_ve_tax)
        """
        if self.move_id:
            invoice = self.move_id
            tax_totals = invoice.tax_totals if hasattr(invoice, 'tax_totals') and invoice.tax_totals else {}

            # Detectar moneda de la factura
            vef_currency = self._get_vef_currency()
            invoice_currency = invoice.currency_id
            invoice_is_vef = vef_currency and (invoice_currency == vef_currency)

            if invoice_is_vef:
                # ============================================================
                # FACTURA EN VEF (Bs): usar *_amount_currency (moneda factura)
                # base_amount_currency = monto en Bs (CORRECTO)
                # base_amount          = monto en USD empresa (INCORRECTO para retención)
                # ============================================================
                bs_untaxed = abs(tax_totals.get('base_amount_currency', 0.0))
                bs_total   = abs(tax_totals.get('total_amount_currency', 0.0))
                bs_iva     = abs(tax_totals.get('tax_amount_currency', 0.0))

                self.invoice_amount        = bs_untaxed
                self.invoice_total         = bs_total
                self.iva_amount            = bs_iva
                self.foreign_invoice_amount = bs_untaxed
                self.foreign_invoice_total  = bs_total
                self.foreign_iva_amount     = bs_iva
            else:
                # ============================================================
                # FACTURA EN USD: los campos native son en USD
                # foreign_amount_untaxed / foreign_amount_total ya están en Bs
                # (calculados por l10n_ve_tax con la tasa BCV)
                # ============================================================
                usd_untaxed = abs(tax_totals.get('base_amount_currency', 0.0))
                usd_total   = abs(tax_totals.get('total_amount_currency', 0.0))
                usd_iva     = abs(tax_totals.get('tax_amount_currency', 0.0))
                bs_untaxed  = abs(tax_totals.get('foreign_amount_untaxed', 0.0))
                bs_total    = abs(tax_totals.get('foreign_amount_total', 0.0))
                bs_iva      = bs_total - bs_untaxed

                self.invoice_amount        = usd_untaxed
                self.invoice_total         = usd_total
                self.iva_amount            = usd_iva
                self.foreign_invoice_amount = bs_untaxed
                self.foreign_invoice_total  = bs_total
                self.foreign_iva_amount     = bs_iva

            self.foreign_currency_rate = invoice.foreign_rate or 1.0
            self.is_retention_client = invoice.move_type in ('out_invoice', 'out_refund', 'out_debit')
            self.invoice_type = invoice.move_type

            # Porcentaje de retención del partner y alícuota para IVA
            type_retention = self.retention_id.type_retention if self.retention_id else 'iva'
            if type_retention == 'iva':
                withholding_amount = invoice.partner_id.withholding_type_id.value or 0.0
                self.related_percentage_tax_base = withholding_amount

                tax_ids = invoice.invoice_line_ids.filtered(
                    lambda l: l.tax_ids and l.tax_ids[0].amount > 0
                ).mapped("tax_ids")
                self.aliquot = tax_ids[0].amount if tax_ids else 0.0

                self.retention_amount = self.iva_amount * (withholding_amount / 100)
                self.foreign_retention_amount = self.foreign_iva_amount * (withholding_amount / 100)

        else:
            # Limpiar los campos si no hay factura seleccionada
            self.invoice_total = 0.0
            self.foreign_invoice_total = 0.0
            self.invoice_amount = 0.0
            self.foreign_invoice_amount = 0.0
            self.iva_amount = 0.0
            self.foreign_iva_amount = 0.0
            self.foreign_currency_rate = 0.0
            self.is_retention_client = False
            self.invoice_type = False
            self.retention_amount = 0.0
            self.foreign_retention_amount = 0.0
            self.aliquot = 0.0
            self.related_pay_from = 0.0
            self.related_percentage_tax_base = 0.0
            self.related_percentage_fees = 0.0
            self.related_amount_subtract_fees = 0.0
            self.payment_concept_id = False
            self.economic_activity_id = False

    @api.depends("retention_id.type_retention", "move_id")
    def _compute_name(self):
        for record in self:
            if record.name:
                continue
            names = {
                "islr": _("ISLR Retention"),
                "iva": _("IVA Retention"),
                "municipal": _("Municipal Retention"),
            }
            type_retention = "islr"
            if record.retention_id.type_retention:
                type_retention = record.retention_id.type_retention
            elif record.move_id:
                if record in record.move_id.retention_iva_line_ids:
                    type_retention = "iva"
                elif record in record.move_id.retention_municipal_line_ids:
                    type_retention = "municipal"

            record.name = names.get(type_retention, _("Retention"))

    @api.depends("retention_id", "move_id")
    def _compute_economic_activity_id(self):
        for line in self:
            if line.economic_activity_id:
                continue
            if line.retention_id and line.retention_id.type_retention == "municipal":
                line.economic_activity_id = line.retention_id.partner_id.economic_activity_id
            if line.move_id and line.id in line.move_id.retention_municipal_line_ids.ids:
                line.economic_activity_id = line.move_id.partner_id.economic_activity_id

    def unlink(self):
        for record in self:
            record.payment_id.unlink()
        return super().unlink()

    # =========== CAMBIO AQUÍ ===========
    @api.onchange("payment_concept_id", "move_id")
    @api.depends("payment_concept_id", "move_id", "move_id.partner_id.type_person_id", "move_id.partner_id.commercial_partner_id.type_person_id")
    def _compute_related_fields(self):
        """
        Calcula los campos relacionados con el concepto de pago para retenciones ISLR.
        """
        lines_from_islr_retention = self.filtered(
            lambda l: l.payment_concept_id or (not l.retention_id or l.retention_id.type_retention == "islr")
        )

        for record in lines_from_islr_retention:
            record.related_pay_from = 0.0
            record.related_percentage_tax_base = 0.0
            record.related_percentage_fees = 0.0
            record.related_amount_subtract_fees = 0.0

            partner = (
                (record.move_id.partner_id if record.move_id else False)
                or (record.retention_id.partner_id if record.retention_id else False)
            )
            if not partner or not record.payment_concept_id:
                continue

            partner_person_type = (
                partner.type_person_id 
                or partner.commercial_partner_id.type_person_id
                or (record.retention_id.partner_id.type_person_id if record.retention_id else False)
                or (record.retention_id.partner_id.commercial_partner_id.type_person_id if record.retention_id else False)
            )
            if not partner_person_type:
                continue

            partner_person_type_name = partner_person_type.name
            payment_concept = record.payment_concept_id.line_payment_concept_ids
            for line in payment_concept:
                if line.type_person_id and partner_person_type_name == line.type_person_id.name:
                    record.related_pay_from = line.pay_from or 0.0
                    record.related_percentage_tax_base = line.percentage_tax_base or 0.0
                    record.related_percentage_fees = line.tariff_id.percentage if line.tariff_id else 0.0
                    record.related_amount_subtract_fees = line.tariff_id.amount_subtract if line.tariff_id else 0.0
                    break

    @api.onchange("payment_concept_id", "move_id")
    def _onchange_concept_or_move(self):
        """
        Resetea los montos de retención para clientes si se cambia la factura o el concepto de pago.
        Esto permite que el método de computo determine que el valor anterior ya no es válido y calcule los nuevos montos.
        """
        for record in self:
            if record.retention_id and record.retention_id.type == 'out_invoice':
                record.invoice_amount = 0.0
                record.invoice_total = 0.0
                record.iva_amount = 0.0
                record.foreign_invoice_amount = 0.0
                record.foreign_invoice_total = 0.0
                record.foreign_iva_amount = 0.0
                record.foreign_currency_rate = 0.0
                record.retention_amount = 0.0
                record.foreign_retention_amount = 0.0

    @api.onchange(
        "move_id",
        "payment_concept_id",
        "economic_activity_id",
        "related_percentage_tax_base",
        "related_percentage_fees",
        "related_amount_subtract_fees",
    )
    @api.depends(
        "move_id",
        "move_id.tax_totals",
        "move_id.foreign_rate",
        "payment_concept_id",
        "economic_activity_id",
        "retention_id.type_retention",
        "retention_id.type",
        "related_percentage_tax_base",
        "related_percentage_fees",
        "related_amount_subtract_fees"
    )
    def _compute_line_amounts(self):
        for record in self:
            if not record.move_id:
                record.invoice_amount = 0.0
                record.invoice_total = 0.0
                record.iva_amount = 0.0
                record.retention_amount = 0.0
                record.foreign_invoice_amount = 0.0
                record.foreign_invoice_total = 0.0
                record.foreign_iva_amount = 0.0
                record.foreign_retention_amount = 0.0
                record.foreign_currency_rate = 1.0
                continue

            invoice = record.move_id
            tax_totals = invoice.tax_totals or {}

            # Detectar moneda de la factura
            vef_currency = record._get_vef_currency()
            invoice_currency = invoice.currency_id
            invoice_is_vef = vef_currency and (invoice_currency == vef_currency)

            if invoice_is_vef:
                # Factura VEF
                bs_untaxed = abs(tax_totals.get('base_amount_currency', 0.0))
                bs_total   = abs(tax_totals.get('total_amount_currency', 0.0))
                bs_iva     = abs(tax_totals.get('tax_amount_currency', 0.0))
                usd_untaxed = bs_untaxed
                usd_total   = bs_total
                usd_iva     = bs_iva
            else:
                # Factura USD
                usd_untaxed = abs(tax_totals.get('base_amount_currency', 0.0))
                usd_total   = abs(tax_totals.get('total_amount_currency', 0.0))
                usd_iva     = abs(tax_totals.get('tax_amount_currency', 0.0))
                bs_untaxed  = abs(tax_totals.get('foreign_amount_untaxed', 0.0))
                bs_total    = abs(tax_totals.get('foreign_amount_total', 0.0))
                bs_iva      = bs_total - bs_untaxed

            # Determinar el tipo de retención
            type_retention = record.retention_id.type_retention if record.retention_id else False
            if not type_retention:
                if record.payment_concept_id:
                    type_retention = 'islr'
                elif record.economic_activity_id:
                    type_retention = 'municipal'
                else:
                    type_retention = 'iva'

            # Porcentaje de retención para IVA/ISLR
            withholding_amount = record.related_percentage_tax_base or (invoice.partner_id.withholding_type_id.value if invoice.partner_id.withholding_type_id else 0.0)
            if not withholding_amount and record.retention_id and record.retention_id.type == 'in_invoice':
                withholding_amount = 75.0  # Default standard in Venezuela

            foreign_rate = invoice.foreign_rate or 1.0

            # Cálculos teóricos
            if record.edit_tax_base and type_retention == 'islr':
                computed_invoice_amount = record.invoice_amount
                computed_foreign_invoice_amount = record.foreign_invoice_amount
            else:
                computed_invoice_amount = usd_untaxed
                computed_foreign_invoice_amount = bs_untaxed

            computed_invoice_total = usd_total
            computed_iva_amount = usd_iva
            computed_foreign_invoice_total = bs_total
            computed_foreign_iva_amount = bs_iva
            computed_foreign_currency_rate = foreign_rate

            if type_retention == 'iva':
                computed_retention_amount = computed_iva_amount * (withholding_amount / 100.0)
                computed_foreign_retention_amount = computed_foreign_iva_amount * (withholding_amount / 100.0)
            elif type_retention == 'islr':
                computed_retention_amount = (
                    (computed_invoice_amount * (record.related_percentage_tax_base / 100))
                    * (record.related_percentage_fees / 100)
                ) - (record.related_amount_subtract_fees / foreign_rate if foreign_rate else 0.0)
                computed_retention_amount = max(computed_retention_amount, 0.0)

                computed_foreign_retention_amount = (
                    (computed_foreign_invoice_amount * (record.related_percentage_tax_base / 100))
                    * (record.related_percentage_fees / 100)
                ) - record.related_amount_subtract_fees
                computed_foreign_retention_amount = max(computed_foreign_retention_amount, 0.0)
            elif type_retention == 'municipal':
                aliquot = record.economic_activity_id.aliquot or 0.0
                computed_retention_amount = computed_invoice_amount * aliquot / 100.0
                computed_foreign_retention_amount = computed_foreign_invoice_amount * aliquot / 100.0

            # Asignación de valores
            if record.retention_id and record.retention_id.type == 'out_invoice':
                # Si es cliente, preservar valores manuales existentes
                record.invoice_amount = record.invoice_amount or computed_invoice_amount
                record.invoice_total = record.invoice_total or computed_invoice_total
                record.iva_amount = record.iva_amount or computed_iva_amount
                record.foreign_invoice_amount = record.foreign_invoice_amount or computed_foreign_invoice_amount
                record.foreign_invoice_total = record.foreign_invoice_total or computed_foreign_invoice_total
                record.foreign_iva_amount = record.foreign_iva_amount or computed_foreign_iva_amount
                record.foreign_currency_rate = record.foreign_currency_rate or computed_foreign_currency_rate
                record.retention_amount = record.retention_amount or computed_retention_amount
                record.foreign_retention_amount = record.foreign_retention_amount or computed_foreign_retention_amount
            else:
                # Si es proveedor o borrador independiente, sobreescribir con el cálculo exacto de la factura
                if record.edit_tax_base and type_retention == 'islr':
                    # Si está activo modificar base para ISLR, mantenemos el valor actual en memoria de las bases imponible
                    record.invoice_amount = record.invoice_amount
                    record.foreign_invoice_amount = record.foreign_invoice_amount
                    record.invoice_total = computed_invoice_total
                    record.iva_amount = computed_iva_amount
                    record.foreign_invoice_total = computed_foreign_invoice_total
                    record.foreign_iva_amount = computed_foreign_iva_amount
                    record.foreign_currency_rate = computed_foreign_currency_rate
                    record.retention_amount = computed_retention_amount
                    record.foreign_retention_amount = computed_foreign_retention_amount
                else:
                    record.invoice_amount = computed_invoice_amount
                    record.invoice_total = computed_invoice_total
                    record.iva_amount = computed_iva_amount
                    record.foreign_invoice_amount = computed_foreign_invoice_amount
                    record.foreign_invoice_total = computed_foreign_invoice_total
                    record.foreign_iva_amount = computed_foreign_iva_amount
                    record.foreign_currency_rate = computed_foreign_currency_rate
                    record.retention_amount = computed_retention_amount
                    record.foreign_retention_amount = computed_foreign_retention_amount
                if type_retention == 'iva':
                    record.related_percentage_tax_base = withholding_amount
                elif type_retention == 'municipal':
                    record.aliquot = record.economic_activity_id.aliquot or 0.0


    @api.onchange("economic_activity_id", "move_id")
    def onchange_economic_activity_id(self):
        """
        Computes the aliquot of the line when the economic activity is changed for the retentions
        of municipal type.
        """
        municipal_lines = self.filtered(
            lambda l: (not l.retention_id or l.retention_id.type_retention == "municipal")
            and l.economic_activity_id and l.move_id
        )

        for record in municipal_lines:
            tax_totals = record.move_id.tax_totals or {}
            if not record.retention_id or record.retention_id.type == "in_invoice":
                record.invoice_amount = tax_totals.get("amount_untaxed", 0.0)
                record.foreign_invoice_amount = tax_totals.get("foreign_amount_untaxed", 0.0)

            # >>> AÑADE ESTAS DOS LÍNEAS AQUÍ para capturar el IVA en retenciones municipales
            record.iva_amount = tax_totals.get("amount_tax", 0.0) 
            record.foreign_iva_amount = tax_totals.get("foreign_amount_tax", 0.0) 


            record.invoice_total = tax_totals.get("amount_total", 0.0)
            record.foreign_invoice_total = tax_totals.get("foreign_amount_total", 0.0)
            record.foreign_currency_rate = record.move_id.foreign_rate or 1.0

            record.aliquot = record.economic_activity_id.aliquot
            record.retention_amount = record.invoice_amount * record.aliquot / 100
            record.foreign_retention_amount = record.foreign_invoice_amount * record.aliquot / 100

    @api.onchange("invoice_amount", "foreign_invoice_amount", "aliquot")
    def onchange_municipal_invoice_amount(self):
        """
        Computes the retention amount when the invoice amount or the aliquot are changed for the
        retentions of municipal type.
        """
        for record in self.filtered(
            lambda l: (not l.retention_id and l.economic_activity_id)
            or (l.retention_id and l.retention_id.type_retention == "municipal")
        ):
            record.retention_amount = record.invoice_amount * record.aliquot / 100
            record.foreign_retention_amount = record.foreign_invoice_amount * record.aliquot / 100

    @api.onchange("retention_amount", "invoice_amount")
    def onchange_retention_amount(self):
        if self.env.context.get("noonchange"):
            return
        for line in self.filtered(lambda l: not l.retention_id or l.retention_id.type == "out_invoice"):
            if line.move_id and line.move_id.foreign_inverse_rate:
                ctx = self.with_context(noonchange=True).env.context
                if not line.retention_id or line.retention_id.type_retention in ("islr", "municipal"):
                    line.with_context(ctx).foreign_invoice_amount = line.invoice_amount * line.move_id.foreign_inverse_rate
                line.with_context(ctx).foreign_retention_amount = line.retention_amount * line.move_id.foreign_inverse_rate

    @api.onchange("foreign_retention_amount", "foreign_invoice_amount")
    def onchange_foreign_retention_amount(self):
        if self.env.context.get("noonchange"):
            return
        for line in self.filtered(lambda l: not l.retention_id or l.retention_id.type == "out_invoice"):
            if line.move_id and line.move_id.foreign_rate:
                ctx = self.with_context(noonchange=True).env.context
                if not line.retention_id or line.retention_id.type_retention in ("islr", "municipal"):
                    line.with_context(ctx).invoice_amount = line.foreign_invoice_amount * (1 / line.move_id.foreign_rate)
                line.with_context(ctx).retention_amount = line.foreign_retention_amount * (1 / line.move_id.foreign_rate)

    @api.onchange('edit_tax_base')
    def _onchange_edit_tax_base(self):
        for record in self:
            if not record.edit_tax_base:
                record.invoice_amount = 0.0
                record.foreign_invoice_amount = 0.0
                record._compute_line_amounts()

    @api.onchange("invoice_amount")
    def _onchange_invoice_amount_manual(self):
        for record in self:
            if record.edit_tax_base and record.foreign_currency_rate > 0:
                record.foreign_invoice_amount = record.invoice_amount * record.foreign_currency_rate
            if record.edit_tax_base:
                record._compute_line_amounts()

    @api.onchange("foreign_invoice_amount")
    def _onchange_foreign_invoice_amount_manual(self):
        for record in self:
            if record.edit_tax_base and record.foreign_currency_rate > 0:
                record.invoice_amount = record.foreign_invoice_amount / record.foreign_currency_rate
            if record.edit_tax_base:
                record._compute_line_amounts()

    # =========== CAMBIO AQUÍ ===========
    @api.constrains(
        "retention_amount",
        "foreign_retention_amount",
        "move_id"
    )
    def _constraint_amounts(self):
        for record in self:
            if record.retention_id and record.retention_id.state == 'draft':
                continue
                
            if record.retention_amount == 0 and record.foreign_retention_amount == 0:
                raise ValidationError(_("You cannot create a retention line with a zero retention amount."))

            is_vef_the_base_currency = bool(self.env.company.currency_id and self.env.company.currency_id.name in ('VEF', 'VES'))
            is_client_retention = record.retention_id and record.retention_id.type == "out_invoice"

            if (is_vef_the_base_currency and is_client_retention and record.move_id
                    and record.retention_amount > record.move_id.amount_residual):
                raise ValidationError(
                    _("The total amount of the retention is greater than the residual amount of the invoice.")
                )

    def get_invoice_paid_amount_not_related_with_retentions(self):
        """
        Returns the amount paid on the invoice that is not related with the retentions for the ISLR
        supplier retention lines.
        """
        # This method seems to calculate for a single line, but iterates. Refactoring for clarity.
        # It should likely operate on `self` which could be a recordset.
        # Assuming `self` is a single record for the logic to make sense.
        self.ensure_one()
        line = self
        
        if not (line.retention_id and line.retention_id.type_retention == 'islr'):
            return 0.0

        payable_line = line.move_id.line_ids.filtered(
            lambda l: l.account_id.account_type == "liability_payable" and l.credit > 0
        )
        if not payable_line:
            return 0.0

        partials = self.env["account.partial.reconcile"].search([
            ('credit_move_id', '=', payable_line[0].id)
        ])
        
        retention_payments = partials.mapped('debit_move_id.payment_id').filtered('is_retention')
        retention_payment_moves = retention_payments.mapped('move_id.line_ids')

        non_retention_partials = partials.filtered(lambda p: p.debit_move_id not in retention_payment_moves)
        
        invoice_paid_amount = 0.0
        for partial in non_retention_partials:
            # Logic to sum amounts in company currency
            if partial.debit_currency_id == self.env.company.currency_id:
                invoice_paid_amount += partial.amount
            else:
                # Fallback to company currency amount on the partial
                invoice_paid_amount += partial.amount


        return invoice_paid_amount
