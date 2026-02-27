from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import logging

_logger = logging.getLogger(__name__)


class AccountRetentionLine(models.Model):
    _name = "account.retention.line"
    _description = "Retention Line"

    check_company = True

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
        compute="_compute_amounts",
        store=True,
        readonly=False,
    )
    retention_amount = fields.Float(
        compute="_compute_retention_amount",
        store=True,
        readonly=False,
    )
#    aliquot = fields.Float(digits=(16, 2))
    amount_tax_ret = fields.Float(string="Retained tax")
    base_ret = fields.Float("Retained base")
    imp_ret = fields.Float(string="tax incurred")
    retention_rate = fields.Float(store=True)
    move_id = fields.Many2one("account.move", "move", ondelete="cascade", store=True)
    is_retention_client = fields.Boolean(default=True)
    display_invoice_number = fields.Char(
        string="Invoice Number", compute="_compute_display_invoice_number", store=True
    )
#    invoice_amount = fields.Float(
#        string="Taxable income",
#        digits="Tasa",
#        compute="_compute_amounts",
#        store=True,
#        readonly=False,
#    )
    invoice_total = fields.Float(string="Total invoiced", store=True)
    iva_amount = fields.Float(string="IVA")

#    retention_amount = fields.Float(
#        digits="Tasa", compute="_compute_retention_amount", store=True, readonly=False
#    )
    foreign_retention_amount = fields.Float(
        compute="_compute_retention_amount", store=True, readonly=False
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

    islr_pay_from = fields.Float(
        string="Pays from",
        compute="_compute_related_fields",
        store=True,
    )
    islr_tax_base = fields.Float(
        string="% tax base",
        compute="_compute_related_fields",
        store=True,
        readonly=False,
    )
    islr_percentage_perc = fields.Float(
        string="% tariffs",
        compute="_compute_related_fields",
        store=True,
    )
    islr_subtract_amount = fields.Float(
        string="Amount subtract tariffs",
        compute="_compute_related_fields",
        store=True,
    )

    # Montos en VEF (Bs.) — Regla universal venezolana
    foreign_invoice_amount = fields.Float(
        string="Base Imponible (Bs.)", compute="_compute_amounts", store=True, readonly=False
    )
    foreign_invoice_total = fields.Float(string="Total Factura (Bs.)")
    foreign_iva_amount = fields.Float(string="IVA (Bs.)")
    foreign_currency_rate = fields.Float(string="Tasa (Extensión de Pago)")
    foreign_currency_inverse_rate = fields.Float(string="Inverse Rate")

    # Después de la definición de tus fields (campos) y antes de tus @api.depends o @api.onchange existentes.
    # Por ejemplo, puedes ponerlo después de 'foreign_currency_rate = fields.Float(string="Rate")'

    @api.onchange('move_id')
    def _onchange_move_id_populate_fields(self):
        """
        Popula los campos de la línea de retención basados en la factura seleccionada (move_id).
        Este método se ejecuta inmediatamente al seleccionar la factura.
        Regla universal venezolana: foreign_ siempre es en Bs. (VEF)
        """
        if self.move_id:
            invoice = self.move_id
            self.invoice_total = invoice.amount_total
            self.invoice_amount = invoice.amount_untaxed
            self.iva_amount = invoice.amount_tax
            
            # Regla de Oro: Siempre convertir a VEF si la factura no está en VEF
            currency_name = invoice.currency_id.name if invoice.currency_id else ''
            is_vef = currency_name in ['VES', 'VEF']
            
            # Priorizamos fields de dual currency (Bs.)
            vef_total = getattr(invoice, 'amount_total_bs', 0.0)
            vef_untaxed = getattr(invoice, 'amount_untaxed_bs', 0.0)
            vef_iva = getattr(invoice, 'amount_tax_bs', 0.0)
            rate = getattr(invoice, 'tax_today', 0.0)
            if not rate or rate == 1.0:
                rate = getattr(invoice, 'foreign_rate', 0.0)
            if not rate:
                rate = 1.0

            # Si no es VEF o los campos duales están vacíos, forzamos conversión por tasa
            if not is_vef or not vef_total:
                vef_total = invoice.amount_total * (rate if rate else 1.0)
            if not is_vef or not vef_untaxed:
                vef_untaxed = invoice.amount_untaxed * (rate if rate else 1.0)
            if not is_vef or not vef_iva:
                vef_iva = invoice.amount_tax * (rate if rate else 1.0)

            self.foreign_invoice_total = vef_total or invoice.amount_total
            self.foreign_invoice_amount = vef_untaxed or invoice.amount_untaxed
            self.foreign_iva_amount = vef_iva or invoice.amount_tax
            self.foreign_currency_rate = rate

            self.is_retention_client = invoice.move_type in ('out_invoice', 'out_refund', 'out_debit')
            self.invoice_type = invoice.move_type

            # Limpiar campos de ISLR/Municipal al cambiar factura
            self.payment_concept_id = False
            self.economic_activity_id = False
            self._compute_retention_amount() # Forzar recalculo de otros tipos
        else:
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

    @api.depends("payment_concept_id", "move_id", "retention_id.type_retention")
    def _compute_related_fields(self):
        """
        Calcula los campos relacionados con el concepto de pago para retenciones ISLR.
        Aplica la regla universal venezolana: los montos siempre se expresan en VEF (Bs.).
        """
        for record in self:
            if not record.payment_concept_id or not record.move_id:
                record.islr_pay_from = 0.0
                record.islr_tax_base = 0.0
                record.islr_percentage_perc = 0.0
                record.islr_subtract_amount = 0.0
                continue

            if not record.move_id.partner_id.type_person_id:
                # No lanzamos error aquí para evitar bloqueos en el UI, solo advertimos
                _logger.warning("Partner %s sin tipo de persona definido para ISLR", record.move_id.partner_id.name)
                continue

            partner_person_type_id = record.move_id.partner_id.type_person_id.id
            payment_concept_lines = record.payment_concept_id.line_payment_concept_ids
            
            found = False
            for line in payment_concept_lines:
                if partner_person_type_id == line.type_person_id.id:
                    record.islr_pay_from = line.pay_from or 0.0
                    record.islr_tax_base = line.percentage_tax_base or 0.0
                    record.islr_percentage_perc = line.tariff_id.percentage if line.tariff_id else 0.0
                    record.islr_subtract_amount = line.tariff_id.amount_subtract if line.tariff_id else 0.0
                    found = True
                    break
            
            if not found:
                record.islr_pay_from = 0.0
                record.islr_tax_base = 0.0
                record.islr_percentage_perc = 0.0
                record.islr_subtract_amount = 0.0
                
    @api.onchange('payment_concept_id')
    def _onchange_payment_concept_id(self):
        """Dispara el cálculo inmediato del ISLR en la UI al seleccionar el concepto."""
        self._compute_related_fields()
        self._compute_retention_amount()

    @api.depends("move_id", "move_id.amount_untaxed", "move_id.amount_untaxed_bs")
    def _compute_amounts(self):
        """
        Sincroniza los montos base de la factura con la línea de retención.
        Fuerza la moneda extranjera a VEF (Bolívares) para retenciones.
        """
        for record in self:
            if not record.move_id:
                continue
            
            invoice = record.move_id
            # Monto base de la factura (USD)
            amount_untaxed = invoice.amount_untaxed
            # Regla de Oro: Siempre convertir a VEF si la factura no está en VEF
            currency_name = invoice.currency_id.name if invoice.currency_id else ''
            is_vef = currency_name in ['VES', 'VEF']
            
            # Montos en Bolívares (VEF)
            vef_untaxed = getattr(invoice, 'amount_untaxed_bs', 0.0)
            vef_total = getattr(invoice, 'amount_total_bs', 0.0)
            vef_iva = getattr(invoice, 'amount_tax_bs', 0.0)
            # Priorizar foreign_rate si tax_today es 1.0 (caso común de facturas en USD con compañía USD)
            rate = getattr(invoice, 'tax_today', 0.0)
            if not rate or rate == 1.0:
                rate = getattr(invoice, 'foreign_rate', 0.0)
            if not rate:
                rate = 1.0
            
            # Si no es VEF o los campos duales están vacíos, forzamos conversión por tasa
            if not is_vef or not vef_untaxed:
                vef_untaxed = amount_untaxed * (rate if rate else 1.0)
            if not is_vef or not vef_total:
                vef_total = invoice.amount_total * (rate if rate else 1.0)
            if not is_vef or not vef_iva:
                vef_iva = invoice.amount_tax * (rate if rate else 1.0)

            record.invoice_amount = amount_untaxed
            record.foreign_invoice_amount = vef_untaxed or amount_untaxed
            record.invoice_total = invoice.amount_total
            record.foreign_invoice_total = vef_total or invoice.amount_total
            
            record.iva_amount = invoice.amount_tax
            record.foreign_iva_amount = vef_iva or invoice.amount_tax
            record.foreign_currency_rate = rate

    @api.depends(
        "invoice_amount",
        "foreign_invoice_amount",
        "islr_tax_base",
        "islr_percentage_perc",
        "islr_subtract_amount",
        "foreign_currency_rate",
        "move_id",
        "payment_concept_id",
        "economic_activity_id",
        "aliquot"
    )
    def _compute_retention_amount(self):
        """
        Calcula el monto de retención ISLR para líneas de proveedor.
        Regla universal venezolana:
        - retention_amount: en la moneda de la empresa
        - foreign_retention_amount: SIEMPRE en VEF (Bs.)
          foreign_invoice_amount ya fue asignado en VEF por _compute_related_fields
        """
        islr_retention_lines = self.filtered(
            lambda l: (not l.retention_id and l.payment_concept_id)
            or (l.retention_id.type_retention == "islr")
        )
        for record in islr_retention_lines:
            # Tasa para des-sustraer en moneda empresa
            foreign_rate = record.foreign_currency_rate or 1.0

            # Retención en moneda empresa (USD)
            record.retention_amount = (
                (record.invoice_amount * (record.islr_tax_base / 100))
                * (record.islr_percentage_perc / 100)
            ) - (record.islr_subtract_amount / foreign_rate if foreign_rate else 0.0)

            # Retención en VEF (Bolívares)
            # Regla universal: foreign_retention_amount = (Base Bs * %Base * %Tarifa) - Sustraendo Bs
            record.foreign_retention_amount = (
                (record.foreign_invoice_amount * (record.islr_tax_base / 100))
                * (record.islr_percentage_perc / 100)
            ) - record.islr_subtract_amount


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

            is_vef_the_base_currency = self.env.company.currency_id == self.env.ref("base.VEF")
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


class AccountRetentionIslrLine(models.Model):
    _name = "account.retention.islr.line"
    _inherit = "account.retention.line"
    _description = "Bridge Model for ISLR Retention Line"


class AccountRetentionIvaLine(models.Model):
    _name = "account.retention.iva.line"
    _inherit = "account.retention.line"
    _description = "Bridge Model for IVA Retention Line"


class AccountRetentionMunicipalLine(models.Model):
    _name = "account.retention.municipal.line"
    _inherit = "account.retention.line"
    _description = "Bridge Model for Municipal Retention Line"
