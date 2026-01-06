
from odoo import models, fields,api,_

class HREmpleyeeVacaciones(models.Model):
    _name = 'hr.employee.vacaciones'
    _description = 'Historico de Vacaciones'

    employee_id = fields.Many2one('hr.employee', string='Empleado', required=True)
    anio = fields.Integer(string='Año', required=True)
    dias_vaca = fields.Integer(string='Días disfrutados', required=True)
    company_id = fields.Many2one('res.company', string='Compañia', required=True, default=lambda self: self.env.company.id)