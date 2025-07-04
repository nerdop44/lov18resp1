# Copyright 2016 Tecnativa - Antonio Espinosa
# Copyright 2017 Tecnativa - Pedro M. Baeza
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import logging

from dateutil.relativedelta import relativedelta

from odoo import _, api, exceptions, fields, models
from odoo.exceptions import ValidationError
from odoo.tools import float_is_zero

_logger = logging.getLogger(__name__)


class AccountFiscalyearClosing(models.Model):
    _inherit = "account.fiscalyear.closing.abstract"
    _name = "account.fiscalyear.closing"
    _description = "Fiscal year closing"

    # Método para permitir el uso del parámetro 'states'
    def _valid_field_parameter(self, field_name, parameter):
        if parameter == 'states':
            return True  # Permite el uso del parámetro 'states'
        return super(AccountFiscalyearClosing, self)._valid_field_parameter(field_name, parameter)

    def _default_year(self):
        company = self._default_company_id()
        lock_date = company.fiscalyear_lock_date or fields.Date.today()
        fiscalyear = lock_date.year
        if (
            lock_date.month < int(company.fiscalyear_last_month)
            and lock_date.day < company.fiscalyear_last_day
        ):
            fiscalyear = fiscalyear - 1
        return fiscalyear

    def _default_company_id(self):
        return self.env.company

    name = fields.Char(
        readonly=True,
        states={"draft": [("readonly", False)]},
    )
    check_draft_moves = fields.Boolean(
        readonly=True,
        states={"draft": [("readonly", False)]},
    )
    year = fields.Integer(
        help="Introduce here the year to close. If the fiscal year is between "
        "several natural years, you have to put here the last one.",
        default=lambda self: self._default_year(),
        readonly=True,
        states={"draft": [("readonly", False)]},
    )
    company_id = fields.Many2one(
        default=lambda self: self._default_company_id(),
        readonly=True,
        states={"draft": [("readonly", False)]},
    )
    # chart_template_id = fields.Many2one( Ya no existe
    #     comodel_name="account.chart.template",
    #     string="Chart template",
    #     related="company_id.chart_template_id",
    #     readonly=True,
    # )
    state = fields.Selection(
        selection=[
            ("draft", "Draft"),
            ("calculated", "Processed"),
            ("posted", "Posted"),
            ("cancelled", "Cancelled"),
        ],
        readonly=True,
        default="draft",
    )
    calculation_date = fields.Datetime(
        string="Calculation date",
        readonly=True,
    )
    date_start = fields.Date(
        string="From date",
        required=True,
        readonly=True,
        states={"draft": [("readonly", False)]},
    )
    date_end = fields.Date(
        string="To date",
        required=True,
        readonly=True,
        states={"draft": [("readonly", False)]},
    )
    date_opening = fields.Date(
        string="Opening date",
        required=True,
        readonly=True,
        states={"draft": [("readonly", False)]},
    )
    closing_template_id = fields.Many2one(
        comodel_name="account.fiscalyear.closing.template",
        string="Closing template",
        # domain="[('chart_template_ids', '=', chart_template_id)]",
        readonly=True,
        states={"draft": [("readonly", False)]},
    )
    move_config_ids = fields.One2many(
        comodel_name="account.fiscalyear.closing.config",
        inverse_name="fyc_id",
        string="Moves configuration",
        readonly=True,
        states={"draft": [("readonly", False)]},
    )
    move_ids = fields.One2many(
        comodel_name="account.move",
        inverse_name="fyc_id",
        string="Moves",
        readonly=True,
    )

    # _sql_constraints = [
    #     (
    #         "year_company_uniq",
    #         "unique(year, company_id)",
    #         _(
    #             "There should be only one fiscal year closing for that year and "
    #             "company!"
    #         ),
    #     ),
    # ]

    def _prepare_mapping(self, tmpl_mapping):
        self.ensure_one()
        dest_account = False
        # Find the destination account
        name = tmpl_mapping.name
        if tmpl_mapping.dest_account:
            dest_account = self.env["account.account"].search(
                [
                    ("company_id", "=", self.company_id.id),
                    ("code", "=ilike", tmpl_mapping.dest_account),
                ],
                limit=1,
            )
            # Use an error name if no destination account found
            if not dest_account:
                name = _("No destination account '%s' found.") % (
                    tmpl_mapping.dest_account,
                )
        return {
            "name": name,
            "src_accounts": tmpl_mapping.src_accounts,
            "dest_account_id": dest_account,
        }

    @api.model
    def _prepare_type(self, tmpl_type):
        return {
            "account_type": tmpl_type.account_type,
            "closing_type": tmpl_type.closing_type,
        }

    def _get_default_journal(self, company):
        """To be inherited if we want to change the default journal."""
        journal_obj = self.env["account.journal"]
        domain = [("company_id", "=", company.id)]
        journal = journal_obj.search(
            domain + [("code", "=", "MISC")],
            limit=1,
        )
        if not journal:
            journal = journal_obj.search(
                domain + [("type", "=", "general")],
                limit=1,
            )
        return journal

    def _prepare_config(self, tmpl_config):
        self.ensure_one()
        mappings = self.env["account.fiscalyear.closing.mapping"]
        for m in tmpl_config.mapping_ids:
            mappings += mappings.new(self._prepare_mapping(m))
        types = self.env["account.fiscalyear.closing.type"]
        for t in tmpl_config.closing_type_ids:
            types += types.new(self._prepare_type(t))
        if tmpl_config.move_date == "last_ending":
            date = self.date_end
        else:
            date = self.date_opening
        return {
            "enabled": True,
            "name": tmpl_config.name,
            "sequence": tmpl_config.sequence,
            "code": tmpl_config.code,
            # "inverse": tmpl_config.inverse,
            "move_type": tmpl_config.move_type,
            "date": date,
            "journal_id": (
                tmpl_config.journal_id or self._get_default_journal(self.company_id).id
            ),
            "mapping_ids": mappings,
            "closing_type_ids": types,
            "closing_type_default": tmpl_config.closing_type_default,
        }

    @api.onchange("closing_template_id")
    def onchange_template_id(self):
        self.move_config_ids = False
        if not self.closing_template_id:
            return
        config_obj = self.env["account.fiscalyear.closing.config"]
        tmpl = self.closing_template_id.with_company(self.company_id)
        self.check_draft_moves = tmpl.check_draft_moves
        for tmpl_config in tmpl.move_config_ids:
            self.move_config_ids += config_obj.new(self._prepare_config(tmpl_config))

    @api.onchange("year")
    def _onchange_year(self):
        self.date_end = "{}-{}-{}".format(
            self.year,
            str(self.company_id.fiscalyear_last_month).zfill(2) or "12",
            str(self.company_id.fiscalyear_last_day).zfill(2) or "31",
        )
        date_end = fields.Date.from_string(self.date_end)
        self.date_start = fields.Date.to_string(
            date_end - relativedelta(years=1) + relativedelta(days=1)
        )
        self.date_opening = fields.Date.to_string(date_end + relativedelta(days=1))
        if self.date_start != self.date_end:
            self.name = "{}-{}".format(self.date_start, self.date_end)
        else:
            self.name = str(self.date_end)

    def draft_moves_check(self):
        for closing in self:
            draft_moves = self.env["account.move"].search(
                [
                    ("company_id", "=", closing.company_id.id),
                    ("state", "=", "draft"),
                    ("date", ">=", closing.date_start),
                    ("date", "<=", closing.date_end),
                ]
            )
            if draft_moves:
                msg = _("One or more draft moves found: \n")
                for move in draft_moves:
                    msg += "ID: {}, Date: {}, Number: {}, Ref: {}\n".format(
                        move.id,
                        move.date,
                        move.name,
                        move.ref,
                    )
                raise ValidationError(msg)
        return True

    def _show_unbalanced_move_wizard(self, data):
        """When a move is not balanced, a wizard is presented for checking the
        possible problem. This method fills the records and return the
        corresponding action for showing that wizard.

        :param data: Dictionary with the values of the unbalanced move.
        :return: Dictionary with the action for showing the wizard.
        """
        del data["closing_type"]
        del data["fyc_id"]
        wizard = self.env["account.fiscalyear.closing.unbalanced.move"].create(data)
        return {
            "type": "ir.actions.act_window",
            "name": _("Unbalanced journal entry found"),
            "view_type": "form",
            "view_mode": "form",
            "res_model": "account.fiscalyear.closing.unbalanced.move",
            "res_id": wizard.id,
            "target": "new",
        }

    def calculate(self):
        for closing in self:
            # Perform checks, raise exception if check fails
            if closing.check_draft_moves:
                closing.draft_moves_check()
            for config in closing.move_config_ids.filtered("enabled"):
                move, data = config.moves_create()
                if not move and data:
                    # The move can't be created
                    return self._show_unbalanced_move_wizard(data)
        return True

    def _moves_remove(self):
        for closing in self:
            closing.mapped("move_ids.line_ids").filtered(
                "reconciled"
            ).remove_move_reconcile()
            closing.move_ids.button_cancel()
            closing.move_ids.unlink()
        return True

    def button_calculate(self):
        res = self.calculate()
        if res is True:
            # Change state only on successful creation
            self.write(
                {
                    "state": "calculated",
                    "calculation_date": fields.Datetime.now(),
                }
            )
        else:
            # Remove intermediate moves already created
            self._moves_remove()
        return res

    def button_recalculate(self):
        self._moves_remove()
        return self.button_calculate()

    def button_post(self):
        # Post moves
        for closing in self:
            for move_config in closing.move_config_ids.sorted("sequence"):
                move_config.move_id.action_post()
        self.write({"state": "posted"})
        return True

    def button_open_moves(self):
        # Return an action for showing moves
        return {
            "name": _("Fiscal closing moves"),
            "type": "ir.actions.act_window",
            "view_type": "form",
            "view_mode": "list,form",
            "res_model": "account.move",
            "domain": [("fyc_id", "in", self.ids)],
        }

    def button_open_move_lines(self):
        return {
            "name": _("Fiscal closing move lines"),
            "type": "ir.actions.act_window",
            "view_type": "form",
            "view_mode": "list,form",
            "res_model": "account.move.line",
            "domain": [("move_id.fyc_id", "in", self.ids)],
        }

    def button_cancel(self):
        self._moves_remove()
        self.write({"state": "cancelled"})
        return True

    def button_recover(self):
        self.write(
            {
                "state": "draft",
                "calculation_date": False,
            }
        )
        return True

    def unlink(self):
        if any(x.state not in ("draft", "cancelled") for x in self):
            raise exceptions.UserError(
                _(
                    "You can't remove any closing that is not in draft or "
                    "cancelled state."
                )
            )
        return super(AccountFiscalyearClosing, self).unlink()


