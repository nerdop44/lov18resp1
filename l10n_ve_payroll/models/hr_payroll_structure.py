
from odoo import models, fields,api

class HRPayslipStructure(models.Model):
    _inherit = 'hr.payroll.structure'

    rule_ids = fields.One2many(
        'hr.salary.rule', 'struct_id',
        string='Salary Rules', default=lambda self: self._get_default_rule_ids())

    procesar_prestaciones = fields.Boolean(string='Procesar Prestaciones', default=False)


    @api.model
    def _get_default_rule_ids(self):
        return [(5, 0, 0)]

    def wizard_copy(self):
        return {
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'hr.payslip.structure.copy',
            'type': 'ir.actions.act_window',
            'target': 'new',
            'res_id': False,
        }