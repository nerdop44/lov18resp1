
from odoo import models, api, fields, _
from odoo.tools.misc import formatLang, format_date, xlsxwriter
from odoo.tools import config, date_utils, get_lang, float_compare, float_is_zero
from base64 import b64encode, b64decode
import datetime
import pandas as pd
import locale
#locale.setlocale(locale.LC_TIME, 'es_ES.UTF-8')
class VenezuelaReportCustomHandlerISLR(models.AbstractModel):
    _name = 'l10n_ve_payroll.report.handler.islr'
    _inherit = 'l10n_ve_payroll.report.handler'
    _description = 'Venezuela ISLR Report Custom Handler'


    def _custom_options_initializer(self, report, options, previous_options=None):
        options['buttons'].append({
                  'name': 'Imprimir Planillas',
                  'sequence': 10,
                  'action': 'imprimir_planillas',
                  'action_param': 'export_to_pdf',
                })
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
                self.env.context = dict(self.env.context, date_from=None, date_to=None)
        rule_employee_integral_ids = self.env.context.get('rule_employee_integral_ids')
        rule_employee_retenido_ids = self.env.context.get('rule_employee_retenido_ids')
        employee_ids = self.env.context.get('employee_ids')
        if rule_employee_integral_ids:
            options['rule_employee_integral_ids'] = rule_employee_integral_ids
        if rule_employee_retenido_ids:
            options['rule_employee_retenido_ids'] = rule_employee_retenido_ids
        if employee_ids:
            options['employee_ids'] = employee_ids
        print('options', options)

    def _dynamic_lines_generator(self, report, options, all_column_groups_expression_totals):
        options['column_headers'] = [
            [{'name': options['date']['string'],
              'forced_options': {
                  'date': options['date'],
              }
              }],
        ]
        company_id = self.env.context.get('company_id') or self.env.company.id
        company_id = self.env['res.company'].browse(company_id)
        currency_company = company_id.currency_id

        trm = 1
        currency_dif = options['currency_dif']
        if not currency_dif == self.env.company.currency_id.symbol:
            trm = self.env.company.currency_id_dif.rate

        lines = []

        rule_employee_integral_ids = options['rule_employee_integral_ids'] if 'rule_employee_integral_ids' in options else self.env.context.get('rule_employee_integral_ids')
        rule_employee_retenido_ids = options['rule_employee_retenido_ids'] if 'rule_employee_retenido_ids' in options else self.env.context.get('rule_employee_retenido_ids')
        employee_ids = options['employee_ids'] if 'employee_ids' in options else self.env.context.get('employee_ids')
        date_from = options['date']['date_from']
        date_to = options['date']['date_to']
        if rule_employee_integral_ids and rule_employee_retenido_ids and employee_ids:
            reglas = rule_employee_integral_ids + rule_employee_retenido_ids
            payslip_line_ids = self.env['hr.payslip.line'].search(
                [('date_from', '>=', date_from), ('date_to', '<=', date_to),
                 ('salary_rule_id', 'in', reglas),
                 ('slip_id.state', 'in', ['done', 'paid', 'verify']),
                 ('slip_id.company_id', '=', company_id.id)])
            lines_employee = self.env['hr.employee'].search([('id', 'in', employee_ids)])

            x = 0
            for l in lines_employee:
                lines_payslip = payslip_line_ids.filtered(lambda x: x.employee_id.id == l.id)
                if lines_payslip:
                    line_id = report._get_generic_line_id('hr.employee', l.id)
                    periodo = ""
                    monto_obj_retencion = lines_payslip.filtered(lambda x: x.salary_rule_id.id in rule_employee_integral_ids).mapped('total')
                    porcentaje = l.islr
                    impuesto_retenido = lines_payslip.filtered(lambda x: x.salary_rule_id.id in rule_employee_retenido_ids).mapped('total')
                    monto_obj_retencion_acumulado = sum(monto_obj_retencion)
                    impuesto_retenido_acumulado = sum(impuesto_retenido)

                    columns = [{'name': '', 'class': 'text'},
                               {'name': self.format_value(sum(monto_obj_retencion), currency=currency_company, blank_if_zero=True, figure_type='monetary'), 'class': 'number'},
                               {'name': str(porcentaje) + ' %', 'class': 'percentage'},
                               {'name': self.format_value(sum(impuesto_retenido), currency=currency_company, blank_if_zero=True, figure_type='monetary'), 'class': 'number'},
                               {'name': self.format_value(monto_obj_retencion_acumulado, currency=currency_company, blank_if_zero=True, figure_type='monetary'), 'class': 'number'},
                               {'name': self.format_value(impuesto_retenido_acumulado, currency=currency_company, blank_if_zero=True, figure_type='monetary'), 'class': 'number'},
                               ]

                    lines.append((x, {
                        'id': line_id,
                        'name': '%s  %s' % (l.rif,l.name),
                        'style': 'background-color: #f2f2f2;',
                        'level': 1,
                        'unfoldable': True,
                        'unfolded': line_id in options.get('unfolded_lines'),
                        'expand_function': None,
                        'columns': columns,
                    }))
                    x += 1
                    if line_id in options.get('unfolded_lines'):


                        meses = pd.date_range(options['date']['date_from'], options['date']['date_to'], freq="1D").strftime("%B").drop_duplicates().tolist()
                        monto_obj_retencion_acumulado_mes = 0
                        impuesto_retenido_acumulado_mes = 0
                        for m in meses:
                            #buscar en lines_payslip las lineas que correspondan al mes
                            lines_payslip_mes = lines_payslip.filtered(lambda x: x.slip_id.date_from.strftime("%B") == m)
                            if lines_payslip_mes:
                                periodo = '%s - %s' % (m, lines_payslip_mes[0].slip_id.date_from.strftime("%Y"))
                                monto_obj_retencion_mes = lines_payslip_mes.filtered(lambda x: x.salary_rule_id.id in rule_employee_integral_ids).mapped('total')
                                porcentaje_mes = l.islr
                                impuesto_retenido_mes = lines_payslip_mes.filtered(lambda x: x.salary_rule_id.id in rule_employee_retenido_ids).mapped('total')
                                monto_obj_retencion_acumulado_mes += sum(monto_obj_retencion_mes)
                                impuesto_retenido_acumulado_mes += sum(impuesto_retenido_mes)

                                columns = [{'name': periodo, 'class': 'text'},
                                           {'name': self.format_value(sum(monto_obj_retencion_mes), currency=currency_company, blank_if_zero=True, figure_type='monetary'), 'class': 'number'},
                                           {'name': str(porcentaje_mes) + ' %', 'class': 'percentage'},
                                           {'name': self.format_value(sum(impuesto_retenido_mes), currency=currency_company, blank_if_zero=True, figure_type='monetary'), 'class': 'number'},
                                           {'name': self.format_value(monto_obj_retencion_acumulado_mes, currency=currency_company, blank_if_zero=True, figure_type='monetary'), 'class': 'number'},
                                           {'name': self.format_value(impuesto_retenido_acumulado_mes, currency=currency_company, blank_if_zero=True, figure_type='monetary'), 'class': 'number'},
                                           ]
                                #print(line_id)
                                lines.append((x, {
                                    'id': line_id + '~' + m,
                                    'name': '',
                                    'level': 3,
                                    'unfoldable': False,
                                    'unfolded': line_id in options.get('unfolded_lines'),
                                    'expand_function': None,
                                    'columns': columns,
                                }))
                                x += 1

        return lines

    def imprimir_planillas(self, options,export_to_pdf=False):
        company_id = self.env.context.get('company_id') or self.env.company.id
        company_id = self.env['res.company'].browse(company_id)
        rule_employee_integral_ids = options[
            'rule_employee_integral_ids'] if 'rule_employee_integral_ids' in options else self.env.context.get(
            'rule_employee_integral_ids')
        rule_employee_retenido_ids = options[
            'rule_employee_retenido_ids'] if 'rule_employee_retenido_ids' in options else self.env.context.get(
            'rule_employee_retenido_ids')
        employee_ids = options['employee_ids'] if 'employee_ids' in options else self.env.context.get('employee_ids')
        employee_ids = self.env['hr.employee'].search([('id', 'in', employee_ids)])
        date_from = options['date']['date_from']
        date_to = options['date']['date_to']
        reglas = rule_employee_integral_ids + rule_employee_retenido_ids
        employee_ids_lines = []
        #agregar a employee_ids_lines los ids de los empleados seleccionados y las lineas correspondientes
        for e in employee_ids:
            payslip_line_ids = self.env['hr.payslip.line'].search(
                [('date_from', '>=', date_from), ('date_to', '<=', date_to),
                 ('salary_rule_id', 'in', reglas),
                 ('slip_id.state', 'in', ['done', 'paid', 'verify']),
                 ('slip_id.company_id', '=', company_id.id)])
            meses = pd.date_range(options['date']['date_from'], options['date']['date_to'], freq="1D").strftime(
                "%B").drop_duplicates().tolist()
            monto_obj_retencion_acumulado_mes = 0
            impuesto_retenido_acumulado_mes = 0
            lines_print = []
            for m in meses:
                lines_payslip_mes = payslip_line_ids.filtered(lambda x: x.slip_id.date_from.strftime("%B") == m and x.employee_id.id == e.id)
                if lines_payslip_mes:
                    periodo = '%s - %s' % (m, lines_payslip_mes[0].slip_id.date_from.strftime("%Y"))
                    monto_obj_retencion_mes = lines_payslip_mes.filtered(
                        lambda x: x.salary_rule_id.id in rule_employee_integral_ids).mapped('total')
                    porcentaje_mes = e.islr
                    impuesto_retenido_mes = lines_payslip_mes.filtered(
                        lambda x: x.salary_rule_id.id in rule_employee_retenido_ids).mapped('total')
                    monto_obj_retencion_acumulado_mes += sum(monto_obj_retencion_mes)
                    impuesto_retenido_acumulado_mes += sum(impuesto_retenido_mes)
                    lines_print.append({
                        'periodo': periodo,
                        'monto_obj_retencion_mes': sum(monto_obj_retencion_mes),
                        'porcentaje_mes': porcentaje_mes,
                        'impuesto_retenido_mes': sum(impuesto_retenido_mes),
                        'monto_obj_retencion_acumulado_mes': monto_obj_retencion_acumulado_mes,
                        'impuesto_retenido_acumulado_mes': impuesto_retenido_acumulado_mes,
                    })
            employee_ids_lines.append({
                'employee_id': e,
                'lines': lines_print,
            })

        #transformar .strftime('%d/%m/%Y') a las fechas
        date_from = datetime.datetime.strptime(date_from, "%Y-%m-%d").strftime("%d/%m/%Y")
        date_to = datetime.datetime.strptime(date_to, "%Y-%m-%d").strftime("%d/%m/%Y")

        pdf = self.env['ir.actions.report'].sudo()._render_qweb_pdf("l10n_ve_payroll.template_comprobante_arc",
                                                              employee_ids,
                                                              data={'employee_ids_lines': employee_ids_lines,
                                                                    'employee_ids': employee_ids,
                                                                    'currency_id': company_id.currency_id,
                                                                    'company_id': company_id,
                                                                    'date_from': date_from,
                                                                    'date_to': date_to,
                                                                    })

        #retornar el pdf para descargar
        pdf_name = 'ComprobantesARC.pdf'
        attachment_id = self.env['ir.attachment'].create({
            'name': pdf_name,
            'datas': b64encode(pdf[0]),
            'mimetype': 'application/x-pdf'
        })
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/%s?download=true' % attachment_id.id,
            'target': 'self',
        }