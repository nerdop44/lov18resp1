
from odoo import models, fields,api

class HRPayslipInputType(models.Model):
    _inherit = 'hr.payslip.input.type'

    monstar_automatico = fields.Boolean(string="Mostrar automatico", default=True)