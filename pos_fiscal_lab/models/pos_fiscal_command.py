# -*- coding: utf-8 -*-
from odoo import models, fields

class PosFiscalCommand(models.Model):
    _name = 'pos.fiscal.command'
    _description = 'Fiscal Printer Technical Command'
    _order = 'sequence, id'

    name = fields.Char(string='Name', required=True)
    code = fields.Char(string='Command Code', required=True, help="Raw command (e.g. I0Z, S1)")
    protocol = fields.Selection([
        ('hka', 'HKA (Standard)'),
        ('bixolon', 'BIXOLON'),
        ('pnp', 'PnP Protocol'),
    ], string='Protocol', default='hka', required=True)
    description = fields.Text(string='Description')
    field_template = fields.Text(string='Fields Template (JSON)', help="JSON definition of fields for data construction (e.g. price, qty)")
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('name_uniq', 'unique (name, protocol)', 'The command name must be unique per protocol!'),
        ('code_uniq', 'unique (code, protocol)', 'The command code must be unique per protocol!'),
    ]
