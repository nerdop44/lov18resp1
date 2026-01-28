
import base64
import logging
import random

from collections import defaultdict, Counter
from datetime import date, datetime
from dateutil.relativedelta import relativedelta

from odoo import api, Command, fields, models, _
from odoo.addons.hr_payroll.models.browsable_object import BrowsableObject, InputLine, WorkedDays, Payslips, ResultRules
from odoo.exceptions import UserError, ValidationError
from odoo.osv.expression import AND
from odoo.tools import float_round, date_utils, convert_file, html2plaintext, is_html_empty, format_amount
from odoo.tools.float_utils import float_compare
from odoo.tools.misc import format_date
from odoo.tools.safe_eval import safe_eval

_logger = logging.getLogger(__name__)
from datetime import datetime, timedelta
import calendar


class HRPayslip(models.Model):
    _inherit = 'hr.payslip'

    currency_id_dif = fields.Many2one("res.currency", string="Referencia en Divisa",
                                      default=lambda self: self.env['res.currency'].search([('name', '=', 'USD')],
                                                                                           limit=1), )

    apuntes_contables = fields.One2many(related='move_id.line_ids', readonly=True)

    lunes_mes = fields.Integer(store=True, compute='_calcular_lunes', string="Lunes del mes")
    lunes_periodo = fields.Integer(store=True, compute='_calcular_lunes', string="Lunes del periodo")
    wage = fields.Monetary(store=True, related='contract_id.wage', string="Salario Mensual (Bs)")
    wage_usd = fields.Monetary(store=True, readonly=True, related='contract_id.wage_usd',
                               string="Salario Mensual (USD)")
    wage_diario = fields.Float(store=True, readonly=True, compute="_wage_diario", string="Sueldo Diario (Bs)")
    wage_diario_usd = fields.Float(store=True, readonly=True, compute="_wage_diario_usd", string="Salario Diario (USD)")

    complemento = fields.Monetary(store=True, readonly=True, related='contract_id.complemento')

    tasa_cambio = fields.Float(store=True, string="Tasa de Cambio",
                               default=lambda self: self._get_default_tasa_cambio(), tracking=True, digits=(16, 4))


    resultado_incentivo_manual = fields.Boolean(default=True)

    adelanto_manual = fields.Boolean(default=True)
    adelanto = fields.Float(string="Adelanto quincenal", store=True, readonly=False, compute="_adelanto")

    pestaciones_id = fields.Many2one('hr.employee.prestaciones', string="Prestaciones Sociales")

    installment_ids = fields.Many2many('hr.employee.loan.installment.line', string='Cuotas de Préstamos')
    installment_amount = fields.Float('Monto de Cuotas', compute='get_installment_amount')
    installment_int = fields.Float('Monto Intereses', compute='get_installment_amount')

    sign_request_id = fields.Many2one('sign.request', string='Solicitud de Firma')
    pdf_signed = fields.Boolean(string='PDF Firmado', copy=False, default=False)
    net_wage_usd = fields.Monetary(store=True, string="Total (USD)", currency_field='currency_id_dif', compute='_compute_basic_net')

    def action_payslip_cancel(self):
        res = super(HRPayslip, self).action_payslip_cancel()
        for rec in self:
            if rec.pestaciones_id:
                rec.pestaciones_id.unlink()

            #descuenta vacaciones historico
            if rec.struct_id.id == self.env.ref('l10n_ve_payroll.structure_vacaciones').id:
                #busco el historico de vacaciones en el empleado, hr_employee_vacaciones
                vacaciones = self.env['hr.employee.vacaciones'].search([('employee_id', '=', rec.employee_id.id),
                                                                         ('anio', '=', rec.date_from.year)])
                dias_vaca = rec.worked_days_line_ids.filtered(lambda x: x.code == 'VACA')
                if vacaciones:
                    if dias_vaca:
                        vacaciones.dias_vaca -= dias_vaca.number_of_days
        return res

    @api.model
    def create(self, vals):
        result = super(HRPayslip, self).create(vals)
        for rec in result:
            if rec.payslip_run_id:
                rec.tasa_cambio = rec.payslip_run_id.tasa_cambio
        return result

    @api.depends('date_to', 'date_from')
    def _calcular_lunes(self):
        contador = 0
        contadort = 0
        formato = "%d/%m/%Y"

        for record in self:
            adesde = record.date_from.year
            mdesde = record.date_from.month
            ddesde = 1  # self.date_from.day
            fechadesde = str(ddesde) + '/' + str(mdesde) + '/' + str(adesde)

            ahasta = record.date_to.year
            mhasta = record.date_to.month
            # dhasta=self.date_to.day
            monthRange = calendar.monthrange(ahasta, mhasta)
            dhasta = monthRange[1]

            fechahasta = str(dhasta) + '/' + str(mhasta) + '/' + str(ahasta)
            fechadesded = datetime.strptime(fechadesde, formato)
            fechahastad = datetime.strptime(fechahasta, formato)
            while fechadesded <= fechahastad:
                if datetime.weekday(fechadesded) == 0:
                    contador += 1
                fechadesded = fechadesded + timedelta(days=1)
            record.lunes_mes = contador

        # calcular lunes del periodo con la fecha de inicio y fin del periodo
        contador = 0
        contadort = 0
        for record in self:
            fechadesded = record.date_from
            fechahastad = record.date_to
            while fechadesded <= fechahastad:
                if datetime.weekday(fechadesded) == 0:
                    contador += 1
                fechadesded = fechadesded + timedelta(days=1)
            record.lunes_periodo = contador

    # self._actualizar_tabla()

    @api.onchange('struct_id')
    def _struct_id_change(self):
        for rec in self:
            otras_entradas = [(5, 0, 0)]
            for o in rec.struct_id.input_line_type_ids:
                if o.monstar_automatico:
                    otras_entradas.append((0, 0, {
                        'input_type_id': o.id
                    }))
            rec.input_line_ids = otras_entradas

    @api.depends('wage')
    def _wage_diario(self):
        for record in self:
            record["wage_diario"] = record.wage / 30

    @api.depends('wage_usd')
    def _wage_diario_usd(self):
        for record in self:
            record["wage_diario_usd"] = record.wage_usd / 30

    @api.onchange('worked_days_line_ids')
    def _actualizar_tabla(self):
        for rec in self:
            struct_vaca_id = self.env.ref('l10n_ve_payroll.structure_vacaciones').id
            if rec.worked_days_line_ids and rec.struct_id.id == struct_vaca_id:
                pass
                #rec.worked_days_line_ids = [(5, 0, 0)]
                #calulo de días de vacaiones segun hr.leave
                #busco las vacaciones del empleado en el periodo
                # vacaciones = self.env['hr.leave'].search([('employee_id', '=', rec.employee_id.id),
                #                                             ('state', '=', 'validate'),
                #                                             ('holiday_status_id.code', '=', 'VAC')])


    @api.depends('employee_id', 'date_from', 'date_to')
    def _adelanto(self):
        for rec in self:
            monto_adelanto = 0
            rec.adelanto_manual = True
            if rec.employee_id and rec.date_from and rec.date_to:
                dominio = [('code', '=', 'ADE'),
                           ('employee_id', '=', rec.employee_id.id), ('date_from', '>=', rec.date_from),
                           ('date_to', '<=', rec.date_to)]
                if rec.number:
                    dominio.append(('slip_id.number', '!=', rec.number))

                adelantos = rec.env['hr.payslip.line'].search(dominio)
                for i in adelantos:
                    if i.slip_id != rec.id:
                        monto_adelanto += i.amount
                        rec.adelanto_manual = False
            rec.adelanto = monto_adelanto

    def _get_default_tasa_cambio(self):
        dolar = self.env['res.currency'].search([('name', '=', 'USD')])
        tasa = 1 / dolar.rate
        for rec in self:
            if rec.payslip_run_id:
                if rec.payslip_run_id.tasa_cambio:
                    if rec.payslip_run_id.tasa_cambio > 0:
                        tasa = rec.payslip_run_id.tasa_cambio
        return tasa

    @api.onchange('tasa_cambio')
    def _tasa_cambio_change(self):
        for pl in self:
            for w in pl.worked_days_line_ids:
                w._amount_usd()

    def compute_sheet(self):
        for rec in self:
            installment_ids = self.env['hr.employee.loan.installment.line'].search(
                [('employee_id', '=', rec.employee_id.id), ('loan_id.state', '=', 'done'),
                 ('is_paid', '=', False), ('date', '<=', rec.date_to)])
            if installment_ids:
                rec.installment_ids = [(6, 0, installment_ids.ids)]
            if len(self.worked_days_line_ids) > 0:
                self._actualizar_tabla()
        res = super(HRPayslip, self).compute_sheet()
        return res

    def _prepare_line_values(self, line, account_id, date, debit, credit):
        res = super(HRPayslip, self)._prepare_line_values(line, account_id, date, debit, credit)
        res['partner_id'] = self._get_partner_id(line.salary_rule_id)
        if debit > 0:
            res['debit_usd'] = line.total_usd
            res['credit_usd'] = 0
        if credit > 0:
            res['credit_usd'] = line.total_usd
            res['debit_usd'] = 0
        return res

    # def _prepare_line_values(self, line, account_id, date, debit, credit):
    # 	return {
    # 		'name': line.name,
    # 		'partner_id': self._get_partner_id(line.salary_rule_id),
    # 		'account_id': account_id,
    # 		'journal_id': line.slip_id.struct_id.journal_id.id,
    # 		'date': date,
    # 		'debit': debit,
    # 		'credit': credit,
    # 		'analytic_distribution': (line.salary_rule_id.analytic_account_id and {
    # 			line.salary_rule_id.analytic_account_id.id: 100}) or
    # 								 (line.slip_id.contract_id.analytic_account_id.id and {
    # 									 line.slip_id.contract_id.analytic_account_id.id: 100})
    # 	}

    def _get_partner_id(self, salary_rule_id):
        if salary_rule_id.origin_partner == 'empleado':
            origin_partner = self.employee_id.address_home_id.id
            # if self.employee_id.user_id:
            # 	origin_partner = self.employee_id.user_id.partner_id.id
            return origin_partner
        elif salary_rule_id.origin_partner == 'empresa':
            return self.company_id.partner_id.id
        elif salary_rule_id.origin_partner == 'ivss':
            return self.company_id.ivss_id.id
        elif salary_rule_id.origin_partner == 'banavih':
            return self.company_id.banavih_id.id
        elif salary_rule_id.origin_partner == 'otro':
            return salary_rule_id.partner_id.id

    @api.depends('tasa_cambio', 'sal_mensual')
    def _sal_mensual_usd(self):
        for record in self:
            if record.tasa_cambio > 0:
                record["sal_mensual_usd"] = record.sal_mensual / record.tasa_cambio

    @api.depends('tasa_cambio')
    def _complemento_mensual_bs(self):
        for record in self:
            if record.tasa_cambio > 0:
                record["complemento_mensual_bs"] = record.complemento_mensual * record.tasa_cambio

    @api.onchange('complemento_mensual')
    def _complemento_mensual_change(self):
        for record in self:
            if record.tasa_cambio > 0:
                record["complemento_mensual_bs"] = record.complemento_mensual * record.tasa_cambio

    @api.depends('complemento_mensual')
    def _complemento_diario(self):
        for record in self:
            record["complemento_diario"] = record.complemento_mensual / 30

    @api.depends('complemento_mensual_bs')
    def _complemeto_diario_bs(self):
        for record in self:
            record["complemento_diario_bs"] = record.complemento_mensual_bs / 30

    def _create_account_move(self, values):
        for rec in self:
            if isinstance(values, list):
                for l in values:
                    # cambiar date por date_to
                    l['date'] = rec.date_to
                    if self.env['ir.module.module'].search(
                            [('name', '=', 'account_dual_currency'), ('state', '=', 'installed')]):
                        l['tax_today'] = rec.tasa_cambio
            else:
                # cambiar date por date_to
                values['date'] = rec.date_to
                if self.env['ir.module.module'].search(
                        [('name', '=', 'account_dual_currency'), ('state', '=', 'installed')]):
                    values['tax_today'] = rec.tasa_cambio

        res = self.env['account.move'].sudo().create(values)

        for rec in res:
            # para todas las line_ids en values sumar los debitos y creditos
            # si el debito es mayor que el credito entonces crear una linea con el monto de la diferencia
            # si el credito es mayor que el debito entonces crear una linea con el monto de la diferencia
            # si el debito es igual al credito entonces no crear linea
            debito = 0
            debito_usd = 0
            credito = 0
            credito_usd = 0
            journal_id = rec.journal_id
            default_account = journal_id.default_account_id
            # print(values['line_ids'])
            for l in res.line_ids:
                debito += l.debit
                debito_usd += l.debit_usd
                credito += l.credit
                credito_usd += l.credit_usd
            diferencia = debito - credito
            diferencia_usd = debito_usd - credito_usd
            diferencia = round(diferencia, rec.company_id.currency_id.decimal_places)
            diferencia_usd = round(diferencia_usd, rec.company_id.currency_id_dif.decimal_places)
            print('diferencia', diferencia)
            print('diferencia_usd', diferencia_usd)
            if diferencia > 0 or diferencia_usd > 0:
                res.line_ids = [(0, 0, {
                    'name': 'Diferencia',
                    'account_id': default_account.id,
                    'debit': 0,
                    'debit_usd': 0,
                    'credit': abs(diferencia),
                    'credit_usd': abs(diferencia_usd),
                })]

            elif diferencia < 0 or diferencia_usd < 0:
                res.line_ids = [(0, 0, {
                    'name': 'Diferencia',
                    'account_id': default_account.id,
                    'debit': abs(diferencia),
                    'debit_usd': abs(diferencia_usd),
                    'credit': 0,
                    'credit_usd': 0,
                })]
        return res

    def action_payslip_done(self):
        res = super(HRPayslip, self).action_payslip_done()
        for rec in self:
            #procesar prestaciones
            if rec.struct_id.procesar_prestaciones:
                rec.procesar_prestaciones()

            #procesar vacaciones historico
            if rec.struct_id.id == self.env.ref('l10n_ve_payroll.structure_vacaciones').id:
                #busco el historico de vacaciones en el empleado, hr_employee_vacaciones
                vacaciones = self.env['hr.employee.vacaciones'].search([('employee_id', '=', rec.employee_id.id),
                                                                         ('anio', '=', rec.date_from.year)])
                dias_vaca = rec.worked_days_line_ids.filtered(lambda x: x.code == 'VACA')
                if vacaciones:
                    if dias_vaca:
                        vacaciones.dias_vaca += dias_vaca.number_of_days
                else:
                    if dias_vaca:
                        data = {
                            'employee_id': rec.employee_id.id,
                            'anio': rec.date_from.year,
                            'dias_vaca': dias_vaca.number_of_days,
                            'company_id': rec.company_id.id,
                        }
                        self.env['hr.employee.vacaciones'].create(data)

            #procesar cuotas de prestamos
            if rec.installment_ids:
                for installment in rec.installment_ids:
                    if not installment.is_skip:
                        installment.is_paid = True
                    installment.payslip_id = rec.id
        return res

    def procesar_prestaciones(self):
        for rec in self:
            if rec.date_to.day >= 28:
                mes_operacion = rec.date_to.month
                anio = rec.date_to.year
                dias_abonados = 0
                dias_adicional = 0
                verificar = self.env['hr.employee.prestaciones'].search([('employee_id', '=', rec.employee_id.id),
                                                                         ('anio', '=', anio),
                                                                         ('mes_opera', '=', mes_operacion)])
                if not verificar:
                    employee_id = rec.employee_id.id
                    salario_base = 0
                    salario_base_diario = 0
                    salario_integral = 0
                    salario_integral_diario = 0
                    dias_abonados = 0
                    dias_adicional = 0
                    mes_cump = 1
                    #fecha inicio de mes
                    fecha_inicio_mes = datetime(anio, mes_operacion, 1)
                    #fecha fin de mes
                    fecha_fin_mes = datetime(anio, mes_operacion, calendar.monthrange(anio, mes_operacion)[1])
                    #buscar el monto cobrado en el mes consultando los hr.payslip.line con las categorías basico y subsidio
                    category_hr_payroll_BASIC = self.env.ref('hr_payroll.BASIC').id
                    category_hr_payroll_SUBS = self.env.ref('l10n_ve_payroll.category_asignacion_subsidio').id
                    payslip_line = self.env['hr.payslip.line'].search([('category_id', 'in',
                                                                        [category_hr_payroll_BASIC,
                                                                         category_hr_payroll_SUBS]),('slip_id.date_from', '>=', fecha_inicio_mes),
                                                                          ('slip_id.date_to', '<=', fecha_fin_mes),
                                                                            ('employee_id', '=', employee_id),('slip_id.struct_id.procesar_prestaciones','=',True)])
                    line_ADEP = self.env['hr.payslip.line'].search([('code', '=', 'ADEP'), ('slip_id.date_from', '>=', fecha_inicio_mes),
                                                                          ('slip_id.date_to', '<=', fecha_fin_mes),
                                                                            ('employee_id', '=', employee_id)])
                    adelanto_prestaciones = 0
                    if line_ADEP:
                        adelanto_prestaciones = sum(line_ADEP.mapped('total'))
                    if payslip_line:
                        salario_base = sum(payslip_line.mapped('total'))
                        salario_base_diario = salario_base / 30

                        utilidades_fracionadas = (salario_base_diario * rec.contract_id.dias_utilidades)/360
                        vacaciones_fracionadas = (salario_base_diario * rec.contract_id.dias_provision_vaca)/360

                        salario_integral = salario_base_diario + utilidades_fracionadas + vacaciones_fracionadas

                        if rec.company_id.periodo_prestaciones == 'mensual':
                            dias_abonados = 5
                        else:
                            dias_abonados = 15
                            meses_incluidos = self.env['hr.employee.prestaciones'].search([('employee_id', '=', rec.employee_id.id)], order='mes_cump desc', limit=1)
                            if meses_incluidos:
                                mes_cump = meses_incluidos.mes_cump + 1
                                if (mes_cump/3).is_integer():
                                    dias_abonados = 15
                                else:
                                    dias_abonados = 0
                                if (mes_cump / 12).is_integer():
                                    dias_adicional = 2 * (mes_cump / 12)
                                    if dias_adicional > 30:
                                        dias_adicional = 30
                            else:
                                dias_abonados = 0

                    if salario_integral > 0:
                        company_id = rec.company_id.id
                        currency_id = rec.company_id.currency_id.id
                        monto_presta = salario_integral * dias_abonados
                        monto_adici = salario_integral * dias_adicional
                        tasa_interes = 15 #buscar la tasa de interes vigente en Parámetros de la regla salarial codigo TASAP


                        data = {
                            'employee_id': employee_id,
                            'anio': anio,
                            'mes_cump': mes_cump,
                            'mes_opera': mes_operacion,
                            'salario_base': salario_base,
                            'salario_base_diario': salario_base_diario,
                            'salario_integral': salario_integral,
                            'dias_abonados': dias_abonados,
                            'dias_adici': dias_adicional,
                            'monto_presta': monto_presta,
                            'monto_adici': monto_adici,
                            'tasa_interes': tasa_interes,
                            'monto_retiro': adelanto_prestaciones,
                            'company_id': company_id,
                        }
                        presta_id = self.env['hr.employee.prestaciones'].create(data)
                        if presta_id:
                            rec.pestaciones_id = presta_id.id
                            rec.message_post(body="Se ha generado el registro de prestaciones sociales para el empleado %s" % rec.employee_id.name)

    def _is_invalid(self):
        self.ensure_one()
        if self.state not in ['done', 'paid']:
            return _("La nómina debe estar en estado 'Hecha' o 'Pagada' para poder imprimir el recibo de pago.")
        return False

    def _get_payslip_lines(self):
        line_vals = []
        for payslip in self:
            if not payslip.contract_id:
                raise UserError(_("There's no contract set on payslip %s for %s. Check that there is at least a contract set on the employee form.", payslip.name, payslip.employee_id.name))

            localdict = self.env.context.get('force_payslip_localdict', None)
            if localdict is None:
                localdict = payslip._get_localdict()

            rules_dict = localdict['rules'].dict
            result_rules_dict = localdict['result_rules'].dict

            blacklisted_rule_ids = self.env.context.get('prevent_payslip_computation_line_ids', [])

            result = {}
            for rule in sorted(payslip.struct_id.rule_ids, key=lambda x: x.sequence):
                if rule.id in blacklisted_rule_ids:
                    continue
                #agregar rule_rounding al localdict con el redondeo de la moneda de la compañia
                localdict.update({
                    'result': None,
                    'result_qty': 1.0,
                    'result_rate': 100,
                    'result_name': False,
                    'rule_rounding': payslip.company_id.currency_id.rounding
                })
                if rule._satisfy_condition(localdict):
                    # Retrieve the line name in the employee's lang
                    employee_lang = payslip.employee_id.sudo().address_home_id.lang
                    # This actually has an impact, don't remove this line
                    context = {'lang': employee_lang}
                    if rule.code in localdict['same_type_input_lines']:
                        for multi_line_rule in localdict['same_type_input_lines'][rule.code]:
                            localdict['inputs'].dict[rule.code] = multi_line_rule
                            amount, qty, rate = rule._compute_rule(localdict)
                            tot_rule = amount * qty * rate / 100.0
                            #redondear el monto a los decimales de la nomenda de la compañía
                            tot_rule = float_round(tot_rule, precision_rounding=localdict['rule_rounding'])
                            print('tot_rule', tot_rule)
                            localdict = rule.category_id._sum_salary_rule_category(localdict,
                                                                                   tot_rule)
                            rule_name = payslip._get_rule_name(localdict, rule, employee_lang)
                            line_vals.append({
                                'sequence': rule.sequence,
                                'code': rule.code,
                                'name':  rule_name,
                                'note': html2plaintext(rule.note) if not is_html_empty(rule.note) else '',
                                'salary_rule_id': rule.id,
                                'contract_id': localdict['contract'].id,
                                'employee_id': localdict['employee'].id,
                                'amount': amount,
                                'quantity': qty,
                                'rate': rate,
                                'slip_id': payslip.id,
                            })

                    else:
                        amount, qty, rate = rule._compute_rule(localdict)
                        #este valor de previous_amount se deja siempre en 0 para que no lo suma en la categoría ya
                        #que afecta el monto de acuerdo a los días que vienen en worked_days
                        previous_amount = 0.0
                        #set/overwrite the amount computed for this rule in the localdict
                        tot_rule = amount * qty * rate / 100.0
                        # redondear el monto a los decimales de la nomenda de la compañía
                        tot_rule = float_round(tot_rule, precision_rounding=localdict['rule_rounding'])
                        print('tot_rule', tot_rule)
                        localdict[rule.code] = tot_rule
                        result_rules_dict[rule.code] = {'total': tot_rule, 'amount': amount, 'quantity': qty}
                        rules_dict[rule.code] = rule
                        # sum the amount for its salary category
                        localdict = rule.category_id._sum_salary_rule_category(localdict, tot_rule - previous_amount)
                        rule_name = payslip._get_rule_name(localdict, rule, employee_lang)
                        # create/overwrite the rule in the temporary results
                        result[rule.code] = {
                            'sequence': rule.sequence,
                            'code': rule.code,
                            'name': rule_name,
                            'note': html2plaintext(rule.note) if not is_html_empty(rule.note) else '',
                            'salary_rule_id': rule.id,
                            'contract_id': localdict['contract'].id,
                            'employee_id': localdict['employee'].id,
                            'amount': amount,
                            'quantity': qty,
                            'rate': rate,
                            'slip_id': payslip.id,
                        }
            line_vals += list(result.values())
        return line_vals

    @api.depends('installment_ids')
    def get_installment_amount(self):
        for payslip in self:
            amount = 0
            int_amount = 0
            if payslip.installment_ids:
                for installment in payslip.installment_ids:
                    if not installment.is_skip:
                        amount += installment.installment_amt
                    int_amount += installment.ins_interest

            payslip.installment_amount = amount
            payslip.installment_int = int_amount

    @api.onchange('employee_id')
    def onchange_employee(self):
        if self.employee_id:
            installment_ids = self.env['hr.employee.loan.installment.line'].search(
                [('employee_id', '=', self.employee_id.id), ('loan_id.state', '=', 'done'),
                 ('is_paid', '=', False), ('date', '<=', self.date_to)])
            if installment_ids:
                self.installment_ids = [(6, 0, installment_ids.ids)]

    @api.onchange('installment_ids')
    def onchange_installment_ids(self):
        if self.employee_id:
            installment_ids = self.env['hr.employee.loan.installment.line'].search(
                [('employee_id', '=', self.employee_id.id), ('loan_id.state', '=', 'done'),
                 ('is_paid', '=', False), ('date', '<=', self.date_to)])
            if installment_ids:
                self.installment_ids = [(6, 0, installment_ids.ids)]

    def send_to_sign(self):
        for rec in self:
            if rec.sign_request_id:
                raise UserError(_("El recibo de pago %s ya ha sido enviado a firmar." % rec.number))
            if rec.pdf_signed:
                raise UserError(_("El recibo de pago %s ya ha sido firmado." % rec.number))
            if rec.employee_id.work_email:
                #generar el pdf y capturar para inluir en sign.request y sign.Template
                pdf = self.env['ir.actions.report'].with_context(lang=rec.employee_id.sudo().address_home_id.lang)._render_qweb_pdf(rec.struct_id.report_id, rec.id, data={'company_id': rec.company_id})[0]
                attachment_id = self.env['ir.attachment'].create({
                    'name': rec.name,
                    'datas': base64.b64encode(pdf),
                    'res_model': 'hr.payslip',
                    'res_id': rec.id,
                    'type': 'binary',
                })
                #crear el sign.template
                template = self.env['sign.template'].create({
                    'name': rec.name,
                    'tag_ids': [(6, 0, [self.env.ref('sign.sign_template_tag_1').id])],
                    'attachment_id': attachment_id.id,
                    'sign_item_ids': [(0, 0, {
                        'name': 'Firma',
                        'responsible_id': self.env.ref('sign.sign_item_role_employee').id,
                        'type_id': self.env.ref('sign.sign_item_type_signature').id,
                        'page': 1,
                        'posX': 0.402,
                        'posY': 0.658,
                        'width': 0.2,
                        'height': 0.05,
                        'required': True,
                    })],
                })
                #crear el sign.request
                request = self.env['sign.request'].create({
                    'reference': 'Nómina %s #%s - %s' % (rec.struct_id.name, rec.number, rec.employee_id.name),
                    'template_id': template.id,
                    'request_item_ids': [(0, 0, {
                        'partner_id': rec.employee_id.address_home_id.id,
                        'access_via_link': True,
                        'role_id': self.env.ref('sign.sign_item_role_employee').id,
                    })],
                    'cc_partner_ids': [(4, rec.employee_id.address_home_id.id)],
                })
                rec.sign_request_id = request.id
            else:
                raise UserError(_("El usuario del empleado no tiene un correo electrónico configurado."))

    @api.depends('line_ids.total', 'line_ids.total_usd')
    def _compute_basic_net(self):
        line_values = (self._origin)._get_line_values(['TOTAL'])
        for payslip in self:
            print('line_values', line_values)
            payslip.basic_wage = 0 #line_values['BASIC'][payslip._origin.id]['total']
            payslip.net_wage = line_values['TOTAL'][payslip._origin.id]['total']
            payslip.net_wage_usd = line_values['TOTAL'][payslip._origin.id]['total_usd'] if 'total_usd' in line_values['TOTAL'][payslip._origin.id] else 0

    def _get_line_values(self, code_list, vals_list=None, compute_sum=False):
        if vals_list is None:
            vals_list = ['total', 'total_usd']
        valid_values = {'quantity', 'amount', 'total','total_usd'}
        if set(vals_list) - valid_values:
            raise UserError(_('The following values are not valid:\n%s', '\n'.join(list(set(vals_list) - valid_values))))
        result = defaultdict(lambda: defaultdict(lambda: dict.fromkeys(vals_list, 0)))
        if not self or not code_list:
            return result
        self.env.flush_all()
        selected_fields = ','.join('SUM(%s) AS %s' % (vals, vals) for vals in vals_list)
        self.env.cr.execute("""
            SELECT
                p.id,
                pl.code,
                %s
            FROM hr_payslip_line pl
            JOIN hr_payslip p
            ON p.id IN %s
            AND pl.slip_id = p.id
            AND pl.code IN %s
            GROUP BY p.id, pl.code
        """ % (selected_fields, '%s', '%s'), (tuple(self.ids), tuple(code_list)))
        # self = hr.payslip(1, 2)
        # request_rows = [
        #     {'id': 1, 'code': 'IP', 'total': 100, 'quantity': 1},
        #     {'id': 1, 'code': 'IP.DED', 'total': 200, 'quantity': 1},
        #     {'id': 2, 'code': 'IP', 'total': -2, 'quantity': 1},
        #     {'id': 2, 'code': 'IP.DED', 'total': -3, 'quantity': 1}
        # ]
        request_rows = self.env.cr.dictfetchall()
        # result = {
        #     'IP': {
        #         'sum': {'quantity': 2, 'total': 300},
        #         1: {'quantity': 1, 'total': 100},
        #         2: {'quantity': 1, 'total': 200},
        #     },
        #     'IP.DED': {
        #         'sum': {'quantity': 2, 'total': -5},
        #         1: {'quantity': 1, 'total': -2},
        #         2: {'quantity': 1, 'total': -3},
        #     },
        # }
        for row in request_rows:
            code = row['code']
            payslip_id = row['id']
            for vals in vals_list:
                if compute_sum:
                    result[code]['sum'][vals] += row[vals] or 0
                result[code][payslip_id][vals] += row[vals] or 0
        return result





