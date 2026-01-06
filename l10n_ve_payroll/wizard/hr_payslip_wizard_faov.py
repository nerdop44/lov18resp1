
from odoo import models, fields, api, _, tools
from odoo.exceptions import UserError, ValidationError
from datetime import datetime, timedelta
import time
from base64 import b64encode, b64decode

class HRPayslipWizardFAOV(models.TransientModel):
    _name = 'hr.payslip.wizard.faov'
    _description = 'Generar reportes de FAOV'

    type = fields.Selection([('txt', 'TXT'),('report', 'Reporte')], string='Tipo de Reporte', default='txt')
    structure_ids = fields.Many2many('hr.payroll.structure', string='Estructuras')
    rule_employee_integral_ids = fields.Many2many('hr.salary.rule', 'hr_salary_rule_employee_integral_rel', 'faov_id', 'rule_id', string='Reglas Salario Integral')
    rule_employee_retenido_ids = fields.Many2many('hr.salary.rule', 'hr_salary_rule_employee_retenido_rel', 'faov_id', 'rule_id', string='Regla Retenido')
    rule_company_aporte_ids = fields.Many2many('hr.salary.rule', 'hr_salary_rule_company_aporte_rel', 'faov_id', 'rule_id', string='Regla Aporte Empresa')
    date_from = fields.Date(string='Fecha Desde')
    date_to = fields.Date(string='Fecha Hasta')
    company_id = fields.Many2one('res.company', 'Company', default=lambda self: self.env.company.id)
    nro_cuenta_faov = fields.Char(string='Nro. Cuenta FAOV', related='company_id.nro_cuenta_faov')

    @api.model_create_multi
    def default_get(self, fields):
        res = super(HRPayslipWizardFAOV, self).default_get(fields)
        #agregar a date_from la fecha inicial de este mes
        date_from = datetime.now().replace(day=1).replace(month=datetime.now().month-1).strftime('%Y-%m-%d')
        #agregar a date_to la fecha ultimo día del mes
        date_to = (datetime.now().replace(day=1).replace(month=datetime.now().month) - timedelta(days=1)).strftime('%Y-%m-%d')
        res.update({
            'date_from': date_from,
            'date_to': date_to,
        })
        return res

    @api.onchange('structure_ids')
    def _onchange_structure_ids(self):
        if self.structure_ids:
            # buscar reglas con códigos TOTAL_ASIG para rule_employee_integral_ids
            rule_ids = self.env['hr.salary.rule'].search(
                    [('code', '=', 'TOTAL_ASIG'), ('struct_id', 'in', self.structure_ids.ids)])
            if rule_ids:
                    self.rule_employee_integral_ids = [(6, 0, rule_ids.ids)]
            # buscar reglas con códigos FAOV para rule_employee_retenido_ids
            rule_ids = self.env['hr.salary.rule'].search([('code', '=', 'FAOV'), ('struct_id', 'in', self.structure_ids.ids)])
            if rule_ids:
                    self.rule_employee_retenido_ids = [(6, 0, rule_ids.ids)]

            # buscar reglas con códigos AFAOV para rule_company_aporte_ids
            rule_ids = self.env['hr.salary.rule'].search([('code', '=', 'AFAOV'), ('struct_id', 'in', self.structure_ids.ids)])
            if rule_ids:
                    self.rule_company_aporte_ids = [(6, 0, rule_ids.ids)]

    @api.onchange('type')
    def _onchange_type(self):
        if not self.structure_ids:
            #buscar estructuras semanal, quincenal y mensual con ref xml l10n_ve_payroll.structure_semanal, l10n_ve_payroll.structure_quincenal, l10n_ve_payroll.structure_mensual
            struc_ids = []
            structure_semanal_id = self.env.ref('l10n_ve_payroll.structure_semanal').id
            if structure_semanal_id:
                struc_ids.append(structure_semanal_id)
            structure_quincenal_id = self.env.ref('l10n_ve_payroll.structure_quincenal').id
            if structure_quincenal_id:
                struc_ids.append(structure_quincenal_id)
            structure_mensual_id = self.env.ref('l10n_ve_payroll.structure_mensual').id
            if structure_mensual_id:
                struc_ids.append(structure_mensual_id)
            #agregar a self.structure_ids
            if struc_ids:
                self.structure_ids = [(6, 0, [structure_semanal_id, structure_quincenal_id, structure_mensual_id])]
                self._onchange_structure_ids()



    def generar_reporte(self):
        if self:
            #retornar un ir.actions.client con tag=account_report y context={'id': id del reporte}
            return {
                'type': 'ir.actions.client',
                'name': 'Reporte FAOV',
                'tag': 'account_report',
                'context': {'report_id': self.env.ref('l10n_ve_payroll.l10n_ve_payroll_report_faov').id,'structure_ids': self.structure_ids.ids,
                            'date_from': self.date_from, 'date_to': self.date_to, 'rule_employee_integral_ids': self.rule_employee_integral_ids.ids,
                            'rule_employee_retenido_ids': self.rule_employee_retenido_ids.ids, 'rule_company_aporte_ids': self.rule_company_aporte_ids.ids}
            }

    def generar_txt(self):
        if self:
            employee_ids = self.env['hr.employee'].search(
                [('active', '=', True), ('company_id', '=', self.company_id.id)])
            if not employee_ids:
                raise UserError(_('No hay empleados activos para generar el archivo'))
            if not self.date_from and not self.date_to:
                raise UserError(_('Debe ingresar las fecha'))
            if not self.nro_cuenta_faov:
                raise UserError(_('La compañía no tiene un número de cuenta FAOV'))

            # Generar el archivo TXT
            txt = ''
            for employee in employee_ids:
                if not employee.fecha_ingreso:
                    raise UserError(_('El empleado %s no tiene una fecha de ingreso') % employee.name)
                if not employee.identification_id:
                    raise UserError(_('El empleado %s no tiene una cédula de identidad') % employee.name)
                txt = txt + str(employee.nationality) + ","
                txt = txt + str(employee.identification_id).replace('.','').replace('-','') + ","
                txt = txt + str(employee.primer_nombre or '') + ","
                txt = txt + str(employee.segundo_nombre or '') + ","
                txt = txt + str(employee.primer_apellido or '') + ","
                txt = txt + str(employee.segundo_apellido or '') + ","
                #buscar el monto de las reglas FAOV para este empleado en el modelo hr.payslip.line para determinar el salario integral
                payslip_line_ids = self.env['hr.payslip.line'].search(
                    [('date_from', '>=', self.date_from), ('date_to', '<=', self.date_to),
                     ('employee_id', '=', employee.id), ('salary_rule_id', 'in', self.rule_employee_integral_ids.ids),
                     ('slip_id.struct_id', 'in', self.structure_ids.ids), ('slip_id.state', 'in', ['done','paid','verify'])])
                salario_integral = sum(payslip_line_ids.mapped('total'))

                #salario desde el contrato, completar desimales a la derecha con 2 ceros, .2f
                #salario = str(f'{employee.contract_id.wage:.2f}').replace('.','')

                salario = str(f'{salario_integral:.2f}').replace('.','')
                txt = txt + salario + ","
                #agregar fecha ingreso en formato DDMMAAAA
                txt = txt + str(employee.fecha_ingreso.strftime('%d%m%Y')) + "\n"

            # Guardar el archivo TXT en un attachment y descargarlo
            file_txt = b64encode(txt.encode('utf-8')).decode("utf-8", "ignore")
            file_txt_name = 'N%s%s.txt' % (self.nro_cuenta_faov, self.date_from.strftime('%d%m%Y'))

            file_base64 = b64encode(txt.encode('utf-8'))
            attachment_id = self.env['ir.attachment'].sudo().create({
                'name': file_txt_name,
                'datas': file_base64
            })
            return {
                'type': 'ir.actions.act_url',
                'url': '/web/content/{}?download=true'.format(attachment_id.id, ),
                'target': 'current',
            }
