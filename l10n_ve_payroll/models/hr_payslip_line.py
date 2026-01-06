
from odoo import models, fields, api


class HRPayslipLine(models.Model):
    _inherit = 'hr.payslip.line'

    currency_id_dif = fields.Many2one("res.currency", string="Referencia en Divisa",
                                      default=lambda self: self.env['res.currency'].search([('name', '=', 'USD')],
                                                                                           limit=1), )
    total_usd = fields.Monetary(store=True, readonly=True, compute="_total_usd", string="Total (USD)", default=0,
                                currency_field='currency_id_dif')
    dias = fields.Char(compute='_compute_dias', store=True, string="Días")
    horas = fields.Char(compute='_compute_dias', store=True, string="Horas")

    department_id = fields.Many2one('hr.department', string='Departamento', related='employee_id.department_id')

    struct_id = fields.Many2one('hr.payroll.structure', string='Estructura', related='slip_id.struct_id')

    @api.depends('total', 'slip_id.tasa_cambio')
    def _total_usd(self):
        # tax_today_id = self.env['res.currency'].search([('name', '=', 'USD')])
        for record in self:
            if record.slip_id.tasa_cambio > 0:
                record[("total_usd")] = record.total / record.slip_id.tasa_cambio
            else:
                record[("total_usd")] = 0
    @api.depends('name','total_usd', 'salary_rule_id')
    def _compute_dias(self):
        valor_dias = ""
        valor_horas = ""
        for rec in self:
            worked_days_line_ids = rec.slip_id.worked_days_line_ids
            if rec.category_id.code == 'BASIC':
                valor_dias = worked_days_line_ids.filtered(lambda x: x.code == 'WORK100').number_of_days + worked_days_line_ids.filtered(lambda x: x.code == 'AUSEP').number_of_days
            else:
                worked_days_line_ids = rec.slip_id.worked_days_line_ids.filtered(lambda x: x.code == rec.code)
                if rec.salary_rule_id.mostrar_cantidad == 'dias':
                    if len(worked_days_line_ids) > 0:
                        valor_dias = round(worked_days_line_ids.number_of_days,2)
                    else:
                        valor_dias = ""
                    valor_horas = ""
                elif rec.salary_rule_id.mostrar_cantidad == 'horas':
                    if len(worked_days_line_ids) > 0:
                        valor_horas = round(worked_days_line_ids.number_of_hours,2)
                    else:
                        valor_horas = ""
                    valor_dias = ""
                else:
                    valor_dias = ""
                    valor_horas = ""

            rec.dias = str(valor_dias)
            rec.horas = str(valor_horas)
