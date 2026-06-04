# -*- coding: utf-8 -*-
from odoo import models, fields, api

class ResPartner(models.Model):
    _inherit = 'res.partner'

    is_intermediary = fields.Boolean(
        string="¿Es Intermediario/Intermediado?",
        default=False,
        help="Marque si el contacto emite facturas bajo intermediación o si es prestador final que requiere fletes directos."
    )

    intermediation_case_id = fields.Many2one(
        'intermediation.case',
        string="Caso de Intermediación",
        help="Asocie el caso de intermediación tributaria parametrizado."
    )

    force_100_retention = fields.Boolean(
        string="Forzar 100% de Retención de IVA",
        default=False,
        help="Active de forma mandatoria si el proveedor presenta inconsistencias fiscales ante el SENIAT."
    )
