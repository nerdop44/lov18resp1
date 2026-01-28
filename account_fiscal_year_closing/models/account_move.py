# Copyright 2016 Tecnativa - Antonio Espinosa
# Copyright 2017 Tecnativa - Pedro M. Baeza
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import _, fields, models


class AccountMove(models.Model):
    _inherit = "account.move"

        if parameter == 'states':
            return True  # Permite el uso del parámetro 'states'
        return super()._valid_field_parameter(field_name, parameter)

    # Asegúrate de que el campo closing_type esté definido correctamente
    closing_type = fields.Selection(
        selection=[
            ("draft", "Draft"),
            ("calculated", "Processed"),
            ("posted", "Posted"),
            ("cancelled", "Cancelled"),
        ],
        readonly=True,
        default="draft",
          # Asegúrate de que states esté definido aquí
    )

    def _selection_closing_type(self):
        """Use selection values from move_type field in closing config
        (making a copy for preventing side effects), plus an extra value for
        non-closing moves."""
        res = list(
            self.env["account.fiscalyear.closing.config"].fields_get(
                allfields=["move_type"]
            )["move_type"]["selection"]
        )
        res.append(("none", _("None")))
        return res

    fyc_id = fields.Many2one(
        comodel_name="account.fiscalyear.closing",
        ondelete="cascade",
        string="Fiscal year closing",
        readonly=True,
    )
    closing_type = fields.Selection(
        selection=_selection_closing_type,
        default="none",
        
    )
