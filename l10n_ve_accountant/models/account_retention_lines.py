# -*- coding: utf-8 -*-
from odoo import fields, models, api, _
from odoo.exceptions import ValidationError

class AccountRetentionIvaLine(models.Model):
    _name = "account.retention.iva.line"
    _description = "Account Retention IVA Line"

    def _valid_field_parameter(self, field_name, parameter):
        return parameter == 'digits' or super()._valid_field_parameter(field_name, parameter)

    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
    ], string='Status', default='draft', readonly=True, copy=False)

    name = fields.Char(
        string="Descripción de Retención IVA",
        compute="_compute_name",
        store=True,
    )

    move_id = fields.Many2one(
        "account.move",
        string="Factura",
        required=True,
        ondelete="cascade",
        index=True,
    )
    foreign_currency_id = fields.Many2one(
        related="move_id.foreign_currency_id",
        string="Moneda Extranjera",
        store=True,
        readonly=True,
    )
    foreign_invoice_total = fields.Monetary(
        string="Total Factura ME (IVA)",
        related="move_id.foreign_total_billed",
        currency_field="foreign_currency_id",
        store=True,
        readonly=True,
    )
    foreign_currency_rate = fields.Float(
        string="Tasa de Cambio (ME)",
        related="move_id.foreign_rate",
        digits=(12, 6),
        readonly=True,
        store=True,
    )
    foreign_iva_amount = fields.Monetary(
        string="Monto IVA (ME)",
        currency_field='foreign_currency_id',
        compute='_compute_foreign_iva_amount',
        store=True,
        readonly=True,
    )
    foreign_rate = fields.Float(
        related="move_id.foreign_rate", string="Tasa Extranjera", store=True, readonly=True
    )
    foreign_inverse_rate = fields.Float(
        related="move_id.foreign_inverse_rate",
        string="Tasa Inversa Extranjera",
        store=True,
        readonly=True,
    )
    base_amount = fields.Monetary(
        string="Base Imponible",
        currency_field="company_currency_id",
        digits="Account",
    )
    retention_amount = fields.Monetary(
        string="Monto Retenido",
        currency_field="company_currency_id",
        digits="Account",
    )
    foreign_base_amount = fields.Monetary(
        string="Base Imponible (ME)",
        currency_field="foreign_currency_id",
        digits="Account",
    )
    foreign_retention_amount = fields.Monetary(
        string="Monto Retenido (ME)",
        currency_field="foreign_currency_id",
        digits="Account",
    )
    iva_amount = fields.Monetary(
        string="Monto IVA",
        related="move_id.amount_tax",
        currency_field="company_currency_id",
        store=True,
        readonly=True,
    )
    invoice_amount = fields.Monetary(
        string="Monto de Factura",
        related="move_id.amount_total",
        currency_field="company_currency_id",
        store=True,
        readonly=True,
    )
    foreign_invoice_amount = fields.Monetary(
        string="Monto Factura ME (IVA)",
        related="move_id.foreign_total_billed",
        currency_field="foreign_currency_id",
        store=True,
        readonly=True,
    )
    aliquot = fields.Float(
        string="Alicuota (%)", digits="Account", default=0.0
    )
    invoice_total = fields.Monetary(
        string="Total Factura",
        related="move_id.amount_total",
        currency_field="company_currency_id",
        store=True,
        readonly=True,
    )
    tax_id = fields.Many2one(
        "account.tax",
        string="Impuesto",
        domain="[('type_tax_use', '=', 'purchase'), ('tax_group_id.name', '=', 'IVA')]",
        ondelete="restrict",
    )
    company_currency_id = fields.Many2one(
        related="move_id.company_id.currency_id",
        string="Moneda de la Compañía",
        store=True,
        readonly=True,
    )
    move_type = fields.Selection(
        related="move_id.move_type",
        string="Tipo de Movimiento",
        store=True,
        readonly=True,
    )
    date = fields.Date(
        related="move_id.date", string="Fecha de Factura", store=True
    )

    @api.depends("move_id")
    def _compute_name(self):
        for rec in self:
            rec.name = f"{rec.move_id.name or _('Nuevo')} - {rec._description}"

    @api.depends('iva_amount', 'foreign_currency_rate', 'foreign_currency_id', 'company_currency_id')
    def _compute_foreign_iva_amount(self):
        for rec in self:
            if rec.foreign_currency_id and rec.foreign_currency_id != rec.company_currency_id and rec.foreign_currency_rate:
                rec.foreign_iva_amount = rec.iva_amount / rec.foreign_currency_rate
            else:
                rec.foreign_iva_amount = rec.iva_amount

    @api.constrains("aliquot")
    def _check_aliquot(self):
        for rec in self:
            if rec.aliquot < 0 or rec.aliquot > 100:
                raise ValidationError(_("The aliquot percentage must be between 0 and 100."))

    @api.onchange("aliquot", "base_amount", "foreign_base_amount")
    def _onchange_retention_amounts(self):
        for rec in self:
            rec.retention_amount = rec.base_amount * (rec.aliquot / 100)
            rec.foreign_retention_amount = rec.foreign_base_amount * (rec.aliquot / 100)

