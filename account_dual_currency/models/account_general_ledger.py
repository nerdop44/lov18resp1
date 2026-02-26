# Libro mayor y balance general
import json

from odoo import models, fields, api, _
from odoo.tools import SQL
from odoo.tools.misc import format_date
from odoo.tools import get_lang
from odoo.exceptions import UserError

from datetime import timedelta
from collections import defaultdict


class GeneralLedgerCustomHandler(models.AbstractModel):
    _inherit = 'account.general.ledger.report.handler'

    def _get_query_sums(self, report, options):
        """ Construct a query retrieving all the aggregated sums to build the report. It includes:
        - sums for all accounts.
        - sums for the initial balances.
        - sums for the unaffected earnings.
        - sums for the tax declaration.
        :return:                    (query, params)
        """
        options_by_column_group = report._split_options_per_column_group(options)

        params = []
        queries = []

        # Create the currency table.
        # As the currency table is the same whatever the comparisons, create it only once.
        ct_sql = self.env['res.currency']._get_simple_currency_table(options)
        currency_dif = options['currency_dif']
        rate_mode = options.get('rate_mode', 'historical')
        # ============================================
        # 1) Get sums for all accounts.
        # ============================================
        for column_group_key, options_group in options_by_column_group.items():
            # Sum is computed including the initial balance of the accounts configured to do so, unless a special option key is used
            # (this is required for trial balance, which is based on general ledger)
            sum_date_scope = 'strict_range' if options_group.get('general_ledger_strict_range') else 'normal'

            query_domain = []

            if options.get('filter_search_bar'):
                query_domain.append(('account_id', 'ilike', options['filter_search_bar']))

            if options_group.get('include_current_year_in_unaff_earnings'):
                query_domain += [('account_id.include_initial_balance', '=', True)]

            query_obj = report._get_report_query(options_group, sum_date_scope, domain=query_domain)
            
            if currency_dif == self.env.company.currency_id.symbol:
                queries.append(SQL("""
                    SELECT
                        account_move_line.account_id                            AS groupby,
                        'sum'                                                   AS key,
                        MAX(account_move_line.date)                             AS max_date,
                        %(column_group_key)s                                    AS column_group_key,
                        COALESCE(SUM(account_move_line.amount_currency), 0.0)   AS amount_currency,
                        SUM(ROUND(account_move_line.debit * currency_table.rate, currency_table.precision))   AS debit,
                        SUM(ROUND(account_move_line.credit * currency_table.rate, currency_table.precision))  AS credit,
                        SUM(ROUND(account_move_line.balance * currency_table.rate, currency_table.precision)) AS balance
                    FROM %(tables)s
                    LEFT JOIN %(ct_query)s ON currency_table.company_id = account_move_line.company_id
                    WHERE %(where_clause)s
                    GROUP BY account_move_line.account_id
                """,
                    column_group_key=column_group_key,
                    tables=query_obj.from_clause,
                    ct_query=ct_sql,
                    where_clause=query_obj.where_clause
                ))
            else:
                queries.append(SQL("""
                    SELECT
                        account_move_line.account_id                            AS groupby,
                        'sum'                                                   AS key,
                        MAX(account_move_line.date)                             AS max_date,
                        %(column_group_key)s                                    AS column_group_key,
                        COALESCE(SUM(0), 0.0)                                   AS amount_currency,
                        SUM(ROUND(account_move_line.debit_usd, currency_table.precision))   AS debit,
                        SUM(ROUND(account_move_line.credit_usd, currency_table.precision))  AS credit,
                        SUM(ROUND(account_move_line.balance_usd, currency_table.precision)) AS balance
                    FROM %(tables)s
                    LEFT JOIN %(ct_query)s ON currency_table.company_id = account_move_line.company_id
                    WHERE %(where_clause)s
                    GROUP BY account_move_line.account_id
                """,
                    column_group_key=column_group_key,
                    tables=query_obj.from_clause,
                    ct_query=ct_sql,
                    where_clause=query_obj.where_clause
                ))
            # ============================================
            # 2) Get sums for the unaffected earnings.
            # ============================================
            if not options_group.get('general_ledger_strict_range'):
                unaff_earnings_domain = [('account_id.include_initial_balance', '=', False)]

                # The period domain is expressed as:
                # [
                #   ('date' <= fiscalyear['date_from'] - 1),
                #   ('account_id.include_initial_balance', '=', False),
                # ]

                new_options = self._get_options_unaffected_earnings(options_group)
                query_obj = report._get_report_query(new_options, 'strict_range', domain=unaff_earnings_domain)

                if currency_dif == self.env.company.currency_id.symbol:
                    queries.append(SQL("""
                        SELECT
                            account_move_line.company_id                            AS groupby,
                            'unaffected_earnings'                                   AS key,
                            NULL                                                    AS max_date,
                            %(column_group_key)s                                    AS column_group_key,
                            COALESCE(SUM(account_move_line.amount_currency), 0.0)   AS amount_currency,
                            SUM(ROUND(account_move_line.debit * currency_table.rate, currency_table.precision))   AS debit,
                            SUM(ROUND(account_move_line.credit * currency_table.rate, currency_table.precision))  AS credit,
                            SUM(ROUND(account_move_line.balance * currency_table.rate, currency_table.precision)) AS balance
                        FROM %(tables)s
                        LEFT JOIN %(ct_query)s ON currency_table.company_id = account_move_line.company_id
                        WHERE %(where_clause)s
                        GROUP BY account_move_line.company_id
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
                                account_move_line.company_id                            AS groupby,
                                'unaffected_earnings'                                   AS key,
                                NULL                                                    AS max_date,
                                %(column_group_key)s                                    AS column_group_key,
                                COALESCE(SUM(0), 0.0)                                   AS amount_currency,
                                SUM(ROUND(account_move_line.debit * currency_table.rate, currency_table.precision))   AS debit,
                                SUM(ROUND(account_move_line.credit * currency_table.rate, currency_table.precision))  AS credit,
                                SUM(ROUND(account_move_line.balance * currency_table.rate, currency_table.precision)) AS balance
                            FROM %(tables)s
                            LEFT JOIN %(ct_query)s ON currency_table.company_id = account_move_line.company_id
                            WHERE %(where_clause)s
                            GROUP BY account_move_line.company_id
                        """,
                            column_group_key=column_group_key,
                            tables=query_obj.from_clause,
                            ct_query=ct_sql,
                            where_clause=query_obj.where_clause
                        ))
                    else:
                        queries.append(SQL("""
                            SELECT
                                account_move_line.company_id                            AS groupby,
                                'unaffected_earnings'                                   AS key,
                                NULL                                                    AS max_date,
                                %(column_group_key)s                                    AS column_group_key,
                                COALESCE(SUM(0), 0.0)                                   AS amount_currency,
                                SUM(ROUND(account_move_line.debit_usd, currency_table.precision))   AS debit,
                                SUM(ROUND(account_move_line.credit_usd, currency_table.precision))  AS credit,
                                SUM(ROUND(account_move_line.balance_usd, currency_table.precision)) AS balance
                            FROM %(tables)s
                            LEFT JOIN %(ct_query)s ON currency_table.company_id = account_move_line.company_id
                            WHERE %(where_clause)s
                            GROUP BY account_move_line.company_id
                        """,
                            column_group_key=column_group_key,
                            tables=query_obj.from_clause,
                            ct_query=ct_sql,
                            where_clause=query_obj.where_clause
                        ))

        return SQL(" UNION ALL ").join(queries) if queries else SQL()

    def _get_query_amls(self, report, options, expanded_account_ids, offset=0, limit=None):
        """ Construct a query retrieving the account.move.lines when expanding a report line with or without the load
        more.
        :param options:               The report options.
        :param expanded_account_ids:  The account.account ids corresponding to consider. If None, match every account.
        :param offset:                The offset of the query (used by the load more).
        :param limit:                 The limit of the query (used by the load more).
        :return:                      (query, params)
        """
        additional_domain = [('account_id', 'in', expanded_account_ids)] if expanded_account_ids is not None else None
        queries = []
        all_params = []
        currency_dif = options['currency_dif']
        rate_mode = options.get('rate_mode', 'historical')
        lang = self.env.user.lang or get_lang(self.env).code
        journal_name = f"COALESCE(journal.name->>'{lang}', journal.name->>'en_US')" if \
            self.pool['account.journal'].name.translate else 'journal.name'
        account_name = f"COALESCE(account.name->>'{lang}', account.name->>'en_US')" if \
            self.pool['account.account'].name.translate else 'account.name'
        for column_group_key, group_options in report._split_options_per_column_group(options).items():
            # Get sums for the account move lines.
            # period: [('date' <= options['date_to']), ('date', '>=', options['date_from'])]
            query_obj = report._get_report_query(group_options, domain=additional_domain, date_scope='strict_range')
            ct_sql = self.env['res.currency']._get_query_currency_table(group_options)
            
            if currency_dif == self.env.company.currency_id.symbol:
                query = SQL('''
                    (SELECT
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
                        account_move_line.debit,
                        account_move_line.credit,
                        account_move_line.balance,
                        move.name                               AS move_name,
                        company.currency_id                     AS company_currency_id,
                        partner.name                            AS partner_name,
                        move.move_type                          AS move_type,
                        account.code                            AS account_code,
                        %(account_name)s                        AS account_name,
                        journal.code                            AS journal_code,
                        %(journal_name)s                        AS journal_name,
                        full_rec.name                           AS full_rec_name,
                        %(column_group_key)s                    AS column_group_key
                    FROM %(tables)s
                    JOIN account_move move                      ON move.id = account_move_line.move_id
                    LEFT JOIN %(ct_query)s                      ON currency_table.company_id = account_move_line.company_id
                    LEFT JOIN res_company company               ON company.id = account_move_line.company_id
                    LEFT JOIN res_partner partner               ON partner.id = account_move_line.partner_id
                    LEFT JOIN account_account account           ON account.id = account_move_line.account_id
                    LEFT JOIN account_journal journal           ON journal.id = account_move_line.journal_id
                    LEFT JOIN account_full_reconcile full_rec   ON full_rec.id = account_move_line.full_reconcile_id
                    WHERE %(where_clause)s
                    ORDER BY account_move_line.date, account_move_line.id)
                ''',
                    account_name=SQL(account_name),
                    journal_name=SQL(journal_name),
                    column_group_key=column_group_key,
                    tables=query_obj.from_clause,
                    ct_query=ct_sql,
                    where_clause=query_obj.where_clause
                )
            else:
                if rate_mode == 'current':
                    query = SQL('''
                            (SELECT
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
                                %(account_name)s                        AS account_name,
                                journal.code                            AS journal_code,
                                %(journal_name)s                        AS journal_name,
                                full_rec.name                           AS full_rec_name,
                                %(column_group_key)s                    AS column_group_key
                            FROM %(tables)s
                            JOIN account_move move                      ON move.id = account_move_line.move_id
                            LEFT JOIN %(ct_query)s                      ON currency_table.company_id = account_move_line.company_id
                            LEFT JOIN res_company company               ON company.id = account_move_line.company_id
                            LEFT JOIN res_partner partner               ON partner.id = account_move_line.partner_id
                            LEFT JOIN account_account account           ON account.id = account_move_line.account_id
                            LEFT JOIN account_journal journal           ON journal.id = account_move_line.journal_id
                            LEFT JOIN account_full_reconcile full_rec   ON full_rec.id = account_move_line.full_reconcile_id
                            WHERE %(where_clause)s
                            ORDER BY account_move_line.date, account_move_line.id)
                        ''',
                            account_name=SQL(account_name),
                            journal_name=SQL(journal_name),
                            column_group_key=column_group_key,
                            tables=query_obj.from_clause,
                            ct_query=ct_sql,
                            where_clause=query_obj.where_clause
                        )
                else:
                    query = SQL('''
                            (SELECT
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
                                %(account_name)s                        AS account_name,
                                journal.code                            AS journal_code,
                                %(journal_name)s                        AS journal_name,
                                full_rec.name                           AS full_rec_name,
                                %(column_group_key)s                    AS column_group_key
                            FROM %(tables)s
                            JOIN account_move move                      ON move.id = account_move_line.move_id
                            LEFT JOIN %(ct_query)s                      ON currency_table.company_id = account_move_line.company_id
                            LEFT JOIN res_company company               ON company.id = account_move_line.company_id
                            LEFT JOIN res_partner partner               ON partner.id = account_move_line.partner_id
                            LEFT JOIN account_account account           ON account.id = account_move_line.account_id
                            LEFT JOIN account_journal journal           ON journal.id = account_move_line.journal_id
                            LEFT JOIN account_full_reconcile full_rec   ON full_rec.id = account_move_line.full_reconcile_id
                            WHERE %(where_clause)s
                            ORDER BY account_move_line.date, account_move_line.id)
                        ''',
                            account_name=SQL(account_name),
                            journal_name=SQL(journal_name),
                            column_group_key=column_group_key,
                            tables=query_obj.from_clause,
                            ct_query=ct_sql,
                            where_clause=query_obj.where_clause
                        )

            queries.append(query)

        full_query = SQL(" UNION ALL ").join(queries)

        if offset:
            full_query = SQL("%s OFFSET %s", full_query, offset)
        if limit:
            full_query = SQL("%s LIMIT %s", full_query, limit)

        return full_query

    def _get_initial_balance_values(self, report, account_ids, options):
        """
        Get sums for the initial balance.
        """
        queries = []
        params = []
        currency_dif = options['currency_dif']
        rate_mode = options.get('rate_mode', 'historical')
        
        for column_group_key, options_group in report._split_options_per_column_group(options).items():
            new_options = self._get_options_initial_balance(options_group)
            ct_sql = self.env['res.currency']._get_simple_currency_table(new_options)
            
            query_obj = report._get_report_query(new_options, 'normal', domain=[
                ('account_id', 'in', account_ids),
                ('account_id.include_initial_balance', '=', True),
            ])
            
            if currency_dif == self.env.company.currency_id.symbol:
                queries.append(SQL("""
                    SELECT
                        account_move_line.account_id                                                          AS groupby,
                        'initial_balance'                                                                     AS key,
                        NULL                                                                                  AS max_date,
                        %(column_group_key)s                                                                  AS column_group_key,
                        COALESCE(SUM(account_move_line.amount_currency), 0.0)                                 AS amount_currency,
                        SUM(account_move_line.debit)   AS debit,
                        SUM(account_move_line.credit)  AS credit,
                        SUM(account_move_line.balance) AS balance
                    FROM %(tables)s
                    LEFT JOIN %(ct_query)s ON currency_table.company_id = account_move_line.company_id
                    WHERE %(where_clause)s
                    GROUP BY account_move_line.account_id
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
                            account_move_line.account_id                                                          AS groupby,
                            'initial_balance'                                                                     AS key,
                            NULL                                                                                  AS max_date,
                            %(column_group_key)s                                                                  AS column_group_key,
                            COALESCE(SUM(0), 0.0)                                                                 AS amount_currency,
                            SUM(ROUND(account_move_line.debit * currency_table.rate, currency_table.precision))   AS debit,
                            SUM(ROUND(account_move_line.credit * currency_table.rate, currency_table.precision))  AS credit,
                            SUM(ROUND(account_move_line.balance * currency_table.rate, currency_table.precision)) AS balance
                    FROM %(tables)s
                    LEFT JOIN %(ct_query)s ON currency_table.company_id = account_move_line.company_id
                    WHERE %(where_clause)s
                    GROUP BY account_move_line.account_id
                """,
                    column_group_key=column_group_key,
                    tables=query_obj.from_clause,
                    ct_query=ct_sql,
                    where_clause=query_obj.where_clause
                ))
                else:
                    queries.append(SQL("""
                        SELECT
                            account_move_line.account_id                                                          AS groupby,
                            'initial_balance'                                                                     AS key,
                            NULL                                                                                  AS max_date,
                            %(column_group_key)s                                                                  AS column_group_key,
                            COALESCE(SUM(0), 0.0)                                                                 AS amount_currency,
                            SUM(ROUND(account_move_line.debit_usd, currency_table.precision))   AS debit,
                            SUM(ROUND(account_move_line.credit_usd, currency_table.precision))  AS credit,
                            SUM(ROUND(account_move_line.balance_usd, currency_table.precision)) AS balance
                    FROM %(tables)s
                    LEFT JOIN %(ct_query)s ON currency_table.company_id = account_move_line.company_id
                    WHERE %(where_clause)s
                    GROUP BY account_move_line.account_id
                """,
                    column_group_key=column_group_key,
                    tables=query_obj.from_clause,
                    ct_query=ct_sql,
                    where_clause=query_obj.where_clause
                ))

        self._cr.execute(SQL(" UNION ALL ").join(queries)) if queries else None

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