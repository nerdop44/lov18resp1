# Libro mayor de empresas

import json

from odoo import models, _, fields
from odoo.tools import SQL
from odoo.exceptions import UserError
from odoo.tools.misc import format_date, get_lang

from datetime import timedelta
from collections import defaultdict

class PartnerLedgerCustomHandler(models.AbstractModel):
    _inherit = 'account.partner.ledger.report.handler'

    def _get_initial_balance_values(self, partner_ids, options):
        queries = []
        report = self.env.ref('account_reports.partner_ledger_report')
        ct_sql_base = self.env['res.currency']._get_simple_currency_table(options)
        ct_sql = SQL("(%(subquery)s) AS currency_table", subquery=ct_sql_base)
        currency_dif = options['currency_dif']
        for column_group_key, column_group_options in report._split_options_per_column_group(options).items():
            # Get sums for the initial balance.
            # period: [('date' <= options['date_from'] - 1)]
            new_options = self._get_options_initial_balance(column_group_options)
            query_obj = report._get_report_query(new_options, 'normal', domain=[('partner_id', 'in', partner_ids)])
            
            if currency_dif == self.env.company.currency_id.symbol:
                queries.append(SQL("""
                    SELECT
                        account_move_line.partner_id,
                        %(column_group_key)s                                                                  AS column_group_key,
                        SUM(ROUND(account_move_line.debit * currency_table.rate, currency_table.precision))   AS debit,
                        SUM(ROUND(account_move_line.credit * currency_table.rate, currency_table.precision))  AS credit,
                        SUM(ROUND(account_move_line.balance * currency_table.rate, currency_table.precision)) AS balance
                    FROM %(tables)s
                    LEFT JOIN %(ct_query)s ON currency_table.company_id = account_move_line.company_id
                    WHERE %(where_clause)s
                    GROUP BY account_move_line.partner_id
                """,
                    column_group_key=column_group_key,
                    tables=query_obj.from_clause,
                    ct_query=ct_sql,
                    where_clause=query_obj.where_clause
                ))
            else:
                queries.append(SQL("""
                    SELECT
                        account_move_line.partner_id,
                        %(column_group_key)s                                                                  AS column_group_key,
                        SUM(ROUND(account_move_line.debit_usd, currency_table.precision))   AS debit,
                        SUM(ROUND(account_move_line.credit_usd, currency_table.precision))  AS credit,
                        SUM(ROUND(account_move_line.balance_usd, currency_table.precision)) AS balance
                    FROM %(tables)s
                    LEFT JOIN %(ct_query)s ON currency_table.company_id = account_move_line.company_id
                    WHERE %(where_clause)s
                    GROUP BY account_move_line.partner_id
                """,
                    column_group_key=column_group_key,
                    tables=query_obj.from_clause,
                    ct_query=ct_sql,
                    where_clause=query_obj.where_clause
                ))

        self._cr.execute(SQL(" UNION ALL ").join(queries)) if queries else None

        init_balance_by_col_group = {
            partner_id: {column_group_key: {} for column_group_key in options['column_groups']}
            for partner_id in partner_ids
        }
        for result in self._cr.dictfetchall():
            init_balance_by_col_group[result['partner_id']][result['column_group_key']] = result

        return init_balance_by_col_group

    def _get_sums_without_partner(self, options):
        """ Get the sum of lines without partner reconciled with a line with a partner, grouped by partner. Those lines
        should be considered as belonging to the partner for the reconciled amount as it may clear some of the partner
        invoice/bill and they have to be accounted in the partner balance."""
        queries = []
        report = self.env.ref('account_reports.partner_ledger_report')
        currency_dif = options['currency_dif']
        for column_group_key, column_group_options in report._split_options_per_column_group(options).items():
            query_obj = report._get_report_query(column_group_options, 'normal')
            
            if currency_dif == self.env.company.currency_id.symbol:
                queries.append(SQL("""
                    SELECT
                        %(column_group_key)s                                                                                  AS column_group_key,
                        aml_with_partner.partner_id                                                                           AS groupby,
                        COALESCE(SUM(CASE WHEN aml_with_partner.balance > 0 THEN 0 ELSE partial.amount END), 0)               AS debit,
                        COALESCE(SUM(CASE WHEN aml_with_partner.balance < 0 THEN 0 ELSE partial.amount END), 0)               AS credit,
                        COALESCE(SUM(CASE WHEN aml_with_partner.balance > 0 THEN -partial.amount ELSE partial.amount END), 0) AS balance
                    FROM %(tables)s
                    JOIN account_partial_reconcile partial
                        ON account_move_line.id = partial.debit_move_id OR account_move_line.id = partial.credit_move_id
                    JOIN account_move_line aml_with_partner ON
                        (aml_with_partner.id = partial.debit_move_id OR aml_with_partner.id = partial.credit_move_id)
                        AND aml_with_partner.partner_id IS NOT NULL
                    WHERE partial.max_date <= %(date_to)s AND %(where_clause)s
                        AND account_move_line.partner_id IS NULL
                    GROUP BY aml_with_partner.partner_id
                """,
                    column_group_key=column_group_key,
                    tables=query_obj.from_clause,
                    where_clause=query_obj.where_clause,
                    date_to=column_group_options['date']['date_to']
                ))
            else:
                queries.append(SQL("""
                    SELECT
                        %(column_group_key)s                                                                                  AS column_group_key,
                        aml_with_partner.partner_id                                                                           AS groupby,
                        COALESCE(SUM(CASE WHEN aml_with_partner.balance_usd > 0 THEN 0 ELSE partial.amount_usd END), 0)               AS debit,
                        COALESCE(SUM(CASE WHEN aml_with_partner.balance_usd < 0 THEN 0 ELSE partial.amount_usd END), 0)               AS credit,
                        COALESCE(SUM(CASE WHEN aml_with_partner.balance_usd > 0 THEN -partial.amount_usd ELSE partial.amount_usd END), 0) AS balance
                    FROM %(tables)s
                    JOIN account_partial_reconcile partial
                        ON account_move_line.id = partial.debit_move_id OR account_move_line.id = partial.credit_move_id
                    JOIN account_move_line aml_with_partner ON
                        (aml_with_partner.id = partial.debit_move_id OR aml_with_partner.id = partial.credit_move_id)
                        AND aml_with_partner.partner_id IS NOT NULL
                    WHERE partial.max_date <= %(date_to)s AND %(where_clause)s
                        AND account_move_line.partner_id IS NULL
                    GROUP BY aml_with_partner.partner_id
                """,
                    column_group_key=column_group_key,
                    tables=query_obj.from_clause,
                    where_clause=query_obj.where_clause,
                    date_to=column_group_options['date']['date_to']
                ))

        return SQL(" UNION ALL ").join(queries), []

    def _get_query_sums(self, options):
        """ Construct a query retrieving all the aggregated sums to build the report. It includes:
        - sums for all partners.
        - sums for the initial balances.
        :param options:             The report options.
        :return:                    (query, params)
        """
        queries = []
        report = self.env.ref('account_reports.partner_ledger_report')

        ct_sql_base = self.env['res.currency']._get_simple_currency_table(options)
        ct_sql = SQL("(%(subquery)s) AS currency_table", subquery=ct_sql_base)
        currency_dif = options['currency_dif']
        rate_mode = options.get('rate_mode', 'historical')
        for column_group_key, column_group_options in report._split_options_per_column_group(options).items():
            query_obj = report._get_report_query(column_group_options, 'normal')
            
            if currency_dif == self.env.company.currency_id.symbol:
                queries.append(SQL("""
                    SELECT
                        account_move_line.partner_id                                                          AS groupby,
                        %(column_group_key)s                                                                  AS column_group_key,
                        SUM(ROUND(account_move_line.debit * currency_table.rate, currency_table.precision))   AS debit,
                        SUM(ROUND(account_move_line.credit * currency_table.rate, currency_table.precision))  AS credit,
                        SUM(ROUND(account_move_line.balance * currency_table.rate, currency_table.precision)) AS balance
                    FROM %(tables)s
                    LEFT JOIN %(ct_query)s ON currency_table.company_id = account_move_line.company_id
                    WHERE %(where_clause)s
                    GROUP BY account_move_line.partner_id
                """,
                    column_group_key=column_group_key,
                    tables=query_obj.from_clause,
                    ct_query=ct_sql,
                    where_clause=query_obj.where_clause
                ))
            else:
                if rate_mode == 'current':
                    queries.append(SQL("""
                        SELECT
                            account_move_line.partner_id                                                          AS groupby,
                            %(column_group_key)s                                                                  AS column_group_key,
                            SUM(ROUND(account_move_line.debit * currency_table.rate, currency_table.precision))   AS debit,
                            SUM(ROUND(account_move_line.credit * currency_table.rate, currency_table.precision))  AS credit,
                            SUM(ROUND(account_move_line.balance * currency_table.rate, currency_table.precision)) AS balance
                        FROM %(tables)s
                        LEFT JOIN %(ct_query)s ON currency_table.company_id = account_move_line.company_id
                        WHERE %(where_clause)s
                        GROUP BY account_move_line.partner_id
                    """,
                        column_group_key=column_group_key,
                        tables=query_obj.from_clause,
                        ct_query=ct_sql,
                        where_clause=query_obj.where_clause
                    ))
                else:
                    queries.append(SQL("""
                        SELECT
                            account_move_line.partner_id                                                          AS groupby,
                            %(column_group_key)s                                                                  AS column_group_key,
                            SUM(ROUND(account_move_line.debit_usd, currency_table.precision))   AS debit,
                            SUM(ROUND(account_move_line.credit_usd, currency_table.precision))  AS credit,
                            SUM(ROUND(account_move_line.balance_usd, currency_table.precision)) AS balance
                        FROM %(tables)s
                        LEFT JOIN %(ct_query)s ON currency_table.company_id = account_move_line.company_id
                        WHERE %(where_clause)s
                        GROUP BY account_move_line.partner_id
                    """,
                        column_group_key=column_group_key,
                        tables=query_obj.from_clause,
                        ct_query=ct_sql,
                        where_clause=query_obj.where_clause
                    ))

        return SQL(" UNION ALL ").join(queries), []


    def _get_aml_values(self, options, partner_ids, offset=0, limit=None):
        rslt = {partner_id: [] for partner_id in partner_ids}

        partner_ids_wo_none = [x for x in partner_ids if x]
        directly_linked_aml_partner_clauses = []
        directly_linked_aml_partner_params = []
        indirectly_linked_aml_partner_params = []
        indirectly_linked_aml_partner_clause = 'aml_with_partner.partner_id IS NOT NULL'
        if None in partner_ids:
            directly_linked_aml_partner_clauses.append('account_move_line.partner_id IS NULL')
        if partner_ids_wo_none:
            directly_linked_aml_partner_clauses.append('account_move_line.partner_id IN %s')
            directly_linked_aml_partner_params.append(tuple(partner_ids_wo_none))
            indirectly_linked_aml_partner_clause = 'aml_with_partner.partner_id IN %s'
            indirectly_linked_aml_partner_params.append(tuple(partner_ids_wo_none))
        directly_linked_aml_partner_clause = '(' + ' OR '.join(directly_linked_aml_partner_clauses) + ')'

        ct_sql_base = self.env['res.currency']._get_simple_currency_table(options)
        ct_sql = SQL("(%(subquery)s) AS currency_table", subquery=ct_sql_base)
        queries = []
        lang = self.env.lang or get_lang(self.env).code
        journal_name = f"COALESCE(journal.name->>'{lang}', journal.name->>'en_US')" if \
            self.pool['account.journal'].name.translate else 'journal.name'
        account_name = f"COALESCE(account.name->>'{lang}', account.name->>'en_US')" if \
            self.pool['account.account'].name.translate else 'account.name'
        report = self.env.ref('account_reports.partner_ledger_report')
        currency_dif = options['currency_dif']
        for column_group_key, group_options in report._split_options_per_column_group(options).items():
            query_obj = report._get_report_query(group_options, 'strict_range')

            # For the move lines directly linked to this partner
            if currency_dif == self.env.company.currency_id.symbol:
                queries.append(SQL("""
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
                        %(account_name)s                                                                 AS account_name,
                        journal.code                                                                     AS journal_code,
                        %(journal_name)s                                                                 AS journal_name,
                        %(column_group_key)s                                                             AS column_group_key,
                        'directly_linked_aml'                                                            AS key
                    FROM %(tables)s
                    JOIN account_move ON account_move.id = account_move_line.move_id
                    LEFT JOIN %(ct_query)s ON currency_table.company_id = account_move_line.company_id
                    LEFT JOIN res_company company               ON company.id = account_move_line.company_id
                    LEFT JOIN res_partner partner               ON partner.id = account_move_line.partner_id
                    LEFT JOIN account_account account           ON account.id = account_move_line.account_id
                    LEFT JOIN account_journal journal           ON journal.id = account_move_line.journal_id
                    WHERE %(where_clause)s AND %(directly_linked_aml_partner_clause)s
                    ORDER BY account_move_line.date, account_move_line.id
                """,
                    account_name=SQL(account_name),
                    journal_name=SQL(journal_name),
                    column_group_key=column_group_key,
                    tables=query_obj.from_clause,
                    ct_query=ct_sql,
                    where_clause=query_obj.where_clause,
                    directly_linked_aml_partner_clause=SQL(directly_linked_aml_partner_clause, *directly_linked_aml_partner_params)
                ))

                # For the move lines linked to no partner, but reconciled with this partner.
                queries.append(SQL("""
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
                        %(account_name)s                                                                    AS account_name,
                        journal.code                                                                        AS journal_code,
                        %(journal_name)s                                                                    AS journal_name,
                        %(column_group_key)s                                                                AS column_group_key,
                        'indirectly_linked_aml'                                                             AS key
                    FROM %(tables)s,
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
                        AND %(indirectly_linked_aml_partner_clause)s
                        AND journal.id = account_move_line.journal_id
                        AND account.id = account_move_line.account_id
                        AND %(where_clause)s
                        AND partial.max_date BETWEEN %(date_from)s AND %(date_to)s
                    ORDER BY account_move_line.date, account_move_line.id
                """,
                    account_name=SQL(account_name),
                    journal_name=SQL(journal_name),
                    column_group_key=column_group_key,
                    tables=query_obj.from_clause,
                    indirectly_linked_aml_partner_clause=SQL(indirectly_linked_aml_partner_clause, *indirectly_linked_aml_partner_params),
                    where_clause=query_obj.where_clause,
                    date_from=group_options['date']['date_from'],
                    date_to=group_options['date']['date_to']
                ))
            else:
                queries.append(SQL("""
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
                        %(account_name)s                                                                 AS account_name,
                        journal.code                                                                     AS journal_code,
                        %(journal_name)s                                                                 AS journal_name,
                        %(column_group_key)s                                                             AS column_group_key,
                        'directly_linked_aml'                                                            AS key
                    FROM %(tables)s
                    JOIN account_move ON account_move.id = account_move_line.move_id
                    LEFT JOIN %(ct_query)s ON currency_table.company_id = account_move_line.company_id
                    LEFT JOIN res_company company               ON company.id = account_move_line.company_id
                    LEFT JOIN res_partner partner               ON partner.id = account_move_line.partner_id
                    LEFT JOIN account_account account           ON account.id = account_move_line.account_id
                    LEFT JOIN account_journal journal           ON journal.id = account_move_line.journal_id
                    WHERE %(where_clause)s AND %(directly_linked_aml_partner_clause)s
                    ORDER BY account_move_line.date, account_move_line.id
                """,
                    account_name=SQL(account_name),
                    journal_name=SQL(journal_name),
                    column_group_key=column_group_key,
                    tables=query_obj.from_clause,
                    ct_query=ct_sql,
                    where_clause=query_obj.where_clause,
                    directly_linked_aml_partner_clause=SQL(directly_linked_aml_partner_clause, *directly_linked_aml_partner_params)
                ))

                # For the move lines linked to no partner, but reconciled with this partner.
                queries.append(SQL("""
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
                        %(account_name)s                                                                    AS account_name,
                        journal.code                                                                        AS journal_code,
                        %(journal_name)s                                                                    AS journal_name,
                        %(column_group_key)s                                                                AS column_group_key,
                        'indirectly_linked_aml'                                                             AS key
                    FROM %(tables)s,
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
                        AND %(indirectly_linked_aml_partner_clause)s
                        AND journal.id = account_move_line.journal_id
                        AND account.id = account_move_line.account_id
                        AND %(where_clause)s
                        AND partial.max_date BETWEEN %(date_from)s AND %(date_to)s
                    ORDER BY account_move_line.date, account_move_line.id
                """,
                    account_name=SQL(account_name),
                    journal_name=SQL(journal_name),
                    column_group_key=column_group_key,
                    tables=query_obj.from_clause,
                    indirectly_linked_aml_partner_clause=SQL(indirectly_linked_aml_partner_clause, *indirectly_linked_aml_partner_params),
                    where_clause=query_obj.where_clause,
                    date_from=group_options['date']['date_from'],
                    date_to=group_options['date']['date_to']
                ))

        query = SQL(" UNION ALL ").join(queries)

        if offset:
            query = SQL("%(query)s OFFSET %(offset)s", query=query, offset=offset)

        if limit:
            query = SQL("%(query)s LIMIT %(limit)s", query=query, limit=limit)

        self._cr.execute(query)
        for aml_result in self._cr.dictfetchall():
            if aml_result['key'] == 'indirectly_linked_aml':

                # Append the line to the partner found through the reconciliation.
                if aml_result['partner_id'] in rslt:
                    rslt[aml_result['partner_id']].append(aml_result)

                # Balance it with an additional line in the Unknown Partner section but having reversed amounts.
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