class AccountFiscalyearClosingConfig(models.Model):
    _inherit = "account.fiscalyear.closing.config.abstract"
    _name = "account.fiscalyear.closing.config"
    _order = "sequence asc, id asc"
    _description = "Fiscal year closing configuration"

    # Método para permitir el uso del parámetro 'states'
    def _valid_field_parameter(self, field_name, parameter):
        if parameter == 'states':
            return True  # Permite el uso del parámetro 'states'
        return super(AccountFiscalyearClosingConfig, self)._valid_field_parameter(field_name, parameter)

    fyc_id = fields.Many2one(
        comodel_name="account.fiscalyear.closing",
        index=True,
        readonly=True,
        string="Fiscal Year Closing",
        required=True,
        ondelete="cascade",
    )
    mapping_ids = fields.One2many(
        comodel_name="account.fiscalyear.closing.mapping",
        inverse_name="fyc_config_id",
        string="Account mappings",
    )
    closing_type_ids = fields.One2many(
        comodel_name="account.fiscalyear.closing.type",
        inverse_name="fyc_config_id",
        string="Closing types",
    )
    date = fields.Date(string="Move date")
    enabled = fields.Boolean(default=True)
    journal_id = fields.Many2one(required=True)
    move_id = fields.Many2one(comodel_name="account.move", string="Move")

    _sql_constraints = [
        (
            "code_uniq",
            "unique(code, fyc_id)",
            _("Code must be unique per fiscal year closing!"),
        ),
    ]

    def config_inverse_get(self):
        configs = self.env["account.fiscalyear.closing.config"]
        for config in self:
            code = config.inverse and config.inverse.strip()
            if code:
                configs |= self.search(
                    [
                        ("fyc_id", "=", config.fyc_id.id),
                        ("code", "=", code),
                    ]
                )
        return configs

    def closing_type_get(self, account):
        self.ensure_one()
        closing_type = self.closing_type_default
        closing_types = self.closing_type_ids.filtered(
            lambda r: r.account_type == account.account_type
        )
        if closing_types:
            closing_type = closing_types[0].closing_type
        return closing_type

    def move_prepare(self, move_lines):
        self.ensure_one()
        description = self.name
        journal_id = self.journal_id.id
        return {
            "ref": description,
            "date": self.date,
            "fyc_id": self.fyc_id.id,
            "closing_type": self.move_type,
            "journal_id": journal_id,
            "line_ids": [(0, 0, m) for m in move_lines],
        }

    def _mapping_move_lines_get(self):
        move_lines = []
        dest_totals = {}
        # Add balance/unreconciled move lines
        for account_map in self.mapping_ids:
            dest = account_map.dest_account_id
            dest_totals.setdefault(dest, 0)
            src_accounts = self.env["account.account"].search(
                [
                    ("company_id", "=", self.fyc_id.company_id.id),
                    ("code", "=ilike", account_map.src_accounts),
                ],
                order="code ASC",
            )
            for account in src_accounts:
                closing_type = self.closing_type_get(account)
                balance = False
                if closing_type == "balance":
                    # Get all lines
                    lines = account_map.account_lines_get(account)
                    balance, move_line = account_map.move_line_prepare(account, lines)
                    if move_line:
                        move_lines.append(move_line)
                elif closing_type == "unreconciled":
                    # Get credit and debit grouping by partner
                    partners = account_map.account_partners_get(account)
                    for partner in partners:
                        balance, move_line = account_map.move_line_partner_prepare(
                            account, partner
                        )
                        if move_line:
                            move_lines.append(move_line)
                else:
                    # Account type has unsupported closing method
                    continue
                if dest and balance:
                    dest_totals[dest] -= balance
        # Add destination move lines, if any
        for account_map in self.mapping_ids.filtered("dest_account_id"):
            dest = account_map.dest_account_id
            balance = dest_totals.get(dest, 0)
            if not balance:
                continue
            dest_totals[dest] = 0
            move_line = account_map.dest_move_line_prepare(dest, balance)
            if move_line:
                move_lines.append(move_line)
        return move_lines

    def inverse_move_prepare(self):
        self.ensure_one()
        move_ids = False
        date = self.fyc_id.date_end
        if self.move_type == "opening":
            date = self.fyc_id.date_opening
        config = self.config_inverse_get()
        if config.move_id:
            move_ids = config.move_id._reverse_moves(
                [
                    dict(
                        date=date,
                        journal_id=self.journal_id.id,
                    )
                ]
            )
        return move_ids.ids

    def moves_create(self):
        self.ensure_one()
        moves = self.env["account.move"]
        # Prepare one move per configuration
        data = False
        if self.mapping_ids:
            move_lines = self._mapping_move_lines_get()
            data = self.move_prepare(move_lines)
        elif self.inverse:
            move_ids = self.inverse_move_prepare()
            move = moves.browse(move_ids[0])
            move.write({"ref": self.name, "closing_type": self.move_type})
            self.move_id = move.id
            return move, data
        # Create move
        if not data:
            return False, data
        total_debit = sum([x[2]["debit"] for x in data["line_ids"]])
        total_credit = sum([x[2]["credit"] for x in data["line_ids"]])
        if abs(round(total_credit - total_debit, 2)) >= 0.01:
            # the move is not balanced
            return False, data
        move = moves.with_context(journal_id=self.journal_id.id).create(data)
        self.move_id = move.id
        return move, data


