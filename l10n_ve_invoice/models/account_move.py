from datetime import datetime
import json
import logging

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
from odoo.tools import format_date

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
   # _name = "account.move"
    #_inherit = ["account.move"]
    _inherit = "account.move"

    correlative = fields.Char("Control Number", copy=False, help="Sequence control number")
    invoice_reception_date = fields.Date(
        "Reception Date",
        help="Indicates when the invoice was received by the client/company",
        tracking=True,
    )
    last_payment_date = fields.Date(compute="_compute_payment_dates", store=True)
    first_payment_date = fields.Date(compute="_compute_payment_dates", store=True)
    is_contingency = fields.Boolean(related="journal_id.is_contingency")

    next_installment_date = fields.Date(compute="_compute_next_installment_date")

#    # INICIO DE LAS MODIFICACIONES SUGERIDAS PARA RELACIONAR CON account.retention.line
#    retention_iva_line_ids = fields.One2many(
#        'account.retention.line',
#        'move_id',
#        string='Retenciones de IVA',
#        domain=[('type_retention', '=', 'iva')],
#        readonly=True,
#        copy=False,
#        # Este campo One2many crea la relación inversa para las líneas de retención de IVA.
#        # 'account.retention.line' es el modelo relacionado.
#        # 'move_id' es el campo Many2one en 'account.retention.line' que conecta con este #modelo.
#    )
#    retention_islr_line_ids = fields.One2many(
#        'account.retention.line',
#        'move_id',
#        string='Retenciones de ISLR',
#        domain=[('type_retention', '=', 'islr')],
#        readonly=True,
#        copy=False,
#        # Este campo One2many crea la relación inversa para las líneas de retención de ISLR.
#        # 'account.retention.line' es el modelo relacionado.
#        # 'move_id' es el campo Many2one en 'account.retention.line' que conecta con este #modelo.
#    )
#    retention_municipal_line_ids = fields.One2many(
#        'account.retention.line',
#        'move_id',
#        string='Retenciones Municipales',
#        domain=[('type_retention', '=', 'municipal')],
#        readonly=True,
#        copy=False,
#        # Este campo One2many crea la relación inversa para las líneas de retención #municipales.
#        # 'account.retention.line' es el modelo relacionado.
#        # 'move_id' es el campo Many2one en 'account.retention.line' que conecta con este #modelo.
#    )
#    # FIN DE LAS MODIFICACIONES SUGERIDAS
   
    @api.constrains("correlative", "journal_id.is_contingency")
    def _check_correlative(self):
        AccountMove = self.env["account.move"]
        is_series_invoicing_enabled = self.company_id.group_sales_invoicing_series
        for move in self:
            if not move.is_contingency:
                continue
            if not is_series_invoicing_enabled and not move.correlative:
                raise ValidationError(
                    _(
                        "Contingency journal's invoices should always have a correlative if series "
                        "invoicing is not enabled"
                    )
                )
            repeated_moves = AccountMove.search(
                [
                    ("is_contingency", "=", True),
                    ("id", "!=", move.id),
                    ("correlative", "!=", False),
                    ("correlative", "=", move.correlative),
                    ("journal_id", "=", move.journal_id.id),
                ],
                limit=1,
            )
            if repeated_moves:
                raise UserError(
                    _("The correlative must be unique per journal when using a contingency journal")
                )

    @api.depends("amount_residual")
    def _compute_payment_dates(self):
        def clear_dates(move):
            move.last_payment_date = False
            move.first_payment_date = False

        for move in self:
            if not move.is_invoice(include_receipts=True) and move.state != "posted":
                clear_dates(move)
                continue

            is_invoice_payment_widget = bool(move.invoice_payments_widget)
            if not is_invoice_payment_widget:
                clear_dates(move)
                continue

            payments = move.invoice_payments_widget
            if not payments or not payments.get("content", False):
                clear_dates(move)
                continue

            last_date = False
            first_date = False

            dates = list()

            for payment in payments.get("content"):
                if not self.validate_payment(payment):
                    continue

                dates.append(payment.get("date", False))

            if len(dates) > 0:
                last_date = fields.Date.from_string(max(dates))
                first_date = fields.Date.from_string(min(dates))

            move.last_payment_date = last_date
            move.first_payment_date = first_date

    @api.model
    def validate_payment(self, payment):
        """This function was created to validate payments through external modules"""
        return True

    @api.onchange("invoice_line_ids")
    def _onchange_invoice_line_ids(self):
        """
        Limit the number of products that can be added to the invoice
        """
        if self.invoice_line_ids and self.move_type in ["out_invoice", "out_refund"]:
            max_product_invoice = self.company_id.max_product_invoice
            if len(self.invoice_line_ids) > max_product_invoice:
                raise ValidationError(
                    _("You can not add more than %s products to the invoice." % max_product_invoice)
                )

    @api.depends("filter_partner")
    def _compute_partner_id_domain(self):
        for move in self:
            company_id = move.company_id.id
            extend_domain = [("type", "!=", "private"), ("company_id", "in", (False, company_id))]
            domain = move.get_partner_domain(extend=extend_domain)

            move.update({"partner_id_domain": json.dumps(domain)})

    @api.depends("payment_term_details")
    def _compute_next_installment_date(self):
        lang = self.env["res.lang"].search([("code", "=", self.env.user.lang)])
        date_format = lang.date_format if lang else "%Y-%m-%d"
        for invoice in self:
            invoice.next_installment_date = False
            if not invoice.payment_term_details:
                invoice.next_installment_date = invoice.invoice_date_due
                continue
            for term in invoice.payment_term_details:
                term_date = datetime.strptime(term.get("date", ""), date_format).date()
                if term_date and term_date >= fields.Date.today():
                    invoice.next_installment_date = term_date
                    break

    def _post(self, soft=True):
        res = super()._post(soft)
        for move in res:
            if move.is_valid_to_sequence():
                move.correlative = move.get_sequence()
        return res

    @api.model
    def is_valid_to_sequence(self) -> bool:
        """
        Check if the invoice satisfies the conditions to associate a new sequence number to its
        correlative.

        Returns:
            True or False whether the invoice already has a sequence number or not.
        """
        journal_type = self.journal_id.type == "sale"
        is_contingency = self.journal_id.is_contingency
        is_series_invoicing_enabled = self.company_id.group_sales_invoicing_series
        is_valid = (
            not self.correlative
            and journal_type
            and (not is_contingency or is_series_invoicing_enabled)
        )

        return is_valid

    @api.model
    def get_sequence(self):
        """
        Allows the invoice to have both a generic sequence
        number or a specific one given certain conditions.

        Returns
        -------
            The next number from the sequence to be assigned.
        """

        self.ensure_one()
        is_series_invoicing_enabled = self.company_id.group_sales_invoicing_series
        sequence = self.env["ir.sequence"].sudo()
        correlative = None

        if is_series_invoicing_enabled:
            correlative = self.journal_id.series_correlative_sequence_id

            if not correlative:
                raise UserError(_("The sale's series sequence must be in the selected journal."))
            return correlative.next_by_id(correlative.id)

        correlative = sequence.search(
            [("code", "=", "invoice.correlative"), ("company_id", "=", self.env.company.id)]
        )
        if not correlative:
            correlative = sequence.create(
                {
                    "name": "Número de control",
                    "code": "invoice.correlative",
                    "padding": 5,
                }
            )
        return correlative.next_by_id(correlative.id)

    @api.model
    def _get_tax_totals(self):
        # Llama al método original para obtener los totales de impuestos
        base_lines = self.invoice_line_ids.mapped(lambda line: {
           'price_subtotal': line.price_subtotal,
           'discount': line.discount,
           'taxes': line.tax_ids,
           'record': line
        })
            
        # Llama al método de impuestos para calcular los totales
        tax_totals = self.env['account.tax']._prepare_tax_totals(base_lines, self.currency_id)
    
        # Asegúrate de que cada subtotal tenga 'formatted_amount'
        for subtotal in tax_totals.get('subtotals',[]):
            if 'formatted_amount' not in subtotal:
                subtotal['formatted_amount'] = self.env['account.move'].format_monetary(subtotal['amount'], self.currency_id)
        
        # Asegúrate de que 'foreign_subtotals' esté presente y tenga 'formatted_amount'
        if 'foreign_subtotals' in tax_totals:
            foreign_currency = self.secondary_currency_id if hasattr(self, 'secondary_currency_id') and self.secondary_currency_id else self.currency_id # Usa la moneda alternativa si está disponible, sino la moneda principal
            for subtotal in tax_totals['foreign_subtotals']:
                if 'formatted_amount' not in subtotal:
                    subtotal['formatted_amount'] = self.env['account.move'].format_monetary(subtotal['amount'], foreign_currency)

        return tax_totals
                ### Verifica que 'foreign_subtotals' esté presente
        ##if 'foreign_subtotals' not in tax_totals:
        ##    tax_totals['foreign_subtotals'] = []  # O inicializa como desees

        ##return tax_totals
