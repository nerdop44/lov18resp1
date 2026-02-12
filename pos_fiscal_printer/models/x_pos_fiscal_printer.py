
from odoo import models, fields

class XPosFiscalPrinter(models.Model):
    _name = "x.pos.fiscal.printer"
    _description = "Impresora fiscal"

    name = fields.Char("Nombre")
    serial = fields.Char("Serial")
    serial_port = fields.Char("Puerto serial")
    #campo seleccion con los flags de la impresora fiscal, 00, 30
    flag_21 = fields.Selection([('00', '00'), ('30', '30')], string="Flag 21", default='00', required=True)

    #seleccion de conexion, serial, usb, api
    connection_type = fields.Selection([('serial', 'Serial'), ('usb', 'USB'), ('usb_serial', 'USB Serial'),('file', 'Archivo'), ('api', 'API')],
                                       string="Tipo de conexión", default='usb_serial', required=True)

    #url de la api
    api_url = fields.Char("URL de la API")
    x_fiscal_command_parity = fields.Selection([
        ("none", "None"),
        ("even", "Even"),
        ("odd", "Odd"),
    ], string="Paridad", default="even", required=True)

    x_fiscal_commands_time = fields.Integer("Tiempo de espera", tracking=True, default=750)
    company_id = fields.Many2one('res.company', string='Compañía', required=True, default=lambda self: self.env.company)

