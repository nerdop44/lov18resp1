# -*- coding: utf-8 -*-
from odoo import fields, models, api, _
from odoo.exceptions import ValidationError

class AccountRetentionIvaLine(models.Model):
    _name = "account.retention.iva.line"
    _description = "Account Retention IVA Line"

    # Campo 'name' añadido
    name = fields.Char(
        string="Descripción de Retención IVA",
        compute="_compute_name",
        store=True, # Almacenar el campo para que sea consultable/filtrable
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
    aliquot = fields.Float(
        string="Alicuota (%)", digits="Account", default=0.0
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
    # CAMBIO: Añadido el campo 'l10n_ve_tax_type' como related field.
    # Esto permite que el dominio del campo 'tax_id' acceda a 'tax_group_id.l10n_ve_tax_type'
    # sin que Odoo piense que es un campo desconocido en este modelo.
 #   l10n_ve_tax_type = fields.Selection(related='tax_id.tax_group_id.l10n_ve_tax_type', store=True, readonly=True)


    @api.constrains("alicuot_percentage")
    def _check_alicuot_percentage(self):
        for rec in self:
            if rec.alicuot_percentage < 0 or rec.alicuot_percentage > 100:
                raise ValidationError(
                    _("The aliquot percentage must be between 0 and 100.")
                )

    @api.onchange("alicuot_percentage", "base_amount", "foreign_base_amount")
    def _onchange_retention_amounts(self):
        for rec in self:
            rec.retention_amount = rec.base_amount * (rec.alicuot_percentage / 100)
            rec.foreign_retention_amount = rec.foreign_base_amount * (
                rec.alicuot_percentage / 100
            )

class AccountRetentionIslrLine(models.Model):
    _name = "account.retention.islr.line"
    _description = "Account Retention ISLR Line"

    # Campo 'name' añadido
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
    foreign_currency_id = fields.Many2one(
        related="move_id.foreign_currency_id",
        string="Moneda Extranjera",
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
    aliquot = fields.Float(
        string="Alicuota (%)", digits="Account", default=0.0
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
    date = fields.Date(
        related="move_id.date", string="Fecha de Factura", store=True
    )
    # CAMBIO: Añadido el campo 'l10n_ve_tax_type' como related field.
#    l10n_ve_tax_type = fields.Selection(related='tax_id.tax_group_id.l10n_ve_tax_type', store=True, readonly=True)


    @api.constrains("alicuot_percentage")
    def _check_alicuot_percentage(self):
        for rec in self:
            if rec.alicuot_percentage < 0 or rec.alicuot_percentage > 100:
                raise ValidationError(
                    _("The aliquot percentage must be between 0 and 100.")
                )

    @api.onchange("alicuot_percentage", "base_amount", "foreign_base_amount")
    def _onchange_retention_amounts(self):
        for rec in self:
            rec.retention_amount = rec.base_amount * (rec.alicuot_percentage / 100)
            rec.foreign_retention_amount = rec.foreign_base_amount * (
                rec.alicuot_percentage / 100
            )

class AccountRetentionMunicipalLine(models.Model):
    _name = "account.retention.municipal.line"
    _description = "Account Retention Municipal Line"

    # Campo 'name' añadido
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
    aliquot = fields.Float(
        string="Alicuota (%)", digits="Account", default=0.0
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
    date = fields.Date(
        related="move_id.date", string="Fecha de Factura", store=True
    )
    # CAMBIO: Añadido el campo 'l10n_ve_tax_type' como related field.
#    l10n_ve_tax_type = fields.Selection(related='tax_id.tax_group_id.l10n_ve_tax_type', store=True, readonly=True)


    @api.constrains("alicuot_percentage")
    def _check_alicuot_percentage(self):
        for rec in self:
            if rec.alicuot_percentage < 0 or rec.alicuot_percentage > 100:
                raise ValidationError(
                    _("The aliquot percentage must be between 0 and 100.")
                )

    @api.onchange("alicuot_percentage", "base_amount", "foreign_base_amount")
    def _onchange_retention_amounts(self):
        for rec in self:
            rec.retention_amount = rec.base_amount * (rec.alicuot_percentage / 100)
            rec.foreign_retention_amount = rec.foreign_base_amount * (
                rec.alicuot_percentage / 100
            )
