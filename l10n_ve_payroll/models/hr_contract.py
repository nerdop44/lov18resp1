
from odoo import models, fields,api
from datetime import date, datetime, timedelta
from dateutil import relativedelta

class HRContact(models.Model):
    _inherit = 'hr.contract'

    currency_id_dif = fields.Many2one("res.currency", 
        string="Referencia en Divisa",
        default=lambda self: self.env['res.currency'].search([('name', '=', 'USD')], limit=1),)

    @api.depends('wage','currency_id_dif','currency_id')
    def _amount_all_usd(self):
        """
        Compute the total amounts of the SO.
        """
        for record in self:
            if record.currency_id_dif.name == record.currency_id.name:
                record[("amount_total_usd")] = record.wage
            if record.currency_id_dif.name != record.currency_id.name:
                record[("amount_total_usd")] = record.wage * record.currency_id_dif.rate
            if record.currency_id.name != 'VEF':
                if record.currency_id.rate > record.currency_id_dif.rate:
                    dif= (record.currency_id.rate - record.currency_id_dif.rate) / record.currency_id_dif.rate 
                    dif = dif + 1.00
                    record[("amount_total_usd")] = record.wage / dif
                if record.currency_id.rate < record.currency_id_dif.rate:
                    dif= (record.currency_id_dif.rate - record.currency_id.rate) / record.currency_id.rate
                    dif = dif + 1.00
                    record[("amount_total_usd")] = record.wage * dif

    @api.depends('amount_total_usd','tax_today')
    def _amount_all_usd_bs(self):
        """
        Compute the total amounts of the SO.
        """
        for record in self:
            record[("wage")] = record.amount_total_usd * record.tax_today

    @api.depends('currency_id_dif')
    def _name_ref(self):
        """
        Compute the total amounts of the SO.
        """
        for record in self:
            record[("name_rate")] = record.currency_id_dif.currency_unit_label
    
    @api.depends('currency_id_dif','currency_id')
    def _tax_today(self):
        """
        Compute the total amounts of the SO.
        """
        for record in self:
            if record.currency_id_dif.rate:
                if record.currency_id_dif.name == record.currency_id.name:
                    record[("tax_today")] = 1
                if record.currency_id_dif.name != record.currency_id.name:
                    record[("tax_today")] = record.currency_id.rate / record.currency_id_dif.rate


    tax_today= fields.Float(readonly=True, compute="_tax_today", default=0)
    name_rate= fields.Char(readonly=True, compute='_name_ref', default="Indefinido")
    basado_usd = fields.Boolean('Basado en USD')
    wage_usd = fields.Monetary(string='Salario Mensual (USD)', tracking=True, default=0, currency_field='currency_id_dif')
    complemento = fields.Monetary(store=True, string='Bono Alimentación (USD)', currency_field='currency_id_dif')

    HED = fields.Monetary(string='Hora extra diurna (Bs)', tracking=True, default=0)
    HEN = fields.Monetary(string='Hora extra nocturna (Bs)', tracking=True, default=0)


    HED_usd = fields.Monetary(string='Hora extra diurna (USD)', tracking=True, default=0, currency_field='currency_id_dif')
    HEN_usd = fields.Monetary(string='Hora extra nocturna (USD)', tracking=True, default=0, currency_field='currency_id_dif')



    anios_antiguedad = fields.Integer(string="Años de antiguedad", compute="_anios_antiguedad")
    meses_antiguedad = fields.Integer(string="Meses de antiguedad", compute="_anios_antiguedad")
    dias_antiguedad = fields.Integer(string="Días de antiguedad", compute="_anios_antiguedad")

    dias_provision_vaca = fields.Integer(string="Días de provisión vacaciones", compute="_dias_provision_vaca")

    sal_normal_promedio = fields.Float(string="Salario normal promedio(año anterior)", default=0.0)

    retencion_islr = fields.Boolean(string="Retención de ISLR", default=False)
    retencion_faov = fields.Boolean(string="Retención de FAOV", default=True)
    retencion_sso = fields.Boolean(string="Retención de SSO", default=True)
    retencion_rpe = fields.Boolean(string="Retención de RPE", default=True)

    contract_type_id = fields.Many2one('hr.contract.type', string='Tipo de contrato', required=True)

    dias_utilidades = fields.Integer(string='Días Utilidades', default=30)
    dias_bono_vacacional = fields.Integer(string='Días Bono Vacacional', default=15)

    vaca_disponible = fields.Integer(string='Días Vacaciones Disponibles', compute="_dias_vaca_disponibles")

    vacaciones_ids = fields.Many2many('hr.employee.vacaciones', string='Vacaciones', domain="[('employee_id', '=', employee_id)]", compute="_vacaciones_ids")


    @api.depends('employee_id')
    def _vacaciones_ids(self):
        for rec in self:
            rec.vacaciones_ids = self.env['hr.employee.vacaciones'].search([('employee_id', '=', rec.employee_id.id)])

    @api.depends('date_start', 'date_end', 'anios_antiguedad')
    def _dias_vaca_disponibles(self):
        for rec in self:
            acumulada = 0
            consumidas = 0
            if rec.vacaciones_ids:
                consumidas = sum(rec.vacaciones_ids.mapped('dias_vaca'))
            if rec.anios_antiguedad > 0:
                if rec.anios_antiguedad == 1:
                    acumulada = 15
                if rec.anios_antiguedad > 1:
                    for a in range(rec.anios_antiguedad):
                        if a >0:
                            dias = 15 + a + 1
                        else:
                            dias = 15
                        if dias > 30:
                            dias = 30
                        print('año',a, 'dias', dias)
                        acumulada += dias
            rec.vaca_disponible = acumulada - consumidas



    @api.depends('date_start','date_end')
    def _anios_antiguedad(self):
        for rec in self:
            if rec.date_start:
                date_end = date.today()
                if rec.date_end:
                    date_end = rec.date_end
                tiempo_transc = relativedelta.relativedelta(date_end, rec.date_start)
                rec.anios_antiguedad = tiempo_transc.years
                rec.meses_antiguedad = tiempo_transc.months
                rec.dias_antiguedad = tiempo_transc.days
            else:
                rec.anios_antiguedad = 0
                rec.meses_antiguedad = 0
                rec.dias_antiguedad = 0

    @api.depends('date_start','anios_antiguedad')
    def _dias_provision_vaca(self):
        for rec in self:
            if rec.anios_antiguedad >0:
                dias = 15
                for i in range(rec.anios_antiguedad):
                    if dias < 31:
                        dias += 1
                rec.dias_provision_vaca = dias
            else:
                rec.dias_provision_vaca = 0