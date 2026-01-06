
from odoo import models, fields,api

class HREmployeeFamily(models.Model):
    _name = 'hr.employee.family'
    _description = "Familiares"

    employee_id = fields.Many2one('hr.employee', string='Empleado', required=True, help='Empleado al que pertenece el familiar')
    name = fields.Char(string='Nombre', required=True, help='Nombre del familiar')
    relationship = fields.Char(string='Parentesco', required=True, help='Parentesco del familiar')
    documento = fields.Char(string='Documento de Identidad', help='Documento de identidad del familiar')
    birthdate = fields.Date(string='Fecha de Nacimiento', required=True, help='Fecha de nacimiento del familiar')
    edad = fields.Integer(string='Edad',help='Edad del familiar', compute='_compute_edad')

    @api.depends('birthdate')
    def _compute_edad(self):
        for record in self:
            if record.birthdate:
                record.edad = (fields.Date.today() - record.birthdate).days / 365
            else:
                record.edad = 0