class AccountFiscalyearClosingMapping(models.Model):
    _inherit = "account.fiscalyear.closing.mapping.abstract"
    _name = "account.fiscalyear.closing.mapping"
    _description = "Fiscal year closing mapping"

    # Método para permitir el uso del parámetro 'states'
    def _valid_field_parameter(self, field_name, parameter):
        if parameter == 'states':
            return True  # Permite el uso del parámetro 'states'
        return super(AccountFiscalyearClosingMapping, self)._valid_field_parameter(field_name, parameter)

    fyc_config_id = fields.Many2one(
        comodel_name="account.fiscalyear.closing.config",
        index=True,
        string="Fiscal year closing config",
        readonly=True,
        required=True,
        ondelete="cascade",
    )
    src_accounts = fields.Char(
        string="Source accounts",
        required=True,
    )
    dest_account_id = fields.Many2one(
        comodel_name="account.account",
        string="Destination account",
    )

    @api.model_create_multi
    def create(self, vals_tree):
        for vals in vals_tree:
            if vals.get("dest_account_id", False):
                vals["dest_account_id"] = vals["dest_account_id"]
        res = super(AccountFiscalyearClosingMapping, self).create(vals_tree)
        return res

    def write(self, vals):
        if vals.get("dest_account_id", False):
            vals["dest_account_id"] = vals["dest_account_id"][0]
        res = super(AccountFiscalyearClosingMapping, self).write(vals)
        return res

    def dest_move_line_prepare(self, dest, balance, partner_id=False):
        self.ensure_one()
        move_line = {}
        precision = self.env["decimal.precision"].precision_get("Account")
        date = self.fyc_config_id.fyc_id.date_end
        if self.fyc_config_id.move_type == "opening":
            date = self.fyc_config_id.fyc_id.date_opening
        if not float_is_zero(balance, precision_digits=precision):
            move_line = {
                "account_id": dest.id,
                "debit": balance < 0 and -balance,
                "credit": balance > 0 and balance,
                "name": _("Result"),
                "date": date,
                "partner_id": partner_id,
            }
        return move_line

    def move_line_prepare(self, account, account_lines, partner_id=False):
        self.ensure_one()
        move_line = {}
        balance = 0
        precision = self.env["decimal.precision"].precision_get("Account")
        description = self.name or account.name
        date = self.fyc_config_id.fyc_id.date_end
        if self.fyc_config_id.move_type == "opening":
            date = self.fyc_config_id.fyc_id.date_opening
        if account_lines:
            balance = sum(account_lines.mapped("debit")) - sum(
                account_lines.mapped("credit")
            )
            if not float_is_zero(balance, precision_digits=precision):
                move_line = {
                    "account_id": account.id,
                    "debit": balance < 0 and -balance,
                    "credit": balance > 0 and balance,
                    "name": description,
                    "date": date,
                    "partner_id": partner_id,
                }
            else:
                balance = 0
        return balance, move_line

    def account_lines_get(self, account):
        self.ensure_one()
        start = self.fyc_config_id.fyc_id.date_start
        end = self.fyc_config_id.fyc_id.date_end
        company_id = self.fyc_config_id.fyc_id.company_id.id
        return self.env["account.move.line"].search(
            [
                ("company_id", "=", company_id),
                ("account_id", "=", account.id),
                ("move_id.state", "!=", "cancel"),
                ("date", ">=", start),
                ("date", "<=", end),
            ]
        )

    def move_line_partner_prepare(self, account, partner):
        self.ensure_one()
        move_line = {}
        balance = partner.get("debit", 0.0) - partner.get("credit", 0.0)
        precision = self.env["decimal.precision"].precision_get("Account")
        description = self.name or account.name
        partner_id = partner.get("partner_id")
        if partner_id:
            partner_id = partner_id[0]
        date = self.fyc_config_id.fyc_id.date_end
        if self.fyc_config_id.move_type == "opening":
            date = self.fyc_config_id.fyc_id.date_opening
        if not float_is_zero(balance, precision_digits=precision):
            move_line = {
                "account_id": account.id,
                "debit": balance < 0 and -balance,
                "credit": balance > 0 and balance,
                "name": description,
                "date": date,
                "partner_id": partner_id,
            }
        else:
            balance = 0
        return balance, move_line

    def account_partners_get(self, account):
        self.ensure_one()
        start = self.fyc_config_id.fyc_id.date_start
        end = self.fyc_config_id.fyc_id.date_end
        company_id = self.fyc_config_id.fyc_id.company_id.id
        return self.env["account.move.line"].read_group(
            [
                ("company_id", "=", company_id),
                ("account_id", "=", account.id),
                ("date", ">=", start),
                ("date", "<=", end),
            ],
            ["partner_id", "credit", "debit"],
            ["partner_id"],
        )


class AccountFiscalyearClosingType(models.Model):
    _inherit = "account.fiscalyear.closing.type.abstract"
    _name = "account.fiscalyear.closing.type"
    _description = "Fiscal year closing type"

    fyc_config_id = fields.Many2one(
        comodel_name="account.fiscalyear.closing.config",
        index=True,
        string="Fiscal year closing config",
        readonly=True,
        required=True,
        ondelete="cascade",
    )
