# -*- coding: utf-8 -*-
from odoo import models, api, fields, _, Command
from odoo.exceptions import UserError
from odoo.tools import float_round
import logging
_logger = logging.getLogger(__name__)

class AccountRetentionLine(models.Model):
    _inherit = 'account.retention.line'

    invoice_line_id = fields.Many2one(
        'account.move.line',
        string="Línea de Factura de Origen"
    )

class AccountRetention(models.Model):
    _inherit = 'account.retention'

    is_intermediation = fields.Boolean(
        string="Es Intermediación",
        compute="_compute_is_intermediation"
    )
    
    intermediation_warning = fields.Html(
        string="Aviso de Intermediación",
        compute="_compute_intermediation_warning"
    )

    printed_partner_id = fields.Many2one(
        'res.partner',
        string="Sujeto Retenido (Impresión)",
        help="Si está definido, el comprobante impreso mostrará los datos de este partner en la cabecera en lugar del partner contable. La lógica interna no se ve afectada."
    )

    partner_is_intermediary = fields.Boolean(
        related="partner_id.is_intermediary",
        string="Socio es Intermediario"
    )

    is_mediated_retention = fields.Boolean(
        string="¿Retención con Sujeto Intermediado?",
        default=False,
        tracking=True
    )

    printed_partner_vat = fields.Char(
        related="printed_partner_id.full_vat",
        string="RIF del Intermediado",
        readonly=True
    )

    @api.onchange('is_mediated_retention', 'retention_line_ids')
    def _onchange_is_mediated_retention(self):
        for record in self:
            if record.is_mediated_retention:
                moves = record.retention_line_ids.mapped('move_id')
                if moves:
                    mediated_partners = moves.mapped('invoice_line_ids.product_id.mediated_partner_id')
                    if mediated_partners:
                        record.printed_partner_id = mediated_partners[0].id
            else:
                record.printed_partner_id = False



    @api.depends('retention_line_ids.move_id.is_intermediation')
    def _compute_is_intermediation(self):
        for retention in self:
            retention.is_intermediation = any(line.move_id.is_intermediation for line in retention.retention_line_ids if line.move_id)

    @api.depends('is_intermediation', 'retention_line_ids.move_id', 'partner_id')
    def _compute_intermediation_warning(self):
        for retention in self:
            if retention.is_intermediation:
                moves = retention.retention_line_ids.mapped('move_id').filtered(lambda m: m.is_intermediation)
                if moves:
                    move = moves[0]
                    is_agency = retention.partner_id == move.partner_id
                    
                    msg = "<div class='alert alert-info' style='margin-bottom: 10px;'>"
                    if is_agency:
                        msg += f"📢 <strong>Comprobante de Retención de Intermediación Comercial.</strong><br/>"
                        msg += f"Este comprobante corresponde a la comisión/fee de intermediación del proveedor: <strong>{retention.partner_id.name}</strong>.<br/>"
                        msg += f"Factura de origen: <strong>{move.name or move.ref or ''}</strong>."
                    else:
                        msg += f"📢 <strong>Comprobante de Retención por Intermediación de Terceros.</strong><br/>"
                        msg += f"Este comprobante corresponde a la retención realizada a cuenta del proveedor/aerolínea principal: <strong>{retention.partner_id.name}</strong>.<br/>"
                        msg += f"Factura de origen (tramitada por {move.partner_id.name}): <strong>{move.name or move.ref or ''}</strong>."
                    msg += "</div>"
                    retention.intermediation_warning = msg
                else:
                    retention.intermediation_warning = False
            else:
                retention.intermediation_warning = False

    @api.model
    def compute_retention_lines_data(self, invoice_id, payment=None):
        """
        Herencia del cálculo de la localización base para inyectar la segmentación por intermediación.
        Si la factura tiene activo el flujo de intermediación, se extrae el IVA y la base únicamente
        de las líneas físicas aplicando el porcentaje del respectivo beneficiario intermediado.
        """
        if not invoice_id.is_intermediation:
            return super(AccountRetention, self).compute_retention_lines_data(invoice_id, payment=payment)

        # Determinar alícuota de retención de IVA según la parametrización del caso o fuerza
        withholding_rate = 75.0
        if invoice_id.partner_id.force_100_retention:
            withholding_rate = 100.0
        elif invoice_id.intermediation_case_id:
            withholding_rate = float(invoice_id.intermediation_case_id.iva_withholding_rate)
        else:
            withholding_rate = invoice_id.partner_id.withholding_type_id.value or 75.0

        # Monedas y tasas para la conversión
        vef_currency = self._get_vef_currency() if self else self.env['account.retention']._get_default_foreign_currency()
        if isinstance(vef_currency, int):
            vef_currency = self.env['res.currency'].browse(vef_currency)

        invoice_currency = invoice_id.currency_id
        invoice_is_in_vef = (vef_currency and invoice_currency == vef_currency) or (
            not vef_currency and invoice_currency == self.env.company.currency_id
        )

        foreign_rate = invoice_id.foreign_rate or 1.0
        foreign_inverse_rate = 1.0 / foreign_rate if foreign_rate else 0.0
        used_rate = invoice_id.foreign_inverse_rate or 1.0

        new_res = []
        for line in invoice_id.invoice_line_ids.filtered(lambda l: not l.display_type and l.product_id):
            tax_ids = line.tax_ids.filtered(lambda t: t.amount > 0)
            if not tax_ids:
                continue

            # Determinación de tasa de retención (Caso A, B o C)
            if line.is_intermediation_commission:
                if invoice_id.intermediation_case_id and invoice_id.intermediation_case_id.iva_withholding_rate == '0':
                    rate = 0.0
                else:
                    rate = withholding_rate
            elif line.mediated_partner_id:
                if line.mediated_partner_id.force_100_retention:
                    rate = 100.0
                else:
                    rate = line.mediated_partner_id.withholding_type_id.value or 75.0
            else:
                rate = 0.0

            # IVA y base en moneda de la empresa
            invoice_amount_company = line.price_subtotal
            iva_amount_company = line.price_total - line.price_subtotal
            invoice_total_company = line.price_total

            # IVA y base en VEF (Regla universal)
            if invoice_is_in_vef:
                vef_invoice_amount = abs(invoice_amount_company)
                vef_iva_amount = abs(iva_amount_company)
                vef_invoice_total = abs(invoice_total_company)
            else:
                vef_invoice_amount = invoice_amount_company * used_rate
                vef_iva_amount = iva_amount_company * used_rate
                vef_invoice_total = invoice_total_company * used_rate

            # Cálculo de retención
            retention_amount_company = float_round(
                iva_amount_company * (rate / 100),
                precision_digits=invoice_id.company_currency_id.decimal_places,
            )
            vef_retention_amount = float_round(
                vef_iva_amount * (rate / 100),
                precision_digits=vef_currency.decimal_places if vef_currency else 2,
            )

            # Evitar líneas con retención nula
            if retention_amount_company == 0.0 and vef_retention_amount == 0.0:
                continue

            line_data = {
                "name": _("Retención IVA - Intermediación"),
                "invoice_type": invoice_id.move_type,
                "move_id": invoice_id.id,
                "invoice_line_id": line.id,
                "payment_id": payment.id if payment else None,
                "aliquot": tax_ids[0].amount,
                "invoice_amount": invoice_amount_company,
                "iva_amount": iva_amount_company,
                "invoice_total": invoice_total_company,
                "retention_amount": retention_amount_company,
                "foreign_invoice_amount": vef_invoice_amount,
                "foreign_iva_amount": vef_iva_amount,
                "foreign_invoice_total": vef_invoice_total,
                "foreign_retention_amount": vef_retention_amount,
                "foreign_currency_rate": foreign_rate,
                "foreign_currency_inverse_rate": foreign_inverse_rate,
                "related_percentage_tax_base": rate,
            }
            new_res.append(line_data)

        return new_res


class AccountMove(models.Model):
    _inherit = 'account.move'

    @api.model
    def _create_supplier_retention(self, type_retention):
        """
        Herencia del creador de comprobantes de retención para pre-completar el switch de intermediación
        y el sujeto intermediado si el partner de la factura es un intermediario.
        """
        self.ensure_one()
        retention = super(AccountMove, self)._create_supplier_retention(type_retention)
        if retention and retention.partner_id.is_intermediary:
            # Buscar en las líneas de la factura si hay algún producto con proveedor intermediado
            mediated_partners = self.invoice_line_ids.filtered(
                lambda l: not l.display_type and l.product_id
            ).mapped('product_id.mediated_partner_id')
            
            if mediated_partners:
                retention.write({
                    'is_mediated_retention': True,
                    'printed_partner_id': mediated_partners[0].id
                })
        return retention


