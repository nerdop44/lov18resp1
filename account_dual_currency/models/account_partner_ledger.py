# Libro mayor de empresas

import json

from odoo import models, _, fields
from odoo.exceptions import UserError
from odoo.tools.misc import format_date, get_lang
from odoo.tools import SQL

from datetime import timedelta
from collections import defaultdict

class PartnerLedgerCustomHandler(models.AbstractModel):
    _inherit = 'account.partner.ledger.report.handler'

    def _get_initial_balance_values(self, partner_ids, options):
        queries = []
        report = self.env.ref('account_reports.partner_ledger_report')
        companies = self.env['res.company'].browse(options.get('company_ids') or self.env.companies.ids)
        ct_query = self.env['res.currency']._get_simple_currency_table(companies)
        currency_dif = options['currency_dif']
        for column_group_key, column_group_options in report._split_options_per_column_group(options).items():
            new_options = self._get_options_initial_balance(column_group_options)
            query_res = report._get_report_query(new_options, 'normal', domain=[('partner_id', 'in', partner_ids)])
            tables, where_clause, where_params = query_res.get_sql()

            if currency_dif == self.env.company.currency_id.symbol:
                queries.append(SQL(
                    """
                    SELECT
                        account_move_line.partner_id                                                          AS groupby,
                        %s                                                                                    AS column_group_key,
                        SUM(ROUND(account_move_line.debit * currency_table.rate, currency_table.precision))   AS debit,
                        SUM(ROUND(account_move_line.credit * currency_table.rate, currency_table.precision))  AS credit,
                        SUM(ROUND(account_move_line.balance * currency_table.rate, currency_table.precision)) AS balance
                    FROM %s
                    LEFT JOIN %s ON currency_table.company_id = account_move_line.company_id
                    WHERE %s
                    GROUP BY account_move_line.partner_id
                    """,
                    column_group_key,
                    tables,
                    ct_query,
                    where_clause,
                ))
            else:
                queries.append(SQL(
                    """
                    SELECT
                        account_move_line.partner_id                                                          AS groupby,
                        %s                                                                                    AS column_group_key,
                        SUM(ROUND(account_move_line.debit_usd, currency_table.precision))   AS debit,
                        SUM(ROUND(account_move_line.credit_usd, currency_table.precision))  AS credit,
                        SUM(ROUND(account_move_line.balance_usd, currency_table.precision)) AS balance
                    FROM %s
                    LEFT JOIN %s ON currency_table.company_id = account_move_line.company_id
                    WHERE %s
                    GROUP BY account_move_line.partner_id
                    """,
                    column_group_key,
                    tables,
                    ct_query,
                    where_clause,
                ))

        self._cr.execute(SQL.join(' UNION ALL ', queries))

        init_balance_by_col_group = {
            partner_id: {column_group_key: {} for column_group_key in options['column_groups']}
            for partner_id in partner_ids
        }
        for result in self._cr.dictfetchall():
            init_balance_by_col_group[result['partner_id']][result['column_group_key']] = result

        return init_balance_by_col_group

    def _get_sums_without_partner(self, options):
        queries = []
        report = self.env.ref('account_reports.partner_ledger_report')
        currency_dif = options['currency_dif']
        for column_group_key, column_group_options in report._split_options_per_column_group(options).items():
            tables, where_clause, where_params = report._query_get(column_group_options, 'normal')
            if currency_dif == self.env.company.currency_id.symbol:
                queries.append(SQL(
                    """
                    SELECT
                        %s                                                                                                    AS column_group_key,
                        aml_with_partner.partner_id                                                                           AS groupby,
                        COALESCE(SUM(CASE WHEN aml_with_partner.balance > 0 THEN 0 ELSE partial.amount END), 0)               AS debit,
                        COALESCE(SUM(CASE WHEN aml_with_partner.balance < 0 THEN 0 ELSE partial.amount END), 0)               AS credit,
                        COALESCE(SUM(CASE WHEN aml_with_partner.balance > 0 THEN -partial.amount ELSE partial.amount END), 0) AS balance
                    FROM %s
                    JOIN account_partial_reconcile partial
                        ON account_move_line.id = partial.debit_move_id OR account_move_line.id = partial.credit_move_id
                    JOIN account_move_line aml_with_partner ON
                        (aml_with_partner.id = partial.debit_move_id OR aml_with_partner.id = partial.credit_move_id)
                        AND aml_with_partner.partner_id IS NOT NULL
                    WHERE partial.max_date <= %s AND %s
                        AND account_move_line.partner_id IS NULL
                    GROUP BY aml_with_partner.partner_id
                    """,
                    column_group_key,
                    tables,
                    column_group_options['date']['date_to'],
                    where_clause,
                ))
            else:
                queries.append(SQL(
                    """
                    SELECT
                        %s                                                                                                    AS column_group_key,
                        aml_with_partner.partner_id                                                                           AS groupby,
                        COALESCE(SUM(CASE WHEN aml_with_partner.balance_usd > 0 THEN 0 ELSE partial.amount_usd END), 0)               AS debit,
                        COALESCE(SUM(CASE WHEN aml_with_partner.balance_usd < 0 THEN 0 ELSE partial.amount_usd END), 0)               AS credit,
                        COALESCE(SUM(CASE WHEN aml_with_partner.balance_usd > 0 THEN -partial.amount_usd ELSE partial.amount_usd END), 0) AS balance
                    FROM %s
                    JOIN account_partial_reconcile partial
                        ON account_move_line.id = partial.debit_move_id OR account_move_line.id = partial.credit_move_id
                    JOIN account_move_line aml_with_partner ON
                        (aml_with_partner.id = partial.debit_move_id OR aml_with_partner.id = partial.credit_move_id)
                        AND aml_with_partner.partner_id IS NOT NULL
                    WHERE partial.max_date <= %s AND %s
                        AND account_move_line.partner_id IS NULL
                    GROUP BY aml_with_partner.partner_id
                    """,
                    column_group_key,
                    tables,
                    column_group_options['date']['date_to'],
                    where_clause,
                ))

        return SQL.join(' UNION ALL ', queries)

    def _get_query_sums(self, options):
        queries = []
        report = self.env.ref('account_reports.partner_ledger_report')
        companies = self.env['res.company'].browse(options.get('company_ids') or self.env.companies.ids)
        ct_query = self.env['res.currency']._get_simple_currency_table(companies)
        currency_dif = options['currency_dif']
        for column_group_key, column_group_options in report._split_options_per_column_group(options).items():
            tables, where_clause, where_params = report._query_get(column_group_options, 'normal')

            if currency_dif == self.env.company.currency_id.symbol:
                queries.append(SQL(
                    """
                    SELECT
                        account_move_line.partner_id                                                          AS groupby,
                        %s                                                                                    AS column_group_key,
                        SUM(ROUND(account_move_line.debit * currency_table.rate, currency_table.precision))   AS debit,
                        SUM(ROUND(account_move_line.credit * currency_table.rate, currency_table.precision))  AS credit,
                        SUM(ROUND(account_move_line.balance * currency_table.rate, currency_table.precision)) AS balance
                    FROM %s
                    LEFT JOIN %s ON currency_table.company_id = account_move_line.company_id
                    WHERE %s
                    GROUP BY account_move_line.partner_id
                    """,
                    column_group_key,
                    tables,
                    ct_query,
                    where_clause,
                ))
            else:
                queries.append(SQL(
                    """
                    SELECT
                        account_move_line.partner_id                                                          AS groupby,
                        %s                                                                                    AS column_group_key,
                        SUM(ROUND(account_move_line.debit_usd, currency_table.precision))   AS debit,
                        SUM(ROUND(account_move_line.credit_usd, currency_table.precision))  AS credit,
                        SUM(ROUND(account_move_line.balance_usd, currency_table.precision)) AS balance
                    FROM %s
                    LEFT JOIN %s ON currency_table.company_id = account_move_line.company_id
                    WHERE %s
                    GROUP BY account_move_line.partner_id
                    """,
                    column_group_key,
                    tables,
                    ct_query,
                    where_clause,
                ))

        return SQL.join(' UNION ALL ', queries)

    def _get_aml_values(self, options, partner_ids, offset=0, limit=None):
        rslt = {partner_id: [] for partner_id in partner_ids}
        partner_ids_wo_none = [x for x in partner_ids if x]
        directly_linked_aml_partner_params = []
        indirectly_linked_aml_partner_params = []
        directly_linked_aml_partner_clause = SQL("TRUE")
        indirectly_linked_aml_partner_clause = SQL("aml_with_partner.partner_id IS NOT NULL")
        
        if None in partner_ids and partner_ids_wo_none:
            directly_linked_aml_partner_clause = SQL("(account_move_line.partner_id IS NULL OR account_move_line.partner_id IN %s)", tuple(partner_ids_wo_none))
            indirectly_linked_aml_partner_clause = SQL("(aml_with_partner.partner_id IS NOT NULL AND aml_with_partner.partner_id IN %s)", tuple(partner_ids_wo_none))
        elif None in partner_ids:
            directly_linked_aml_partner_clause = SQL("account_move_line.partner_id IS NULL")
        elif partner_ids_wo_none:
            directly_linked_aml_partner_clause = SQL("account_move_line.partner_id IN %s", tuple(partner_ids_wo_none))
            indirectly_linked_aml_partner_clause = SQL("aml_with_partner.partner_id IN %s", tuple(partner_ids_wo_none))

        companies = self.env['res.company'].browse(options.get('company_ids') or self.env.companies.ids)
        ct_query = self.env['res.currency']._get_simple_currency_table(companies)
        queries = []
        lang = self.env.lang or get_lang(self.env).code
        journal_name = SQL("COALESCE(journal.name->>%s, journal.name->>'en_US')", lang) if \
            self.pool['account.journal'].name.translate else SQL("journal.name")
        account_name = SQL("COALESCE(account.name->>%s, account.name->>'en_US')", lang) if \
            self.pool['account.account'].name.translate else SQL("account.name")
        report = self.env.ref('account_reports.partner_ledger_report')
        currency_dif = options['currency_dif']

        for column_group_key, group_options in report._split_options_per_column_group(options).items():
            query_res = report._get_report_query(group_options, 'strict_range')
            tables, where_clause, where_params = query_res.get_sql()

            if currency_dif == self.env.company.currency_id.symbol:
                # Directly linked
                queries.append(SQL(
                    """
                    SELECT
                        account_move_line.id,
                        account_move_line.date,
                        account_move_line.date_maturity,
                        account_move_line.name,
                        account_move_line.ref,
                        account_move_line.company_id,
                        account_move_line.account_id,
                        account_move_line.payment_id,
                        account_move_line.partner_id,
                        account_move_line.currency_id,
                        account_move_line.amount_currency,
                        account_move_line.matching_number,
                        ROUND(account_move_line.debit * currency_table.rate, currency_table.precision)   AS debit,
                        ROUND(account_move_line.credit * currency_table.rate, currency_table.precision)  AS credit,
                        ROUND(account_move_line.balance * currency_table.rate, currency_table.precision) AS balance,
                        account_move.name                                                                AS move_name,
                        account_move.move_type                                                           AS move_type,
                        account.code                                                                     AS account_code,
                        %s                                                                               AS account_name,
                        journal.code                                                                     AS journal_code,
                        %s                                                                               AS journal_name,
                        %s                                                                               AS column_group_key,
                        'directly_linked_aml'                                                            AS key
                    FROM %s
                    JOIN account_move ON account_move.id = account_move_line.move_id
                    LEFT JOIN %s ON currency_table.company_id = account_move_line.company_id
                    LEFT JOIN account_account account           ON account.id = account_move_line.account_id
                    LEFT JOIN account_journal journal           ON journal.id = account_move_line.journal_id
                    WHERE %s AND %s
                    """,
                    account_name,
                    journal_name,
                    column_group_key,
                    tables,
                    ct_query,
                    where_clause,
                    directly_linked_aml_partner_clause,
                ))

                # Indirectly linked
                queries.append(SQL(
                    """
                    SELECT
                        account_move_line.id,
                        account_move_line.date,
                        account_move_line.date_maturity,
                        account_move_line.name,
                        account_move_line.ref,
                        account_move_line.company_id,
                        account_move_line.account_id,
                        account_move_line.payment_id,
                        aml_with_partner.partner_id,
                        account_move_line.currency_id,
                        account_move_line.amount_currency,
                        account_move_line.matching_number,
                        CASE WHEN aml_with_partner.balance > 0 THEN 0 ELSE partial.amount END               AS debit,
                        CASE WHEN aml_with_partner.balance < 0 THEN 0 ELSE partial.amount END               AS credit,
                        CASE WHEN aml_with_partner.balance > 0 THEN -partial.amount ELSE partial.amount END AS balance,
                        account_move.name                                                                   AS move_name,
                        account_move.move_type                                                              AS move_type,
                        account.code                                                                        AS account_code,
                        %s                                                                                  AS account_name,
                        journal.code                                                                        AS journal_code,
                        %s                                                                                  AS journal_name,
                        %s                                                                                  AS column_group_key,
                        'indirectly_linked_aml'                                                             AS key
                    FROM %s,
                        account_partial_reconcile partial,
                        account_move,
                        account_move_line aml_with_partner,
                        account_journal journal,
                        account_account account
                    WHERE
                        (account_move_line.id = partial.debit_move_id OR account_move_line.id = partial.credit_move_id)
                        AND account_move_line.partner_id IS NULL
                        AND account_move.id = account_move_line.move_id
                        AND (aml_with_partner.id = partial.debit_move_id OR aml_with_partner.id = partial.credit_move_id)
                        AND %s
                        AND journal.id = account_move_line.journal_id
                        AND account.id = account_move_line.account_id
                        AND %s
                        AND partial.max_date BETWEEN %s AND %s
                    """,
                    account_name,
                    journal_name,
                    column_group_key,
                    tables,
                    indirectly_linked_aml_partner_clause,
                    where_clause,
                    group_options['date']['date_from'],
                    group_options['date']['date_to'],
                ))
            else:
                # USD Version directly
                queries.append(SQL(
                    """
                    SELECT
                        account_move_line.id,
                        account_move_line.date,
                        account_move_line.date_maturity,
                        account_move_line.name,
                        account_move_line.ref,
                        account_move_line.company_id,
                        account_move_line.account_id,
                        account_move_line.payment_id,
                        account_move_line.partner_id,
                        account_move_line.currency_id,
                        0 as amount_currency,
                        account_move_line.matching_number,
                        ROUND(account_move_line.debit_usd, currency_table.precision)   AS debit,
                        ROUND(account_move_line.credit_usd, currency_table.precision)  AS credit,
                        ROUND(account_move_line.balance_usd, currency_table.precision) AS balance,
                        account_move.name                                                                AS move_name,
                        account_move.move_type                                                           AS move_type,
                        account.code                                                                     AS account_code,
                        %s                                                                               AS account_name,
                        journal.code                                                                     AS journal_code,
                        %s                                                                               AS journal_name,
                        %s                                                                               AS column_group_key,
                        'directly_linked_aml'                                                            AS key
                    FROM %s
                    JOIN account_move ON account_move.id = account_move_line.move_id
                    LEFT JOIN %s ON currency_table.company_id = account_move_line.company_id
                    LEFT JOIN account_account account           ON account.id = account_move_line.account_id
                    LEFT JOIN account_journal journal           ON journal.id = account_move_line.journal_id
                    WHERE %s AND %s
                    """,
                    account_name,
                    journal_name,
                    column_group_key,
                    tables,
                    ct_query,
                    where_clause,
                    directly_linked_aml_partner_clause,
                ))

                # USD Version indirectly
                queries.append(SQL(
                    """
                    SELECT
                        account_move_line.id,
                        account_move_line.date,
                        account_move_line.date_maturity,
                        account_move_line.name,
                        account_move_line.ref,
                        account_move_line.company_id,
                        account_move_line.account_id,
                        account_move_line.payment_id,
                        aml_with_partner.partner_id,
                        account_move_line.currency_id,
                        0 as amount_currency,
                        account_move_line.matching_number,
                        CASE WHEN aml_with_partner.balance_usd > 0 THEN 0 ELSE partial.amount_usd END               AS debit,
                        CASE WHEN aml_with_partner.balance_usd < 0 THEN 0 ELSE partial.amount_usd END               AS credit,
                        CASE WHEN aml_with_partner.balance_usd > 0 THEN -partial.amount_usd ELSE partial.amount_usd END AS balance,
                        account_move.name                                                                   AS move_name,
                        account_move.move_type                                                              AS move_type,
                        account.code                                                                        AS account_code,
                        %s                                                                                  AS account_name,
                        journal.code                                                                        AS journal_code,
                        %s                                                                                  AS journal_name,
                        %s                                                                                  AS column_group_key,
                        'indirectly_linked_aml'                                                             AS key
                    FROM %s,
                        account_partial_reconcile partial,
                        account_move,
                        account_move_line aml_with_partner,
                        account_journal journal,
                        account_account account
                    WHERE
                        (account_move_line.id = partial.debit_move_id OR account_move_line.id = partial.credit_move_id)
                        AND account_move_line.partner_id IS NULL
                        AND account_move.id = account_move_line.move_id
                        AND (aml_with_partner.id = partial.debit_move_id OR aml_with_partner.id = partial.credit_move_id)
                        AND %s
                        AND journal.id = account_move_line.journal_id
                        AND account.id = account_move_line.account_id
                        AND %s
                        AND partial.max_date BETWEEN %s AND %s
                    """,
                    account_name,
                    journal_name,
                    column_group_key,
                    tables,
                    indirectly_linked_aml_partner_clause,
                    where_clause,
                    group_options['date']['date_from'],
                    group_options['date']['date_to'],
                ))

        full_query = SQL.join(' UNION ALL ', [SQL("(%s)", q) for q in queries])
        
        if offset:
            full_query = SQL("%s OFFSET %s ", full_query, offset)
        if limit:
            full_query = SQL("%s LIMIT %s ", full_query, limit)

        self._cr.execute(full_query)
        for aml_result in self._cr.dictfetchall():
            if aml_result['key'] == 'indirectly_linked_aml':
                if aml_result['partner_id'] in rslt:
                    rslt[aml_result['partner_id']].append(aml_result)
                if None in rslt:
                    rslt[None].append({
                        **aml_result,
                        'debit': aml_result['credit'],
                        'credit': aml_result['debit'],
                        'balance': -aml_result['balance'],
                    })
            else:
                rslt[aml_result['partner_id']].append(aml_result)
        return rslt
