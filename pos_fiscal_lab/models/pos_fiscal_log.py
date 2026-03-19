# -*- coding: utf-8 -*-
from odoo import models, fields

class PosFiscalLog(models.Model):
    _name = 'pos.fiscal.log'
    _description = 'Fiscal Printer Communication Log'
    _order = 'timestamp desc'

    timestamp = fields.Datetime(string='Timestamp', default=fields.Datetime.now, required=True)
    command_raw = fields.Char(string='Command Sent')
    response_raw = fields.Char(string='Response Received')
    interpretation = fields.Text(string='Technical Interpretation')
    protocol = fields.Selection([
        ('hka', 'HKA'),
        ('bixolon', 'BIXOLON'),
        ('pnp', 'PnP'),
    ], string='Protocol')
    user_id = fields.Many2one('res.users', string='Technical User', default=lambda self: self.env.user)
