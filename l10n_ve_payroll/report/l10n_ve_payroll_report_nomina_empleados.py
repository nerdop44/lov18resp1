
from odoo import models, api, fields, _
from odoo.tools.misc import formatLang, format_date, xlsxwriter
from odoo.tools import config, date_utils, get_lang, float_compare, float_is_zero
import datetime
import pandas as pd
import locale
#locale.setlocale(locale.LC_TIME, 'es_ES.UTF-8')
class VenezuelaReportCustomHandlerNominaEmpleados(models.AbstractModel):
    _name = 'l10n_ve_payroll.report.handler.nomina_empleados'
    _inherit = 'l10n_ve_payroll.report.handler'
    _description = 'Venezuela Payroll Report Nomina Empleados'


    def _custom_options_initializer(self, report, options, previous_options=None):
        if previous_options:
            if 'slip_ids' in previous_options:
                del previous_options['slip_ids']

        if self.env.context.get('previous_options', False):
            previous_options = None
        super()._custom_options_initializer(report, options, previous_options=previous_options)
        if 'date' in options:
            date_from_context = self.env.context.get('date_from')
            date_to_context = self.env.context.get('date_to')
            if date_from_context and date_to_context:
                options['date']['date_from'] = date_from_context
                options['date']['date_to'] = date_to_context
                options['date']['mode'] = 'range'
                options['date']['filter'] = 'custom'
                options['date']['string'] = 'Desde %s - Hasta %s' % (datetime.datetime.strptime(date_from_context, "%Y-%m-%d").strftime("%d/%m/%Y"), datetime.datetime.strptime(date_to_context, "%Y-%m-%d").strftime("%d/%m/%Y"))

                options['column_headers'] = [
                    [{'name': options['date']['string'],
                      'forced_options': {
                          'date': options['date'],
                      }
                      }],
                ]
            else:
                if previous_options:
                    if 'date' in previous_options:
                        del previous_options['date']
        slip_ids = self.env.context.get('slip_ids')
        if slip_ids:
            options['slip_ids'] = slip_ids
        else:
            if previous_options:
                if 'slip_ids' in previous_options:
                    del previous_options['slip_ids']
        self.env.context = dict(self.env.context, date_from=None, date_to=None, slip_ids=None)

    def _dynamic_lines_generator(self, report, options, all_column_groups_expression_totals):
        company_id = self.env.context.get('company_id') or self.env.company.id
        company_id = self.env['res.company'].browse(company_id)
        currency_company = company_id.currency_id
        date_from = options['date']['date_from']
        date_to = options['date']['date_to']
        slip_ids = options['slip_ids'] if 'slip_ids' in options else self.env.context.get('slip_ids')
        campo_total = 'total'
        currency_dif = options['currency_dif']
        if not currency_dif == self.env.company.currency_id.symbol:
            campo_total = 'total_usd'
        lines = []
        payslip_line_ids = self.env['hr.payslip.line'].search(
            [('date_from', '>=', date_from), ('date_to', '<=', date_to), ('slip_id.state', 'in', ['done', 'paid', 'verify']),
             ('slip_id.company_id', '=', company_id.id)])
        if slip_ids:
            payslip_line_ids = payslip_line_ids.filtered(lambda x: x.slip_id.id in slip_ids)

        x = 1
        if payslip_line_ids:
            # primera agrupación por departamento
            departamentos = payslip_line_ids.mapped('department_id')
            for d in departamentos:
                line_id = report._get_generic_line_id('hr.department', d.id)
                asignacion = payslip_line_ids.filtered(lambda x: x.department_id.id == d.id and x.code == 'TOTAL_ASIG').mapped(campo_total)
                deduccion = payslip_line_ids.filtered(lambda x: x.department_id.id == d.id and x.code == 'TOTAL_DED').mapped(campo_total)
                otros = payslip_line_ids.filtered(lambda x: x.department_id.id == d.id and x.category_id.code in ['OTROS','COMP']).mapped(campo_total)
                total = payslip_line_ids.filtered(lambda x: x.department_id.id == d.id and x.code == 'TOTAL').mapped(campo_total)
                columns_departamento = [{'name': '', 'class': 'text'},
                                        {'name': '', 'class': 'text'},
                                        {'name': '', 'class': 'text'},
                                        {'name': '', 'class': 'text'},
                                        {'name': self.format_value(sum(asignacion), currency=currency_company, blank_if_zero=True, figure_type='monetary'), 'class': 'number'},
                                        {'name': self.format_value(sum(deduccion), currency=currency_company, blank_if_zero=True, figure_type='monetary'), 'class': 'number'},
                                        {'name': self.format_value(sum(otros), currency=currency_company, blank_if_zero=True, figure_type='monetary'), 'class': 'number'},
                                        {'name': self.format_value(sum(total), currency=currency_company, blank_if_zero=True, figure_type='monetary'), 'class': 'number'}]

                lines.append((x, {
                    'id': line_id,
                    'name': d.name,
                    'style': 'background-color: #f2f2f2;',
                    'level': 0,
                    'unfoldable': False,
                    'unfolded': False,
                    'columns': columns_departamento,
                }))
                x += 1

                # segunda agrupación por empleado
                empleados = payslip_line_ids.filtered(lambda x: x.department_id.id == d.id).mapped('employee_id')
                for e in empleados:
                    line_id = report._get_generic_line_id('hr.employee', e.id)
                    asignacion = payslip_line_ids.filtered(lambda x: x.employee_id.id == e.id and x.code == 'TOTAL_ASIG').mapped(campo_total)
                    deduccion = payslip_line_ids.filtered(lambda x: x.employee_id.id == e.id and x.code == 'TOTAL_DED').mapped(campo_total)
                    otros = payslip_line_ids.filtered(lambda x: x.employee_id.id == e.id and x.category_id.code in ['OTROS','COMP']).mapped(campo_total)
                    total = payslip_line_ids.filtered(lambda x: x.employee_id.id == e.id and x.code == 'TOTAL').mapped(campo_total)
                    columns_empleado = [{'name': '', 'class': 'text'},
                                        {'name': '', 'class': 'text'},
                                        {'name': '', 'class': 'text'},
                                        {'name': '', 'class': 'text'},
                                        {'name': self.format_value(sum(asignacion), currency=currency_company, blank_if_zero=True, figure_type='monetary'), 'class': 'number'},
                                        {'name': self.format_value(sum(deduccion), currency=currency_company, blank_if_zero=True, figure_type='monetary'), 'class': 'number'},
                                        {'name': self.format_value(sum(otros), currency=currency_company, blank_if_zero=True, figure_type='monetary'), 'class': 'number'},
                                        {'name': self.format_value(sum(total), currency=currency_company, blank_if_zero=True, figure_type='monetary'), 'class': 'number'}]

                    lines.append((x, {
                        'id': line_id,
                        'name': e.name,
                        'level': 1,
                        'unfoldable': False,
                        'unfolded': False,
                        'columns': columns_empleado,
                    }))
                    x += 1

                    # tercera agrupación por reglas
                    reglas = payslip_line_ids.filtered(lambda x: x.employee_id.id == e.id and x.code not in ['TOTAL_ASIG','TOTAL_DED','TOTAL']).mapped('salary_rule_id')
                    for r in reglas:
                        linea_payslip = payslip_line_ids.filtered(lambda x: x.employee_id.id == e.id and x.salary_rule_id.id == r.id)
                        line_id = report._get_generic_line_id('hr.salary.rule', r.id)
                        codigo_concepto = r.code
                        descripcion = r.name
                        dias = ''
                        horas = ''
                        asignacion = 0
                        deduccion = 0
                        otros = 0
                        total = 0
                        if r.mostrar_cantidad == 'dias':
                            dias = payslip_line_ids.filtered(lambda x: x.employee_id.id == e.id and x.salary_rule_id.id == r.id).mapped('dias')
                            if dias:
                                #sumar todos los dias pasando a float
                                dias = sum([float(i if not i == '' else 0) for i in dias])
                                if dias == 0:
                                    dias = ''
                        elif r.mostrar_cantidad == 'horas':
                            horas = payslip_line_ids.filtered(lambda x: x.employee_id.id == e.id and x.salary_rule_id.id == r.id).mapped('horas')
                            if horas:
                                #sumar todas las horas pasando a float
                                horas = sum([float(i if not i == '' else 0) for i in horas])
                                if horas == 0:
                                    horas = ''
                        else:
                            dias = ''
                            horas = ''
                        monto_regla = payslip_line_ids.filtered(lambda x: x.employee_id.id == e.id and x.salary_rule_id.id == r.id).mapped(campo_total)
                        if r.category_id.code in ['ASIGNA','SUBS','BASIC']:
                            asignacion = sum(monto_regla)
                            deduccion = 0
                            otros = 0
                            total = sum(monto_regla)
                        elif r.category_id.code in ['DED','DESC']:
                            asignacion = 0
                            deduccion = sum(monto_regla)
                            otros = 0
                            total = sum(monto_regla)
                        else:
                            asignacion = 0
                            deduccion = 0
                            otros = sum(monto_regla)
                            total = sum(monto_regla)

                        columns_regla = [{'name': codigo_concepto, 'class': 'text', 'style': 'text-align: left;'},
                                        {'name': descripcion, 'class': 'text', 'style': 'text-align: left;'},
                                        {'name': str(dias), 'class': 'text'},
                                        {'name': str(horas), 'class': 'text'},
                                        {'name': self.format_value(asignacion, currency=currency_company, blank_if_zero=True, figure_type='monetary'), 'class': 'number'},
                                        {'name': self.format_value(deduccion, currency=currency_company, blank_if_zero=True, figure_type='monetary'), 'class': 'number'},
                                        {'name': self.format_value(otros, currency=currency_company, blank_if_zero=True, figure_type='monetary'), 'class': 'number'},
                                        {'name': self.format_value(total, currency=currency_company, blank_if_zero=True, figure_type='monetary'), 'class': 'number'}]

                        lines.append((x, {
                            'id': line_id,
                            'name': str(linea_payslip.mapped('slip_id').mapped('number')),
                            'level': 3,
                            'unfoldable': False,
                            'unfolded': False,
                            'columns': columns_regla,
                        }))
                        x += 1
        return lines