from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import datetime
from dateutil.relativedelta import relativedelta


class HRLoanInstallmentLine(models.Model):
    _name = 'hr.employee.loan.installment.line'
    _description = 'Lineas de Cuotas'
    _order = 'date,name'
    
    name = fields.Char('Nombre')
    employee_id = fields.Many2one('hr.employee',string='Empleado',required="1")
    loan_id = fields.Many2one('hr.employee.loan',string='Préstamo',required="1", ondelete='cascade')
    date = fields.Date('Fecha')
    is_paid = fields.Boolean('Pagado')
    amount = fields.Monetary('Monto',currency_field='currency_id_dif')
    interest = fields.Monetary('Total Intereses',currency_field='currency_id_dif')
    ins_interest = fields.Monetary('Interés',currency_field='currency_id_dif')
    installment_amt = fields.Monetary('Cuota Capital' ,currency_field='currency_id_dif')
    total_installment = fields.Monetary('Total Cuota',compute='get_total_installment',currency_field='currency_id_dif')
    payslip_id = fields.Many2one('hr.payslip',string='Nómina')
    is_skip = fields.Boolean('Saltar')

    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    currency_id_dif = fields.Many2one('res.currency', string='Moneda', related='company_id.currency_id_dif', readonly=True)
    
    @api.depends('installment_amt','ins_interest')
    def get_total_installment(self):
        for line in self:
            line.total_installment = line.ins_interest + line.installment_amt
            
            
        
    def action_view_payslip(self):
        if self.payslip_id:
            return {
                'view_mode': 'form',
                'res_id': self.payslip_id.id,
                'res_model': 'hr.payslip',
                'view_type': 'form',
                'type': 'ir.actions.act_window',
                
            }

