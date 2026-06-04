# -*- coding: utf-8 -*-
from odoo import models, fields, api

class IntermediationCase(models.Model):
    _name = 'intermediation.case'
    _description = 'Caso de Intermediación Comercial (SENIAT)'
    _order = 'name'

    name = fields.Char(
        string="Nombre del Caso",
        required=True,
        translate=True,
        help="Ej. Agencias de Viaje y Turismo, Corredores de Seguros, Publicidad, etc."
    )

    active = fields.Boolean(
        string="Activo",
        default=True,
        help="Permite archivar o desarchivar este caso si deja de tener validez fiscal."
    )

    iva_withholding_rate = fields.Selection([
        ('0', '0% (Exento / No Territorial)'),
        ('75', '75% (Tasa Estándar)'),
        ('100', '100% (Tasa Especial por Inconsistencias)')
    ], string="Tasa Retención IVA de Comisión", default='75', required=True)

    payment_concept_id = fields.Many2one(
        'payment.concept',
        string="Concepto ISLR por Defecto",
        help="Concepto de retención de ISLR oficial del SENIAT (Generalmente Código 018 o 019).",
        domain=[('state', '=', True)]
    )

    description = fields.Text(
        string="Descripción / Base Legal",
        help="Resumen informativo de la base legal o reglamento del SENIAT aplicable."
    )
