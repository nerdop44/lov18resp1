# Libro mayor y balance general
import json

from odoo import models, fields, api, _
from odoo.tools.misc import format_date
from odoo.tools import get_lang, SQL
from odoo.exceptions import UserError

from datetime import timedelta
from collections import defaultdict


class GeneralLedgerCustomHandler(models.AbstractModel):
    _inherit = 'account.general.ledger.report.handler'

    def _get_query_sums(self, report, options):
        options_by_column_group = report._split_options_per_column_group(options)
        queries = []
        companies = self.env['res.company'].browse(options.get('company_ids') or self.env.companies.ids)
        ct_query = self.env['res.currency']._get_simple_currency_table(companies)
        currency_dif = options['currency_dif']

        for column_group_key, options_group in options_by_column_group.items():
            sum_date_scope = 'strict_range' if options_group.get('general_ledger_strict_range') else 'normal'
            query_domain = []
            if options.get('filter_search_bar'):
                query_domain.append(('account_id', 'ilike', options['filter_search_bar']))
            if options_group.get('include_current_year_in_unaff_earnings'):
                query_domain += [('account_id.include_initial_balance', '=', True)]

            query_res = report._get_report_query(options_group, sum_date_scope, domain=query_domain)
            tables, where_clause, where_params = query_res.get_sql()

            if currency_dif == self.env.company.currency_id.symbol:
                queries.append(SQL(
                    """
                    SELECT
                        account_move_line.account_id                            AS groupby,
                        'sum'                                                   AS key,
                        MAX(account_move_line.date)                             AS max_date,
                        %s                                                      AS column_group_key,
                        COALESCE(SUM(account_move_line.amount_currency), 0.0)   AS amount_currency,
                        SUM(ROUND(account_move_line.debit * currency_table.rate, currency_table.precision))   AS debit,
                        SUM(ROUND(account_move_line.credit * currency_table.rate, currency_table.precision))  AS credit,
                        SUM(ROUND(account_move_line.balance * currency_table.rate, currency_table.precision)) AS balance
                    FROM %s
                    LEFT JOIN %s ON currency_table.company_id = account_move_line.company_id
                    WHERE %s
                    GROUP BY account_move_line.account_id
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
                        account_move_line.account_id                            AS groupby,
                        'sum'                                                   AS key,
                        MAX(account_move_line.date)                             AS max_date,
                        %s                                                      AS column_group_key,
                        COALESCE(SUM(0), 0.0)                                   AS amount_currency,
                        SUM(ROUND(account_move_line.debit_usd, currency_table.precision))   AS debit,
                        SUM(ROUND(account_move_line.credit_usd, currency_table.precision))  AS credit,
                        SUM(ROUND(account_move_line.balance_usd, currency_table.precision)) AS balance
                    FROM %s
                    LEFT JOIN %s ON currency_table.company_id = account_move_line.company_id
                    WHERE %s
                    GROUP BY account_move_line.account_id
                    """,
                    column_group_key,
                    tables,
                    ct_query,
                    where_clause,
                ))

            if not options_group.get('general_ledger_strict_range'):
                unaff_earnings_domain = [('account_id.include_initial_balance', '=', False)]
                new_options = self._get_options_unaffected_earnings(options_group)
                query_res = report._get_report_query(new_options, 'strict_range', domain=unaff_earnings_domain)
                tables, where_clause, where_params = query_res.get_sql()

                if currency_dif == self.env.company.currency_id.symbol:
                    queries.append(SQL(
                        """
                        SELECT
                            account_move_line.company_id                            AS groupby,
                            'unaffected_earnings'                                   AS key,
                            NULL                                                    AS max_date,
                            %s                                                      AS column_group_key,
                            COALESCE(SUM(account_move_line.amount_currency), 0.0)   AS amount_currency,
                            SUM(ROUND(account_move_line.debit * currency_table.rate, currency_table.precision))   AS debit,
                            SUM(ROUND(account_move_line.credit * currency_table.rate, currency_table.precision))  AS credit,
                            SUM(ROUND(account_move_line.balance * currency_table.rate, currency_table.precision)) AS balance
                        FROM %s
                        LEFT JOIN %s ON currency_table.company_id = account_move_line.company_id
                        WHERE %s
                        GROUP BY account_move_line.company_id
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
                            account_move_line.company_id                            AS groupby,
                            'unaffected_earnings'                                   AS key,
                            NULL                                                    AS max_date,
                            %s                                                      AS column_group_key,
                            COALESCE(SUM(0), 0.0)                                   AS amount_currency,
                            SUM(ROUND(account_move_line.debit_usd, currency_table.precision))   AS debit,
                            SUM(ROUND(account_move_line.credit_usd, currency_table.precision))  AS credit,
                            SUM(ROUND(account_move_line.balance_usd, currency_table.precision)) AS balance
                        FROM %s
                        LEFT JOIN %s ON currency_table.company_id = account_move_line.company_id
                        WHERE %s
                        GROUP BY account_move_line.company_id
                        """,
                        column_group_key,
                        tables,
                        ct_query,
                        where_clause,
                    ))

        return SQL.join(' UNION ALL ', queries)

    def _get_query_amls(self, report, options, expanded_account_ids, offset=0, limit=None):
        additional_domain = [('account_id', 'in', expanded_account_ids)] if expanded_account_ids is not None else None
        queries = []
        currency_dif = options['currency_dif']
        lang = self.env.user.lang or get_lang(self.env).code
        journal_name = SQL("COALESCE(journal.name->>%s, journal.name->>'en_US')", lang) if \
            self.pool['account.journal'].name.translate else SQL("journal.name")
        account_name = SQL("COALESCE(account.name->>%s, account.name->>'en_US')", lang) if \
            self.pool['account.account'].name.translate else SQL("account.name")

        for column_group_key, group_options in report._split_options_per_column_group(options).items():
            query_res = report._get_report_query(group_options, domain=additional_domain, date_scope='strict_range')
            tables, where_clause, where_params = query_res.get_sql()
            companies = self.env['res.company'].browse(group_options.get('company_ids') or self.env.companies.ids)
            ct_query = self.env['res.currency']._get_simple_currency_table(companies)
            
            if currency_dif == self.env.company.currency_id.symbol:
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
                        ROUND(account_move_line.debit * currency_table.rate, currency_table.precision)   AS debit,
                        ROUND(account_move_line.credit * currency_table.rate, currency_table.precision)  AS credit,
                        ROUND(account_move_line.balance * currency_table.rate, currency_table.precision) AS balance,
                        move.name                               AS move_name,
                        company.currency_id                     AS company_currency_id,
                        partner.name                            AS partner_name,
                        move.move_type                          AS move_type,
                        account.code                            AS account_code,
                        %s                                      AS account_name,
                        journal.code                            AS journal_code,
                        %s                                      AS journal_name,
                        full_rec.name                           AS full_rec_name,
                        %s                                      AS column_group_key
                    FROM %s
                    JOIN account_move move                      ON move.id = account_move_line.move_id
                    LEFT JOIN %s                                ON currency_table.company_id = account_move_line.company_id
                    LEFT JOIN res_company company               ON company.id = account_move_line.company_id
                    LEFT JOIN res_partner partner               ON partner.id = account_move_line.partner_id
                    LEFT JOIN account_account account           ON account.id = account_move_line.account_id
                    LEFT JOIN account_journal journal           ON journal.id = account_move_line.journal_id
                    LEFT JOIN account_full_reconcile full_rec   ON full_rec.id = account_move_line.full_reconcile_id
                    WHERE %s
                    ORDER BY account_move_line.date, account_move_line.id
                    """,
                    account_name,
                    journal_name,
                    column_group_key,
                    tables,
                    ct_query,
                    where_clause,
                ))
            else:
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
                        ROUND(account_move_line.debit_usd, currency_table.precision)   AS debit,
                        ROUND(account_move_line.credit_usd, currency_table.precision)  AS credit,
                        ROUND(account_move_line.balance_usd, currency_table.precision) AS balance,
                        move.name                               AS move_name,
                        company.currency_id                     AS company_currency_id,
                        partner.name                            AS partner_name,
                        move.move_type                          AS move_type,
                        account.code                            AS account_code,
                        %s                                      AS account_name,
                        journal.code                            AS journal_code,
                        %s                                      AS journal_name,
                        full_rec.name                           AS full_rec_name,
                        %s                                      AS column_group_key
                    FROM %s
                    JOIN account_move move                      ON move.id = account_move_line.move_id
                    LEFT JOIN %s                                ON currency_table.company_id = account_move_line.company_id
                    LEFT JOIN res_company company               ON company.id = account_move_line.company_id
                    LEFT JOIN res_partner partner               ON partner.id = account_move_line.partner_id
                    LEFT JOIN account_account account           ON account.id = account_move_line.account_id
                    LEFT JOIN account_journal journal           ON journal.id = account_move_line.journal_id
                    LEFT JOIN account_full_reconcile full_rec   ON full_rec.id = account_move_line.full_reconcile_id
                    WHERE %s
                    ORDER BY account_move_line.date, account_move_line.id
                    """,
                    account_name,
                    journal_name,
                    column_group_key,
                    tables,
                    ct_query,
                    where_clause,
                ))

        full_query = SQL.join(' UNION ALL ', [SQL("(%s)", q) for q in queries])
        if offset:
            full_query = SQL("%s OFFSET %s ", full_query, offset)
        if limit:
            full_query = SQL("%s LIMIT %s ", full_query, limit)

        return full_query

    def _get_initial_balance_values(self, report, account_ids, options):
        queries = []
        currency_dif = options['currency_dif']
        for column_group_key, options_group in report._split_options_per_column_group(options).items():
            new_options = self._get_options_initial_balance(options_group)
            companies = self.env['res.company'].browse(new_options.get('company_ids') or self.env.companies.ids)
            ct_query = self.env['res.currency']._get_simple_currency_table(companies)
            query_res = report._get_report_query(new_options, 'normal', domain=[
                ('account_id', 'in', account_ids),
                ('account_id.include_initial_balance', '=', True),
            ])
            tables, where_clause, where_params = query_res.get_sql()

            if currency_dif == self.env.company.currency_id.symbol:
                queries.append(SQL(
                    """
                    SELECT
                        account_move_line.account_id                                                          AS groupby,
                        'initial_balance'                                                                     AS key,
                        NULL                                                                                  AS max_date,
                        %s                                                                                    AS column_group_key,
                        COALESCE(SUM(account_move_line.amount_currency), 0.0)                                 AS amount_currency,
                        SUM(ROUND(account_move_line.debit * currency_table.rate, currency_table.precision))   AS debit,
                        SUM(ROUND(account_move_line.credit * currency_table.rate, currency_table.precision))  AS credit,
                        SUM(ROUND(account_move_line.balance * currency_table.rate, currency_table.precision)) AS balance
                    FROM %s
                    LEFT JOIN %s ON currency_table.company_id = account_move_line.company_id
                    WHERE %s
                    GROUP BY account_move_line.account_id
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
                        account_move_line.account_id                                                          AS groupby,
                        'initial_balance'                                                                     AS key,
                        NULL                                                                                  AS max_date,
                        %s                                                                                    AS column_group_key,
                        COALESCE(SUM(0), 0.0)                                                                 AS amount_currency,
                        SUM(ROUND(account_move_line.debit_usd, currency_table.precision))   AS debit,
                        SUM(ROUND(account_move_line.credit_usd, currency_table.precision))  AS credit,
                        SUM(ROUND(account_move_line.balance_usd, currency_table.precision)) AS balance
                    FROM %s
                    LEFT JOIN %s ON currency_table.company_id = account_move_line.company_id
                    WHERE %s
                    GROUP BY account_move_line.account_id
                    """,
                    column_group_key,
                    tables,
                    ct_query,
                    where_clause,
                ))

        self._cr.execute(SQL.join(' UNION ALL ', queries))

        init_balance_by_col_group = {
            account_id: {column_group_key: {} for column_group_key in options['column_groups']}
            for account_id in account_ids
        }
        for result in self._cr.dictfetchall():
            init_balance_by_col_group[result['groupby']][result['column_group_key']] = result

        accounts = self.env['account.account'].browse(account_ids)
        return {
            account.id: (account, init_balance_by_col_group[account.id])
            for account in accounts
        }