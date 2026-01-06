    ##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2015 DevIntelle Consulting Service Pvt.Ltd. (<http://devintellecs.com>).
#
##############################################################################
from odoo import fields, models, api
from datetime import datetime, timedelta,date

class HREmployeeLoanDocument(models.Model):
    _name='hr.employee.loan.document'
    _description = 'Documento de Prestamo de Empleado'

    sequ_name = fields.Char(string ='Sequence',readonly=True,copy= False)
    name = fields.Char(string = 'Name',required=True)
    employee_id = fields.Many2one('hr.employee',string = 'Employee',required=True)
    loan_id = fields.Many2one('hr.employee.loan',string = 'Loan')
    document = fields.Binary(string ='Document',required=True,copy= False)
    date = fields.Date(string = 'Date',default=date.today())
    note = fields.Text(string ='Note')
    
    
    @api.model
    def create(self, vals):
        vals['sequ_name'] = self.env['ir.sequence'].next_by_code(
            'hr.employee.loan.document') or 'LOAN/DOC/'
        result = super(HREmployeeLoanDocument, self).create(vals)
        return result
        
    
   