class AccountRetentionIslrLine(models.Model):
    _name = "account.retention.islr.line"
    _description = "Account Retention ISLR Line"

    def _valid_field_parameter(self, field_name, parameter):
        return parameter == 'digits' or super()._valid_field_parameter(field_name, parameter)

    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
    ], string='Status', default='draft', readonly=True, copy=False)

    name = fields.Char(
        string="Descripción de Retención ISLR",
        compute="_compute_name",
        store=True,
    )

    move_id = fields.Many2one(
        "account.move",
        string="Factura",
        required=True,
        ondelete="cascade",
        index=True,
    )
    related_pay_from = fields.Many2one(
        'res.partner',
        string='Pagado Desde',
        related='move_id.partner_id',
        readonly=True,
        store=True
    )
    foreign_currency_id = fields.Many2one(
        related="move_id.foreign_currency_id",
        string="Moneda Extranjera",
        store=True,
        readonly=True,
    )
    foreign_invoice_total = fields.Monetary(
        string="Total Factura ME (ISLR)",
        related="move_id.foreign_total_billed",
        currency_field="foreign_currency_id",
        store=True,
        readonly=True,
    )
    foreign_currency_rate = fields.Float(
        string="Tasa de Cambio (ME)",
        related="move_id.foreign_rate",
        digits=(12, 6),
        readonly=True,
        store=True,
    )
    foreign_iva_amount = fields.Monetary(
        string="Monto IVA (ME)",
        currency_field='foreign_currency_id',
        compute='_compute_foreign_iva_amount',
        store=True,
        readonly=True,
    )
    foreign_rate = fields.Float(
        related="move_id.foreign_rate", string="Tasa Extranjera", store=True, readonly=True
    )
    foreign_inverse_rate = fields.Float(
        related="move_id.foreign_inverse_rate",
        string="Tasa Inversa Extranjera",
        store=True,
        readonly=True,
    )
    base_amount = fields.Monetary(
        string="Base Imponible",
        currency_field="company_currency_id",
        digits="Account",
    )
    retention_amount = fields.Monetary(
        string="Monto Retenido",
        currency_field="company_currency_id",
        digits="Account",
    )
    foreign_base_amount = fields.Monetary(
        string="Base Imponible (ME)",
        currency_field="foreign_currency_id",
        digits="Account",
    )
    foreign_retention_amount = fields.Monetary(
        string="Monto Retenido (ME)",
        currency_field="foreign_currency_id",
        digits="Account",
    )
    related_percentage_fees = fields.Float(
        string="Porcentaje de Honorarios Relacionados",
        digits="Account",
    )
    iva_amount = fields.Monetary(
        string="Monto IVA",
        related="move_id.amount_tax",
        currency_field="company_currency_id",
        store=True,
        readonly=True,
    )
    invoice_amount = fields.Monetary(
        string="Monto de Factura",
        related="move_id.amount_total",
        currency_field="company_currency_id",
        store=True,
        readonly=True,
    )
    foreign_invoice_amount = fields.Monetary(
        string="Monto Factura ME (ISLR)",
        related="move_id.foreign_total_billed",
        currency_field="foreign_currency_id",
        store=True,
        readonly=True,
    )
    aliquot = fields.Float(
        string="Alicuota (%)", digits="Account", default=0.0
    )
    invoice_total = fields.Monetary(
        string="Total Factura",
        related="move_id.amount_total",
        currency_field="company_currency_id",
        store=True,
        readonly=True,
    )
    tax_id = fields.Many2one(
        "account.tax",
        string="Impuesto",
        domain="[('type_tax_use', '=', 'purchase'), ('tax_group_id.name', '=', 'ISLR')]",
        ondelete="restrict",
    )
    company_currency_id = fields.Many2one(
        related="move_id.company_id.currency_id",
        string="Moneda de la Compañía",
        store=True,
        readonly=True,
    )
    move_type = fields.Selection(
        related="move_id.move_type",
        string="Tipo de Movimiento",
        store=True,
        readonly=True,
    )
    related_percentage_tax_base = fields.Float(
        string="Porcentaje de Base Imponible Relacionado",
        digits="Account",
        default=0.0,
    )
    date = fields.Date(
        related="move_id.date", string="Fecha de Factura", store=True
    )

    @api.depends("move_id")
    def _compute_name(self):
        for rec in self:
            rec.name = f"{rec.move_id.name or _('Nuevo')} - {rec._description}"

    @api.depends('iva_amount', 'foreign_currency_rate', 'foreign_currency_id', 'company_currency_id')
    def _compute_foreign_iva_amount(self):
        for rec in self:
            if rec.foreign_currency_id and rec.foreign_currency_id != rec.company_currency_id and rec.foreign_currency_rate:
                rec.foreign_iva_amount = rec.iva_amount / rec.foreign_currency_rate
            else:
                rec.foreign_iva_amount = rec.iva_amount

    @api.constrains("aliquot")
    def _check_alicuot_percentage(self):
        for rec in self:
            if rec.aliquot < 0 or rec.aliquot > 100:
                raise ValidationError(_("The aliquot percentage must be between 0 and 100."))

    @api.onchange("aliquot", "base_amount", "foreign_base_amount")
    def _onchange_retention_amounts(self):
        for rec in self:
            rec.retention_amount = rec.base_amount * (rec.aliquot / 100)
            rec.foreign_retention_amount = rec.foreign_base_amount * (rec.aliquot / 100)

