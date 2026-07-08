# -*- coding: utf-8 -*-
from odoo import models, fields

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    mediated_partner_id = fields.Many2one(
        'res.partner',
        string="Proveedor Intermediado",
        help="Si el producto es un servicio de tercero (ej. boleto aéreo), indique aquí el proveedor real (ej. aerolínea). Al generar la retención, el comprobante se imprimirá con sus datos."
    )
