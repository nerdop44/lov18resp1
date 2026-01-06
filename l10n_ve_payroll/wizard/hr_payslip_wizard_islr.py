
from odoo import models, fields, api, _, tools
from odoo.exceptions import UserError, ValidationError
from datetime import datetime, timedelta
import time
from base64 import b64encode, b64decode

class HRPayslipWizardISLR(models.TransientModel):
    _name = 'hr.payslip.wizard.islr'
    _description = 'Generar reportes de ISLR'

    employee_ids = fields.Many2many('hr.employee', string='Empleados')
    rule_employee_integral_ids = fields.Many2many('hr.salary.rule', 'hr_salary_rule_employee_islr_integral_rel', 'islr_id', 'rule_id', string='Reglas Salario Integral')
    rule_employee_retenido_ids = fields.Many2many('hr.salary.rule', 'hr_salary_rule_employee_islr_retenido_rel', 'islr_id', 'rule_id', string='Regla Retenido')

    date_from = fields.Date(string='Fecha Desde')
    date_to = fields.Date(string='Fecha Hasta')
    company_id = fields.Many2one('res.company', 'Company', default=lambda self: self.env.company.id)

    @api.model_create_multi
    def default_get(self, fields):
        res = super(HRPayslipWizardISLR, self).default_get(fields)
        # agregar a date_from la fecha inicial del año
        date_from = datetime.now().replace(day=1).replace(month=1).strftime('%Y-%m-%d')
        # agregar a date_to la fecha ultimo día del año
        date_to = (datetime.now().replace(month=12).replace(day=31)).strftime('%Y-%m-%d')

        employee_ids = self.env['hr.employee'].search([('company_id', '=', self.env.company.id), ('active', '=', True),('islr', '>', 0)])
        if employee_ids:
            res.update({
                'employee_ids': [(6, 0, employee_ids.ids)],
            })
        payslip_line_ids = self.env['hr.payslip.line'].search(
            [('date_from', '>=', date_from), ('date_to', '<=', date_to),
             ('employee_id', 'in', employee_ids.ids),('salary_rule_id.code', '=', 'ISLR')])
        if payslip_line_ids:
            #busco las payslip
            struct_id = payslip_line_ids.mapped('struct_id')
            if struct_id:
                rule_ids = self.env['hr.salary.rule'].search(
                    [('code', '=', 'TOTAL_ASIG'), ('struct_id', 'in', struct_id.ids)])
                if rule_ids:
                    res.update({
                        'rule_employee_integral_ids': [(6, 0, rule_ids.ids)],
                    })
            rule_islr_id = payslip_line_ids.mapped('salary_rule_id')
            if rule_islr_id:
                res.update({
                    'rule_employee_retenido_ids': [(6, 0, rule_islr_id.ids)],
                })


        res.update({
            'date_from': date_from,
            'date_to': date_to,
        })
        return res

    def generar_reporte(self):
        self.ensure_one()
        if self.employee_ids:
            print('self.employee_ids', self.employee_ids.ids)
            return {
                'type': 'ir.actions.client',
                'name': 'Listado Retenciones Varias ACR-V',
                'tag': 'account_report',
                'context': {
                    'report_id': self.env.ref('l10n_ve_payroll.l10n_ve_payroll_report_islr').id,
                    'date_from': self.date_from,
                    'date_to': self.date_to,
                    'rule_employee_integral_ids': self.rule_employee_integral_ids.ids,
                    'rule_employee_retenido_ids': self.rule_employee_retenido_ids.ids,
                    'employee_ids': self.employee_ids.ids,
                    'company_id': self.company_id.id,
                }
            }
        else:
            raise UserError(_('No hay empleados seleccionados'))



