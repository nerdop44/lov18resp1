
import pandas as pd


from datetime import datetime, timedelta, time
from pytz import timezone, UTC
from odoo.tools import date_utils

from odoo import api, Command, fields, models, tools
from odoo.addons.base.models.res_partner import _tz_get
from odoo.addons.resource.models.utils import float_to_time, HOURS_PER_DAY
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools import float_compare, format_date
from odoo.tools.float_utils import float_round
from odoo.tools.misc import format_date
from odoo.tools.translate import _
from odoo.osv import expression

class HrLeave(models.Model):
    _inherit = 'hr.leave'

    dias_habiles = fields.Integer(string="Días Hábiles", compute="_compute_dias_habiles", store=True)
    dias_fer_desc = fields.Integer(string="Días Feriados y Descanso", compute="_compute_dias_fer_desc", store=True)

    vaca_disponible = fields.Integer(string="Días Disponibles", compute="_compute_disponibles", store=True)
    dias_a_disfrutar = fields.Integer(string="Días a Disfrutar")

    is_vaca = fields.Boolean(string="Es Vacaciones", compute="_compute_is_vaca", store=True)


    @api.depends('holiday_status_id')
    def _compute_is_vaca(self):
        for rec in self:
            if rec.holiday_status_id.id == self.env.ref('hr_holidays.holiday_status_cl').id:
                rec.is_vaca = True
            else:
                rec.is_vaca = False

    @api.onchange('dias_a_disfrutar')
    def _onchange_dias_a_disfrutar(self):
        for rec in self:
            if rec.holiday_status_id.id == self.env.ref('hr_holidays.holiday_status_cl').id and rec.employee_id:
                if rec.dias_a_disfrutar > rec.vaca_disponible:
                    raise ValidationError(_("No puede solicitar más días de los disponibles"))
                fecha_desde = rec.request_date_from
                fecha_hasta = rec.request_date_from - timedelta(days=1)
                #recorrer dias_a_disfrutar para determinar la nueva fecha hasta
                if rec.dias_a_disfrutar > 0:
                    restasntes = rec.dias_a_disfrutar
                    while restasntes > 0:
                        fecha_hasta += timedelta(days=1)
                        if fecha_hasta.weekday() != 5 and fecha_hasta.weekday() != 6:
                            restasntes -= 1
                rec.request_date_to = fecha_hasta




    @api.depends('employee_id')
    def _compute_disponibles(self):
        for rec in self:
            if rec.employee_id:
                rec.vaca_disponible = rec.employee_id.contract_id.vaca_disponible
            else:
                rec.vaca_disponible = 0

    @api.depends('request_date_from', 'request_date_to')
    def _compute_dias_habiles(self):
        for rec in self:
            dh = 0
            dfd = 0
            a = pd.date_range(start=rec.request_date_from, end=rec.request_date_to)
            for i in a:
                if i.weekday() == 5 or i.weekday() == 6:
                    dfd += 1
                else:
                    dh += 1
            rec.dias_habiles = dh
            rec.dias_fer_desc = dfd

    def action_approve(self):
        creados = []
        for rec in self:
            if rec.holiday_type == 'employee' and rec.holiday_status_id.id == self.env.ref('hr_holidays.holiday_status_cl').id:
                #contiene fin de semana
                contiene_fin_semana = False
                a = pd.date_range(start=rec.request_date_from, end=rec.request_date_to)
                for i in a:
                    if i.weekday() == 5 or i.weekday() == 6:
                        contiene_fin_semana = True


                #verifica si holiday_status_id es igual a ref hr_holidays.holiday_status_cl
                if rec.holiday_status_id.id == self.env.ref('hr_holidays.holiday_status_cl').id and contiene_fin_semana:
                    #crear un ciclo entre las fechas request_date_from y request_date_to y verifica si tienen sabado y domingo
                    #si tienen sabado y domingo entonces no se puede confirmar
                    #si no tienen sabado y domingo entonces se puede confirmar
                    fecha_inicio = rec.date_from
                    fecha_fin = rec.date_to
                    periodos = []
                    periodo_num = 0
                    x = 0
                    original_modificado = False
                    a = pd.date_range(start=fecha_inicio, end=fecha_fin)
                    for i in a:
                        if i.weekday() == 5 or i.weekday() == 6:
                            if x > 0 and not original_modificado:
                                rec.request_date_to = i - timedelta(days=1)
                                original_modificado = True
                                #commit
                                #self.env.cr.commit()
                            # si ya hay periodos, cerrar la fecha del ultimo periodo
                            if periodos and original_modificado and i.weekday() == 5:
                                periodo_num += 1
                                periodos.append([periodo_num, i - timedelta(days=5), i - timedelta(days=1)])

                            #si es sabado y es el ultimo día en a, crear el periodo request_date_from y request_date_to con la misma fecha
                            if i == a[-1] and i.weekday() == 5:
                                periodo_num += 1
                                periodos.append([periodo_num, i, i])

                            #si es domingo se crea el periodo request_date_from y request_date_to con i y un día anterior
                            if i.weekday() == 6:
                                periodo_num += 1
                                periodos.append([periodo_num, i - timedelta(days=1), i])
                        #si i es la ultima fecha en a y no es sabado ni domingo, crear el periodo request_date_from y request_date_to con la misma fecha
                        if i == a[-1] and i.weekday() != 5 and i.weekday() != 6:
                            periodo_num += 1
                            periodos.append([periodo_num, i - timedelta(days=i.weekday()), i])

                        x += 1
                    #por cada uno de los periodos, crear un nuevo registro de hr.leave con holiday_status_id == self.env.ref('l10n_ve_payroll.holiday_status_ve_vaca_des_fer').id
                    #print('data rec', rec.read())
                    print('periodos: ', periodos)
                    for periodo in periodos:
                        #agregar horas a periodo
                        periodo[1] = periodo[1].replace(hour=rec.date_from.hour, minute=rec.date_from.minute, second=rec.date_from.second)
                        periodo[2] = periodo[2].replace(hour=rec.date_to.hour, minute=rec.date_to.minute, second=rec.date_to.second)

                        if periodo[1] == rec.request_date_from:
                            rec.request_date_to = periodo[2]
                            if periodo[1].weekday() == 5 or periodo[1].weekday() == 6:
                                rec.holiday_status_id = self.env.ref('l10n_ve_payroll.holiday_status_ve_vaca_des_fer').id
                        else:
                            #number_of_days from periodo[1] to periodo[2]
                            number_of_days = (periodo[2] - periodo[1]).days + 2
                            data = {
                                'name': rec.display_name or '',
                                'state': 'confirm',
                                'user_id': rec.user_id.id,
                                'employee_id': rec.employee_id.id,
                                'holiday_type': rec.holiday_type,
                                'employee_ids': rec.employee_ids.ids,
                                'date_from': periodo[1],
                                'date_to': periodo[2],
                                'request_date_from': periodo[1].strftime('%Y-%m-%d'),
                                'request_date_to': periodo[2].strftime('%Y-%m-%d'),
                                'number_of_days': number_of_days,
                                'tz': rec.tz
                            }

                            #si periodo[1] .weekday() == 5 or .weekday() == 6 crear con holiday_status_ve_vaca_des_fer
                            if periodo[1].weekday() == 5 or periodo[1].weekday() == 6:
                                data['holiday_status_id'] = self.env.ref('l10n_ve_payroll.holiday_status_ve_vaca_des_fer').id
                            else:
                                data['holiday_status_id'] = self.env.ref('hr_holidays.holiday_status_cl').id

                            print('data: ', data)

                            #crear y confirmar
                            nuevo = self.env['hr.leave'].with_user(rec.employee_id).create(data)
                            nuevo._compute_number_of_days()
                            nuevo._compute_display_name()
                            nuevo._compute_tz()
                            #nuevo.action_confirm()
                            creados.append(nuevo)


        res = super(HrLeave, self).action_approve()
        if creados:
            for nuevo in creados:
                nuevo.with_user(rec.employee_id).action_approve()
        return res

    def name_get(self):
        res = []
        for leave in self:
            user_tz = timezone(leave.tz)
            print('user_tz',user_tz)
            date_from_utc = leave.date_from #and leave.date_from.astimezone(user_tz).date()
            date_to_utc = leave.date_to #and leave.date_to.astimezone(user_tz).date()
            if self.env.context.get('short_name'):
                if leave.leave_type_request_unit == 'hour':
                    res.append((leave.id, _("%s : %.2f hours") % (leave.name or leave.holiday_status_id.name, leave.number_of_hours_display)))
                else:
                    res.append((leave.id, _("%s : %.2f days") % (leave.name or leave.holiday_status_id.name, leave.number_of_days)))
            else:
                if leave.holiday_type == 'company':
                    target = leave.mode_company_id.name
                elif leave.holiday_type == 'department':
                    target = leave.department_id.name
                elif leave.holiday_type == 'category':
                    target = leave.category_id.name
                elif leave.employee_id:
                    target = leave.employee_id.name
                else:
                    target = ', '.join(leave.employee_ids.mapped('name'))
                display_date = format_date(self.env, date_from_utc) or ""
                if leave.leave_type_request_unit == 'hour':
                    if self.env.context.get('hide_employee_name') and 'employee_id' in self.env.context.get('group_by', []):
                        res.append((
                            leave.id,
                            _("%(person)s on %(leave_type)s: %(duration).2f hours on %(date)s",
                                person=target,
                                leave_type=leave.holiday_status_id.name,
                                duration=leave.number_of_hours_display,
                                date=display_date,
                            )
                        ))
                    else:
                        res.append((
                            leave.id,
                            _("%(person)s on %(leave_type)s: %(duration).2f hours on %(date)s",
                                person=target,
                                leave_type=leave.holiday_status_id.name,
                                duration=leave.number_of_hours_display,
                                date=display_date,
                            )
                        ))
                else:
                    if leave.number_of_days > 1 and date_from_utc and date_to_utc:
                        display_date += ' / %s' % format_date(self.env, date_to_utc) or ""
                    if not target or self.env.context.get('hide_employee_name') and 'employee_id' in self.env.context.get('group_by', []):
                        res.append((
                            leave.id,
                            _("%(leave_type)s: %(duration).2f days (%(start)s)",
                                leave_type=leave.holiday_status_id.name,
                                duration=leave.number_of_days,
                                start=display_date,
                            )
                        ))
                    else:
                        res.append((
                            leave.id,
                            _("%(person)s on %(leave_type)s: %(duration).2f days (%(start)s)",
                                person=target,
                                leave_type=leave.holiday_status_id.name,
                                duration=leave.number_of_days,
                                start=display_date,
                            )
                        ))
        return res