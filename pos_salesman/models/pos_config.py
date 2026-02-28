
from functools import partial

from odoo import models, fields


class PosConfig(models.Model):
    _inherit = 'pos.config'

    salesman_ids = fields.Many2many('hr.employee', 'hr_employee_pos_config_rel_salesman', 'pos_config_id', 'hr_employee_id', string="Vendedores")
