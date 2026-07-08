# -*- coding: utf-8 -*-
from odoo import models, fields, api

class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    is_intermediation_commission = fields.Boolean(
        string="¿Es Comisión?",
        default=False,
        help="Marque si esta línea corresponde al honorario o comisión del intermediario."
    )

    mediated_partner_id = fields.Many2one(
        'res.partner',
        string="Sujeto Intermediado",
        help="Seleccione el prestador de servicio real (ej. la aerolínea) para emitirle la retención de forma directa."
    )

    @api.onchange('product_id')
    def _onchange_product_id_intermediation(self):
        """Heredar por defecto si el producto representa una comisión de intermediación."""
        for line in self:
            if line.product_id and line.move_id.is_intermediation:
                # Si el producto contiene palabras clave como comisión, fee o corretaje, pre-marcar.
                name = (line.product_id.name or '').lower()
                if any(k in name for k in ['comision', 'fee', 'corretaje', 'honorario']):
                    line.is_intermediation_commission = True
                else:
                    line.is_intermediation_commission = False


class AccountMove(models.Model):
    _inherit = 'account.move'

    is_intermediation = fields.Boolean(
        string="Es Intermediación",
        compute="_compute_is_intermediation",
        store=True,
        readonly=False,
        help="Activa el cálculo segmentado de IVA e ISLR para múltiples beneficiarios."
    )

    intermediation_case_id = fields.Many2one(
        'intermediation.case',
        string="Caso de Intermediación",
        compute="_compute_intermediation_case_id",
        store=True,
        readonly=False,
        help="Caso tributario parametrizado para la factura."
    )

    partner_is_intermediary = fields.Boolean(
        string="Proveedor es Intermediario",
        related="partner_id.is_intermediary",
        store=False,
        readonly=True
    )

    intermediation_warning = fields.Html(
        string="Aviso de Intermediación",
        compute="_compute_intermediation_warning"
    )

    @api.depends('partner_id', 'partner_id.is_intermediary')
    def _compute_is_intermediation(self):
        for move in self:
            if move.move_type == 'in_invoice' and move.partner_id.is_intermediary:
                move.is_intermediation = True
            else:
                move.is_intermediation = False

    @api.depends('partner_id', 'partner_id.intermediation_case_id')
    def _compute_intermediation_case_id(self):
        for move in self:
            if move.move_type == 'in_invoice' and move.partner_id.intermediation_case_id:
                move.intermediation_case_id = move.partner_id.intermediation_case_id.id
            else:
                move.intermediation_case_id = False

    @api.depends('is_intermediation', 'intermediation_case_id', 'invoice_line_ids.mediated_partner_id')
    def _compute_intermediation_warning(self):
        for move in self:
            if move.is_intermediation and move.move_type == 'in_invoice':
                mediated_lines = move.invoice_line_ids.filtered(lambda l: not l.is_intermediation_commission and l.mediated_partner_id)
                
                msg = "<div class='alert alert-info' style='margin-bottom: 10px; margin-top: 10px;'>"
                msg += "📢 <strong>Factura de Intermediación Comercial activa.</strong> Al publicarse, el sistema generará automáticamente comprobantes de retención separados:<br/>"
                msg += f"• <strong>Retención A (Comisión/Fee):</strong> A nombre del intermediario <strong>{move.partner_id.name}</strong> (RIF: {move.partner_id.vat or 'N/A'}).<br/>"
                
                if mediated_lines:
                    partners_names = ", ".join(set(mediated_lines.mapped('mediated_partner_id.name')))
                    msg += f"• <strong>Retención B (Reembolso de Terceros):</strong> A nombre de: <strong>{partners_names}</strong>.<br/>"
                else:
                    msg += "• <em>Aún no se han asignado proveedores intermediados (ej. Aerolínea) en las líneas de reembolso. Asigne un Sujeto Intermediado en las líneas de producto para generar las retenciones correspondientes.</em><br/>"
                
                msg += "<small>* Los boletos de vuelos internacionales están exentos de IVA y no generarán retención de IVA.</small>"
                msg += "</div>"
                move.intermediation_warning = msg
            else:
                move.intermediation_warning = False



