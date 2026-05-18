# -*- coding: utf-8 -*-
from odoo import models, api, fields, _, Command
from odoo.exceptions import UserError
import logging
_logger = logging.getLogger(__name__)

class AccountRetention(models.Model):
    _inherit = 'account.retention'

    @api.model
    def compute_retention_lines_data(self, invoice_id, payment=None):
        """
        Herencia del cálculo de la localización base para inyectar la segmentación por intermediación.
        Si la factura tiene activo el flujo de intermediación, se extrae el IVA y la base únicamente
        de las líneas marcadas como Comisión/Fee, aplicando la tasa del caso de intermediación.
        """
        res = super(AccountRetention, self).compute_retention_lines_data(invoice_id, payment=payment)
        
        if not invoice_id.is_intermediation:
            return res

        # Determinar alícuota de retención de IVA según la parametrización del caso o fuerza
        withholding_rate = 75.0
        if invoice_id.partner_id.force_100_retention or not invoice_id.partner_id.rif_valid:
            withholding_rate = 100.0
        elif invoice_id.intermediation_case_id:
            withholding_rate = float(invoice_id.intermediation_case_id.iva_withholding_rate)
        else:
            withholding_rate = invoice_id.partner_id.withholding_type_id.value or 75.0

        new_res = []
        for line_data in res:
            invoice_line = invoice_id.invoice_line_ids.filtered(lambda l: l.id == line_data.get("invoice_line_id"))
            
            # Caso A: Es la línea de comisión
            if invoice_line and invoice_line.is_intermediation_commission:
                # Si el caso de intermediación es un broker internacional, el IVA es exento (0%)
                if invoice_id.intermediation_case_id and invoice_id.intermediation_case_id.iva_withholding_rate == '0':
                    line_data["iva_amount"] = 0.0
                    line_data["foreign_iva_amount"] = 0.0
                    line_data["retention_amount"] = 0.0
                    line_data["foreign_retention_amount"] = 0.0
                else:
                    # Aplicar la retención de IVA segmentada sobre el IVA de la comisión
                    line_data["retention_amount"] = line_data["iva_amount"] * (withholding_rate / 100)
                    line_data["foreign_retention_amount"] = line_data["foreign_iva_amount"] * (withholding_rate / 100)
                new_res.append(line_data)

            # Caso B: Es línea de reembolso/terceros pero TIENE un intermediado asignado (ej. Aerolínea)
            elif invoice_line and not invoice_line.is_intermediation_commission and invoice_line.mediated_partner_id:
                # El IVA del pasaje/flete generalmente está exento (0%), pero si tuviera IVA se aplica 0%
                line_data["iva_amount"] = 0.0
                line_data["foreign_iva_amount"] = 0.0
                line_data["retention_amount"] = 0.0
                line_data["foreign_retention_amount"] = 0.0
                new_res.append(line_data)

            # Caso C: Es línea de reembolso simple (sin intermediado asignado) -> No genera retención alguna
            elif invoice_line and not invoice_line.is_intermediation_commission and not invoice_line.mediated_partner_id:
                line_data["iva_amount"] = 0.0
                line_data["foreign_iva_amount"] = 0.0
                line_data["retention_amount"] = 0.0
                line_data["foreign_retention_amount"] = 0.0
                new_res.append(line_data)
            else:
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
            return super(AccountMove, self)._create_supplier_retention(type_retention)

        # 1. Agrupar las líneas de retención según el beneficiario real
        partner_lines = {}
        
        if type_retention == 'iva':
            # Para IVA, calculamos los datos temporales
            Retention = self.env["account.retention"]
            retention_lines_data = Retention.compute_retention_lines_data(self)
            
            for line_data in retention_lines_data:
                # Recuperar la línea de factura asociada
                inv_line = self.invoice_line_ids.filtered(lambda l: l.id == line_data.get("invoice_line_id"))
                # Si la línea tiene un intermediado, ese es el beneficiario. Si no, es la agencia.
                partner = inv_line.mediated_partner_id or self.partner_id
                
                if partner not in partner_lines:
                    partner_lines[partner] = []
                partner_lines[partner].append(line_data)
                
        elif type_retention == 'islr':
            for islr_line in self.retention_islr_line_ids.filtered(lambda rl: rl.state != "cancel"):
                # Recuperar la línea de factura vinculada de forma segura
                inv_line = getattr(islr_line, 'invoice_line_id', False) or self.invoice_line_ids.filtered(
                    lambda l: l.product_id == islr_line.payment_concept_id.product_id
                )
                partner = inv_line[:1].mediated_partner_id or self.partner_id
                
                if partner not in partner_lines:
                    partner_lines[partner] = []
                partner_lines[partner].append(islr_line)
                
        else: # municipal
            for mun_line in self.retention_municipal_line_ids.filtered(lambda rl: rl.state != "cancel"):
                inv_line = getattr(mun_line, 'invoice_line_id', False)
                partner = inv_line[:1].mediated_partner_id or self.partner_id
                
                if partner not in partner_lines:
                    partner_lines[partner] = []
                partner_lines[partner].append(mun_line)

        # 2. Si no hay múltiples beneficiarios o solo hay uno, procesar con el comportamiento nativo
        if len(partner_lines) <= 1:
            return super(AccountMove, self)._create_supplier_retention(type_retention)

        # 3. Crear múltiples comprobantes de retención (uno para cada partner)
        journals = {
            "iva": self.env.company.iva_supplier_retention_journal_id,
            "islr": self.env.company.islr_supplier_retention_journal_id,
            "municipal": self.env.company.municipal_supplier_retention_journal_id,
        }
        
        Payment = self.env["account.payment"]
        Retention = self.env["account.retention"]
        last_retention = False

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

            if type_retention == "iva":
                retention_vals["retention_line_ids"] = [
                    Command.create(line) for line in lines
                ]
            else:
                retention_vals["retention_line_ids"] = [Command.link(l.id) for l in lines]

            retention = Retention.create(retention_vals)
            payment.compute_retention_amount_from_retention_lines()
            last_retention = retention

        return last_retention
