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
        Herencia del creador de comprobantes de retención para agrupar y emitir de forma automática
        múltiples comprobantes si hay intermediados (ej. la Aerolínea) asignados en las líneas.
        """
        self.ensure_one()
        if not self.is_intermediation:
            retention = super(AccountMove, self)._create_supplier_retention(type_retention)
            if retention:
                mediated_partner = self.invoice_line_ids.filtered(
                    lambda l: not l.display_type and l.product_id and (l.mediated_partner_id or l.product_id.mediated_partner_id)
                ).mapped(lambda l: l.mediated_partner_id or l.product_id.mediated_partner_id)
                if mediated_partner:
                    retention.write({'printed_partner_id': mediated_partner[0].id})
            return retention

        # 1. Agrupar las líneas de retención según el beneficiario real
        partner_lines = {}
        
        if type_retention == 'iva':
            # Para IVA, calculamos los datos temporales
            Retention = self.env["account.retention"]
            retention_lines_data = Retention.compute_retention_lines_data(self)
            
            for line_data in retention_lines_data:
                # Recuperar la línea de factura asociada
                inv_line = self.invoice_line_ids.filtered(lambda l: l.id == line_data.get("invoice_line_id"))
                # Si la línea tiene un intermediado (o su producto), ese es el beneficiario. Si no, es la agencia.
                partner = inv_line.mediated_partner_id or inv_line.product_id.mediated_partner_id or self.partner_id
                
                if partner not in partner_lines:
                    partner_lines[partner] = []
                partner_lines[partner].append(line_data)
                
        elif type_retention == 'islr':
            for islr_line in self.retention_islr_line_ids.filtered(lambda rl: rl.state != "cancel"):
                # Recuperar la línea de factura vinculada de forma segura
                inv_line = getattr(islr_line, 'invoice_line_id', False) or self.invoice_line_ids.filtered(
                    lambda l: l.payment_concept_id == islr_line.payment_concept_id
                )
                partner = inv_line[:1].mediated_partner_id or inv_line[:1].product_id.mediated_partner_id or self.partner_id
                
                if partner not in partner_lines:
                    partner_lines[partner] = []
                partner_lines[partner].append(islr_line)
                
        else: # municipal
            for mun_line in self.retention_municipal_line_ids.filtered(lambda rl: rl.state != "cancel"):
                inv_line = getattr(mun_line, 'invoice_line_id', False) or self.invoice_line_ids.filtered(
                    lambda l: l.economic_activity_id == mun_line.economic_activity_id
                )
                partner = inv_line[:1].mediated_partner_id or inv_line[:1].product_id.mediated_partner_id or self.partner_id
                
                if partner not in partner_lines:
                    partner_lines[partner] = []
                partner_lines[partner].append(mun_line)

        # 2. Si no hay múltiples beneficiarios o solo hay uno, procesar con el comportamiento nativo
        if len(partner_lines) <= 1:
            retention = super(AccountMove, self)._create_supplier_retention(type_retention)
            if retention:
                mediated_partner = self.invoice_line_ids.filtered(
                    lambda l: not l.display_type and l.product_id and (l.mediated_partner_id or l.product_id.mediated_partner_id)
                ).mapped(lambda l: l.mediated_partner_id or l.product_id.mediated_partner_id)
                if mediated_partner:
                    retention.write({'printed_partner_id': mediated_partner[0].id})
            return retention

        # 3. Crear múltiples comprobantes de retención (uno para cada partner)
        journals = {
            "iva": self.env.company.iva_supplier_retention_journal_id,
            "islr": self.env.company.islr_supplier_retention_journal_id,
            "municipal": self.env.company.municipal_supplier_retention_journal_id,
        }

        Payment = self.env["account.payment"]
        Retention = self.env["account.retention"]
        created_retentions = self.env["account.retention"]
        first_retention = False

        for partner, lines in partner_lines.items():
            payment_type = "outbound"
            if self.move_type == "in_refund":
                payment_type = "inbound"

            payment_vals = {
                "payment_type": payment_type,
                "partner_type": "supplier",
                "partner_id": partner.id,
                "journal_id": journals[type_retention].id,
                "payment_type_retention": type_retention,
                "payment_method_id": self.env.ref("account.account_payment_method_manual_in").id,
                "is_retention": True,
                "foreign_rate": self.foreign_rate,
                "foreign_inverse_rate": self.foreign_inverse_rate,
                "currency_id": self.env.user.company_id.currency_id.id,
            }

            if type_retention in ('islr', 'municipal'):
                payment_vals["retention_line_ids"] = [Command.link(l.id) for l in lines]

            payment = Payment.create(payment_vals)
            retention_vals = {
                "payment_ids": [Command.link(payment.id)],
                "date_accounting": self.date,
                "date": self.date if self.move_type == "in_invoice" else False,
                "type_retention": type_retention,
                "type": "in_invoice",
                "partner_id": partner.id,
            }
            if partner != self.partner_id:
                retention_vals["printed_partner_id"] = partner.id

            if type_retention == "iva":
                for line in lines:
                    line["payment_id"] = payment.id
                retention_vals["retention_line_ids"] = [
                    Command.create(line) for line in lines
                ]
            else:
                retention_vals["retention_line_ids"] = [Command.link(l.id) for l in lines]

            retention = Retention.create(retention_vals)
            payment.compute_retention_amount_from_retention_lines()

            # Publicar la retención inmediatamente dentro del loop
            retention.action_post()
            _logger.info(
                "Retención de intermediación %s creada y publicada para partner %s (número: %s)",
                retention.id, partner.name, retention.number
            )

            created_retentions |= retention
            if not first_retention:
                first_retention = retention

        # Guardar el número concatenado directamente en la factura (por tipo)
        numbers = " / ".join(filter(None, created_retentions.mapped('number')))
        voucher_field = {
            "iva": "iva_voucher_number",
            "islr": "islr_voucher_number",
            "municipal": "municipal_voucher_number",
        }.get(type_retention)
        if voucher_field:
            self.write({voucher_field: numbers})
            _logger.info(
                "Campo %s de la factura %s actualizado a: %s",
                voucher_field, self.id, numbers
            )

        # Retornar la primera retención para satisfacer el contrato del método padre
        return first_retention