class AccountRetentionMunicipalLine(models.Model):
    _name = "account.retention.municipal.line"
    _description = "Account Retention Municipal Line"

    def _valid_field_parameter(self, field_name, parameter):
        return parameter == 'digits' or super()._valid_field_parameter(field_name, parameter)

    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
    ], string='Status', default='draft', readonly=True, copy=False)

    name = fields.Char(
        string="Descripción de Retención Municipal",
        compute="_compute_name",
        store=True,
    )

    move_id = fields.Many2one(
        "account.move",
        string="Factura",
        required=True,
        ondelete="cascade",
        index=True,
    )
    foreign_currency_id = fields.Many2one(
        related="move_id.foreign_currency_id",
        string="Moneda Extranjera",
        store=True,
        readonly=True,
    )
    foreign_invoice_total = fields.Monetary(
        string="Total Factura ME (Munic)",
        related="move_id.foreign_total_billed",
        currency_field="foreign_currency_id",
        store=True,
        readonly=True,
    )
    foreign_currency_rate = fields.Float(
        string="Tasa de Cambio (ME)",
        related="move_id.foreign_rate",
        digits=(12, 6),
        readonly=True,
        store=True,
    )
    foreign_iva_amount = fields.Monetary(
        string="Monto IVA (ME)",
        currency_field='foreign_currency_id',
        compute='_compute_foreign_iva_amount',
        store=True,
        readonly=True,
    )
    foreign_rate = fields.Float(
        related="move_id.foreign_rate", string="Tasa Extranjera", store=True, readonly=True
    )
    foreign_inverse_rate = fields.Float(
        related="move_id.foreign_inverse_rate",
        string="Tasa Inversa Extranjera",
        store=True,
        readonly=True,
    )
    base_amount = fields.Monetary(
        string="Base Imponible",
        currency_field="company_currency_id",
        digits="Account",
    )
    retention_amount = fields.Monetary(
        string="Monto Retenido",
        currency_field="company_currency_id",
        digits="Account",
    )
    foreign_base_amount = fields.Monetary(
        string="Base Imponible (ME)",
        currency_field="foreign_currency_id",
        digits="Account",
    )
    foreign_retention_amount = fields.Monetary(
        string="Monto Retenido (ME)",
        currency_field="foreign_currency_id",
        digits="Account",
    )
    invoice_amount = fields.Monetary(
        string="Monto de Factura",
        related="move_id.amount_total",
        currency_field="company_currency_id",
        store=True,
        readonly=True,
    )
    iva_amount = fields.Monetary(
        string="Monto IVA",
        related="move_id.amount_tax",
        currency_field="company_currency_id",
        store=True,
        readonly=True,
    )
    foreign_invoice_amount = fields.Monetary(
        string="Monto Factura ME (Munic)",
        related="move_id.foreign_total_billed",
        currency_field="foreign_currency_id",
        store=True,
        readonly=True,
    )
    aliquot = fields.Float(
        string="Alicuota (%)", digits="Account", default=0.0
    )
    invoice_total = fields.Monetary(
        string="Total Factura",
        related="move_id.amount_total",
        currency_field="company_currency_id",
        store=True,
        readonly=True,
    )
    tax_id = fields.Many2one(
        "account.tax",
        string="Impuesto",
        domain="[('type_tax_use', '=', 'purchase'), ('tax_group_id.name', '=', 'Municipal')]",
        ondelete="restrict",
    )
    company_currency_id = fields.Many2one(
        related="move_id.company_id.currency_id",
        string="Moneda de la Compañía",
        store=True,
        readonly=True,
    )
    move_type = fields.Selection(
        related="move_id.move_type",
        string="Tipo de Movimiento",
        store=True,
        readonly=True,
    )
    related_percentage_tax_base = fields.Float(
        string="Porcentaje de Base Imponible Relacionado",
        digits="Account",
        default=0.0,
    )
    date = fields.Date(
        related="move_id.date", string="Fecha de Factura", store=True
    )

    @api.depends("move_id")
    def _compute_name(self):
        for rec in self:
            rec.name = f"{rec.move_id.name or _('Nuevo')} - {rec._description}"

    @api.depends('iva_amount', 'foreign_currency_rate', 'foreign_currency_id', 'company_currency_id')
    def _compute_foreign_iva_amount(self):
        for rec in self:
            if rec.foreign_currency_id and rec.foreign_currency_id != rec.company_currency_id and rec.foreign_currency_rate:
                rec.foreign_iva_amount = rec.iva_amount / rec.foreign_currency_rate
            else:
                rec.foreign_iva_amount = rec.iva_amount

    @api.constrains("aliquot")
    def _check_alicuot_percentage(self):
        for rec in self:
            if rec.aliquot < 0 or rec.aliquot > 100:
                raise ValidationError(_("The aliquot percentage must be between 0 and 100."))

    @api.onchange("aliquot", "base_amount", "foreign_base_amount")
    def _onchange_retention_amounts(self):
        for rec in self:
            rec.retention_amount = rec.base_amount * (rec.aliquot / 100)
            rec.foreign_retention_amount = rec.foreign_base_amount * (rec.aliquot / 100)
