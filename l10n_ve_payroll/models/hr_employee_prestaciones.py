
from odoo import models, fields,api,_

class HREmpleyeePrestaciones(models.Model):
    _name = 'hr.employee.prestaciones'
    _description = 'Prestaciones Sociales'

    employee_id = fields.Many2one('hr.employee', string='Empleado', required=True)
    anio = fields.Integer(string='Año', required=True)
    mes_cump = fields.Integer(string='Mes Cumplido', required=True)
    mes_opera = fields.Integer(string='Mes Operación', required=True)
    salario_base = fields.Monetary(string='Salario Base', required=True)
    salario_base_diario = fields.Monetary(string='Salario Base Diario', required=True)
    salario_integral = fields.Monetary(string='Salario Integral', required=True)
    dias_abonados = fields.Integer(string='Días Abonados', required=True)
    dias_acumulados = fields.Integer(string='Días Acumulados')
    dias_adici = fields.Integer(string='Días Adicional', default=0)
    dias_adici_acumulado = fields.Integer(string='Días Adicional Acumulados')

    monto_presta = fields.Monetary(string='Monto Prestaciones')
    monto_presta_acumulado = fields.Monetary(string='Monto Prestaciones Acumulado')

    monto_adici = fields.Monetary(string='Monto Adicional')
    monto_adici_acumulado = fields.Monetary(string='Monto Adicional Acumulado')

    monto_retiro = fields.Monetary(string='Monto Retiro')
    monto_acumulado = fields.Monetary(string='Monto Acumulado')
    tasa_interes = fields.Monetary(string='Tasa de Interes')
    monto_interes = fields.Monetary(string='Monto Interes')
    monto_interes_acumulado = fields.Monetary(string='Monto Interes Acumulado')
    monto_total = fields.Monetary(string='Monto Total')

    company_id = fields.Many2one('res.company', string='Compañia', required=True, default=lambda self: self.env.company.id)
    currency_id = fields.Many2one('res.currency', string='Moneda', required=True, default=lambda self: self.env.company.currency_id.id)