
from odoo import models, fields, api, _
from odoo.tools import SQL
from odoo.tools.misc import get_lang


class CashFlowReportCustomHandler(models.AbstractModel):
    _inherit = 'account.cash.flow.report.handler'

    def _compute_liquidity_balance(self, report, options, currency_table_query, payment_account_ids, date_scope):
        ''' Compute the balance of all liquidity accounts to populate the following sections:
            'Cash and cash equivalents, beginning of period' and 'Cash and cash equivalents, closing balance'.
        '''
        queries = []
        currency_dif = options['currency_dif']
        if self.pool['account.account'].name.translate:
            lang = self.env.user.lang or get_lang(self.env).code
            account_name_str = f"COALESCE(account_account.name->>'{lang}', account_account.name->>'en_US')"
        else:
            account_name_str = 'account_account.name'

        for column_group_key, column_group_options in report._split_options_per_column_group(options).items():
            query_obj = report._get_report_query(column_group_options, date_scope, domain=[('account_id', 'in', payment_account_ids)])
            
            if currency_dif == self.env.company.currency_id.symbol:
                queries.append(SQL("""
                    SELECT
                        %(column_group_key)s AS column_group_key,
                        account_move_line.account_id,
                        account_account.code AS account_code,
                        %(account_name)s AS account_name,
                        SUM(account_move_line.balance) AS balance
                    FROM %(tables)s
                    JOIN account_account
                        ON account_account.id = account_move_line.account_id
                    LEFT JOIN %(ct_query)s
                        ON currency_table.company_id = account_move_line.company_id
                    WHERE %(where_clause)s
                    GROUP BY account_move_line.account_id, account_account.code, account_name
                """,
                    column_group_key=column_group_key,
                    account_name=SQL(account_name_str),
                    tables=query_obj.from_clause,
                    ct_query=currency_table_query,
                    where_clause=query_obj.where_clause
                ))
            else:
                queries.append(SQL("""
                    SELECT
                        %(column_group_key)s AS column_group_key,
                        account_move_line.account_id,
                        account_account.code AS account_code,
                        %(account_name)s AS account_name,
                        SUM(account_move_line.balance_usd) AS balance
                    FROM %(tables)s
                    JOIN account_account
                        ON account_account.id = account_move_line.account_id
                    LEFT JOIN %(ct_query)s
                        ON currency_table.company_id = account_move_line.company_id
                    WHERE %(where_clause)s
                    GROUP BY account_move_line.account_id, account_account.code, account_name
                """,
                    column_group_key=column_group_key,
                    account_name=SQL(account_name_str),
                    tables=query_obj.from_clause,
                    ct_query=currency_table_query,
                    where_clause=query_obj.where_clause
                ))

        self._cr.execute(SQL(' UNION ALL ').join(queries)) if queries else None
        return self._cr.dictfetchall()

    def _get_liquidity_moves(self, report, options, currency_table_query, payment_account_ids, payment_move_ids, cash_flow_tag_ids):
        if not payment_move_ids:
            return []

        reconciled_aml_groupby_account = {}
        queries = []
        currency_dif = options['currency_dif']
        if self.pool['account.account'].name.translate:
            lang = self.env.user.lang or get_lang(self.env).code
            account_name_str = f"COALESCE(account_account.name->>'{lang}', account_account.name->>'en_US')"
        else:
            account_name_str = 'account_account.name'

        for column_group_key, column_group_options in report._split_options_per_column_group(options).items():
            move_ids_subquery = self._get_move_ids_query(report, payment_account_ids, column_group_options)
            
            # move_ids_subquery usually returns a string with f-strings/params in base Odoo.
            # We must be careful if it's already an SQL object or not. 
            # In dual currency module it was redefined to return a string.
            
            if currency_dif == self.env.company.currency_id.symbol:
                subquery = SQL("""
                    WITH payment_move_ids AS (%(move_ids)s)
                    -- Credit amount of each account
                    SELECT
                        %(column_group_key)s AS column_group_key,
                        account_move_line.account_id,
                        account_account.code AS account_code,
                        %(account_name)s AS account_name,
                        account_account.account_type AS account_account_type,
                        account_account_account_tag.account_account_tag_id AS account_tag_id,
                        SUM(ROUND(account_partial_reconcile.amount * currency_table.rate, currency_table.precision)) AS balance
                    FROM account_move_line
                    LEFT JOIN %(ct_query)s
                        ON currency_table.company_id = account_move_line.company_id
                    LEFT JOIN account_partial_reconcile
                        ON account_partial_reconcile.credit_move_id = account_move_line.id
                    JOIN account_account
                        ON account_account.id = account_move_line.account_id
                    LEFT JOIN account_account_account_tag
                        ON account_account_account_tag.account_account_id = account_move_line.account_id
                        AND account_account_account_tag.account_account_tag_id IN %(tags)s
                    WHERE account_move_line.move_id IN (SELECT unnest(payment_move_ids.move_id) FROM payment_move_ids)
                        AND account_move_line.account_id NOT IN %(payment_accounts)s
                        AND account_partial_reconcile.max_date BETWEEN %(date_from)s AND %(date_to)s
                    GROUP BY account_move_line.company_id, account_move_line.account_id, account_account.code, account_name, account_account.account_type, account_account_account_tag.account_account_tag_id
    
                    UNION ALL
    
                    -- Debit amount of each account
                    SELECT
                        %(column_group_key)s AS column_group_key,
                        account_move_line.account_id,
                        account_account.code AS account_code,
                        %(account_name)s AS account_name,
                        account_account.account_type AS account_account_type,
                        account_account_account_tag.account_account_tag_id AS account_tag_id,
                        -SUM(ROUND(account_partial_reconcile.amount * currency_table.rate, currency_table.precision)) AS balance
                    FROM account_move_line
                    LEFT JOIN %(ct_query)s
                        ON currency_table.company_id = account_move_line.company_id
                    LEFT JOIN account_partial_reconcile
                        ON account_partial_reconcile.debit_move_id = account_move_line.id
                    JOIN account_account
                        ON account_account.id = account_move_line.account_id
                    LEFT JOIN account_account_account_tag
                        ON account_account_account_tag.account_account_id = account_move_line.account_id
                         AND account_account_account_tag.account_account_tag_id IN %(tags)s
                    WHERE account_move_line.move_id IN (SELECT unnest(payment_move_ids.move_id) FROM payment_move_ids)
                        AND account_move_line.account_id NOT IN %(payment_accounts)s
                        AND account_partial_reconcile.max_date BETWEEN %(date_from)s AND %(date_to)s
                    GROUP BY account_move_line.company_id, account_move_line.account_id, account_account.code, account_name, account_account.account_type, account_account_account_tag.account_account_tag_id
    
                    UNION ALL
    
                    -- Total amount of each account
                    SELECT
                        %(column_group_key)s AS column_group_key,
                        account_move_line.account_id AS account_id,
                        account_account.code AS account_code,
                        %(account_name)s AS account_name,
                        account_account.account_type AS account_account_type,
                        account_account_account_tag.account_account_tag_id AS account_tag_id,
                        SUM(ROUND(account_move_line.balance * currency_table.rate, currency_table.precision)) AS balance
                    FROM account_move_line
                    LEFT JOIN %(ct_query)s
                        ON currency_table.company_id = account_move_line.company_id
                    JOIN account_account
                        ON account_account.id = account_move_line.account_id
                    LEFT JOIN account_account_account_tag
                        ON account_account_account_tag.account_account_id = account_move_line.account_id
                         AND account_account_account_tag.account_account_tag_id IN %(tags)s
                    WHERE account_move_line.move_id IN (SELECT unnest(payment_move_ids.move_id) FROM payment_move_ids)
                        AND account_move_line.account_id NOT IN %(payment_accounts)s
                    GROUP BY account_move_line.account_id, account_account.code, account_name, account_account.account_type, account_account_account_tag.account_account_tag_id
                """,
                    move_ids=SQL(move_ids_subquery),
                    column_group_key=column_group_key,
                    account_name=SQL(account_name_str),
                    ct_query=currency_table_query,
                    tags=tuple(cash_flow_tag_ids) or (None,),
                    payment_accounts=payment_account_ids,
                    date_from=column_group_options['date']['date_from'],
                    date_to=column_group_options['date']['date_to']
                )
                queries.append(subquery)
            else:
                subquery = SQL("""
                    WITH payment_move_ids AS (%(move_ids)s)
                    -- Credit amount of each account
                    SELECT
                        %(column_group_key)s AS column_group_key,
                        account_move_line.account_id,
                        account_account.code AS account_code,
                        %(account_name)s AS account_name,
                        account_account.account_type AS account_account_type,
                        account_account_account_tag.account_account_tag_id AS account_tag_id,
                        SUM(ROUND(account_partial_reconcile.amount_usd, currency_table.precision)) AS balance
                    FROM account_move_line
                    LEFT JOIN %(ct_query)s
                        ON currency_table.company_id = account_move_line.company_id
                    LEFT JOIN account_partial_reconcile
                        ON account_partial_reconcile.credit_move_id = account_move_line.id
                    JOIN account_account
                        ON account_account.id = account_move_line.account_id
                    LEFT JOIN account_account_account_tag
                        ON account_account_account_tag.account_account_id = account_move_line.account_id
                        AND account_account_account_tag.account_account_tag_id IN %(tags)s
                    WHERE account_move_line.move_id IN (SELECT unnest(payment_move_ids.move_id) FROM payment_move_ids)
                        AND account_move_line.account_id NOT IN %(payment_accounts)s
                        AND account_partial_reconcile.max_date BETWEEN %(date_from)s AND %(date_to)s
                    GROUP BY account_move_line.company_id, account_move_line.account_id, account_account.code, account_name, account_account.account_type, account_account_account_tag.account_account_tag_id
    
                    UNION ALL
    
                    -- Debit amount of each account
                    SELECT
                        %(column_group_key)s AS column_group_key,
                        account_move_line.account_id,
                        account_account.code AS account_code,
                        %(account_name)s AS account_name,
                        account_account.account_type AS account_account_type,
                        account_account_account_tag.account_account_tag_id AS account_tag_id,
                        -SUM(ROUND(account_partial_reconcile.amount_usd, currency_table.precision)) AS balance
                    FROM account_move_line
                    LEFT JOIN %(ct_query)s
                        ON currency_table.company_id = account_move_line.company_id
                    LEFT JOIN account_partial_reconcile
                        ON account_partial_reconcile.debit_move_id = account_move_line.id
                    JOIN account_account
                        ON account_account.id = account_move_line.account_id
                    LEFT JOIN account_account_account_tag
                        ON account_account_account_tag.account_account_id = account_move_line.account_id
                         AND account_account_account_tag.account_account_tag_id IN %(tags)s
                    WHERE account_move_line.move_id IN (SELECT unnest(payment_move_ids.move_id) FROM payment_move_ids)
                        AND account_move_line.account_id NOT IN %(payment_accounts)s
                        AND account_partial_reconcile.max_date BETWEEN %(date_from)s AND %(date_to)s
                    GROUP BY account_move_line.company_id, account_move_line.account_id, account_account.code, account_name, account_account.account_type, account_account_account_tag.account_account_tag_id
    
                    UNION ALL
    
                    -- Total amount of each account
                    SELECT
                        %(column_group_key)s AS column_group_key,
                        account_move_line.account_id AS account_id,
                        account_account.code AS account_code,
                        %(account_name)s AS account_name,
                        account_account.account_type AS account_account_type,
                        account_account_account_tag.account_account_tag_id AS account_tag_id,
                        SUM(ROUND(account_move_line.balance_usd, currency_table.precision)) AS balance
                    FROM account_move_line
                    LEFT JOIN %(ct_query)s
                        ON currency_table.company_id = account_move_line.company_id
                    JOIN account_account
                        ON account_account.id = account_move_line.account_id
                    LEFT JOIN account_account_account_tag
                        ON account_account_account_tag.account_account_id = account_move_line.account_id
                         AND account_account_account_tag.account_account_tag_id IN %(tags)s
                    WHERE account_move_line.move_id IN (SELECT unnest(payment_move_ids.move_id) FROM payment_move_ids)
                        AND account_move_line.account_id NOT IN %(payment_accounts)s
                    GROUP BY account_move_line.account_id, account_account.code, account_name, account_account.account_type, account_account_account_tag.account_account_tag_id
                """,
                    move_ids=SQL(move_ids_subquery),
                    column_group_key=column_group_key,
                    account_name=SQL(account_name_str),
                    ct_query=currency_table_query,
                    tags=tuple(cash_flow_tag_ids) or (None,),
                    payment_accounts=payment_account_ids,
                    date_from=column_group_options['date']['date_from'],
                    date_to=column_group_options['date']['date_to']
                )
                queries.append(subquery)

        self._cr.execute(SQL(" UNION ALL ").join(queries))
        for aml_data in self._cr.dictfetchall():
            reconciled_aml_groupby_account.setdefault(aml_data['account_id'], {})
            reconciled_aml_groupby_account[aml_data['account_id']].setdefault(aml_data['column_group_key'], {
                'column_group_key': aml_data['column_group_key'],
                'account_id': aml_data['account_id'],
                'account_code': aml_data['account_code'],
                'account_name': aml_data['account_name'],
                'account_account_type': aml_data['account_account_type'],
                'account_tag_id': aml_data['account_tag_id'],
                'balance': 0.0,
            })
            reconciled_aml_groupby_account[aml_data['account_id']][aml_data['column_group_key']]['balance'] -= aml_data['balance']

        return list(reconciled_aml_groupby_account.values())

    def _get_reconciled_moves(self, report, options, currency_table_query, payment_account_ids, payment_move_ids, cash_flow_tag_ids):
        if not payment_move_ids:
            return []

        reconciled_account_ids = {column_group_key: set() for column_group_key in options['column_groups']}
        reconciled_percentage_per_move = {column_group_key: {} for column_group_key in options['column_groups']}
        queries = []
        currency_dif = options['currency_dif']
        
        for column_group_key, column_group_options in report._split_options_per_column_group(options).items():
            move_ids_subquery = self._get_move_ids_query(report, payment_account_ids, column_group_options)
            
            if currency_dif == self.env.company.currency_id.symbol:
                queries.append(SQL("""
                    SELECT
                        %(column_group_key)s AS column_group_key,
                        debit_line.move_id,
                        debit_line.account_id,
                        SUM(account_partial_reconcile.amount) AS balance
                    FROM account_move_line AS credit_line
                    LEFT JOIN account_partial_reconcile
                        ON account_partial_reconcile.credit_move_id = credit_line.id
                    INNER JOIN account_move_line AS debit_line
                        ON debit_line.id = account_partial_reconcile.debit_move_id
                    WITH payment_move_ids AS (%(move_ids)s)
                    WHERE credit_line.move_id IN (SELECT unnest(payment_move_ids.move_id) FROM payment_move_ids)
                        AND credit_line.account_id NOT IN %(payment_accounts)s
                        AND credit_line.credit > 0.0
                        AND debit_line.move_id NOT IN (SELECT unnest(payment_move_ids.move_id) FROM payment_move_ids)
                        AND account_partial_reconcile.max_date BETWEEN %(date_from)s AND %(date_to)s
                    GROUP BY debit_line.move_id, debit_line.account_id
    
                    UNION ALL
    
                    SELECT
                        %(column_group_key)s AS column_group_key,
                        credit_line.move_id,
                        credit_line.account_id,
                        -SUM(account_partial_reconcile.amount) AS balance
                    FROM account_move_line AS debit_line
                    LEFT JOIN account_partial_reconcile
                        ON account_partial_reconcile.debit_move_id = debit_line.id
                    INNER JOIN account_move_line AS credit_line
                        ON credit_line.id = account_partial_reconcile.credit_move_id
                    WITH payment_move_ids AS (%(move_ids)s)
                    WHERE debit_line.move_id IN (SELECT unnest(payment_move_ids.move_id) FROM payment_move_ids)
                        AND debit_line.account_id NOT IN %(payment_accounts)s
                        AND debit_line.debit > 0.0
                        AND credit_line.move_id NOT IN (SELECT unnest(payment_move_ids.move_id) FROM payment_move_ids)
                        AND account_partial_reconcile.max_date BETWEEN %(date_from)s AND %(date_to)s
                    GROUP BY credit_line.move_id, credit_line.account_id
                """,
                    column_group_key=column_group_key,
                    move_ids=SQL(move_ids_subquery),
                    payment_accounts=payment_account_ids,
                    date_from=column_group_options['date']['date_from'],
                    date_to=column_group_options['date']['date_to']
                ))
            else:
                queries.append(SQL("""
                    SELECT
                        %(column_group_key)s AS column_group_key,
                        debit_line.move_id,
                        debit_line.account_id,
                        SUM(account_partial_reconcile.amount_usd) AS balance
                    FROM account_move_line AS credit_line
                    LEFT JOIN account_partial_reconcile
                        ON account_partial_reconcile.credit_move_id = credit_line.id
                    INNER JOIN account_move_line AS debit_line
                        ON debit_line.id = account_partial_reconcile.debit_move_id
                    WITH payment_move_ids AS (%(move_ids)s)
                    WHERE credit_line.move_id IN (SELECT unnest(payment_move_ids.move_id) FROM payment_move_ids)
                        AND credit_line.account_id NOT IN %(payment_accounts)s
                        AND credit_line.credit_usd > 0.0
                        AND debit_line.move_id NOT IN (SELECT unnest(payment_move_ids.move_id) FROM payment_move_ids)
                        AND account_partial_reconcile.max_date BETWEEN %(date_from)s AND %(date_to)s
                    GROUP BY debit_line.move_id, debit_line.account_id
    
                    UNION ALL
    
                    SELECT
                        %(column_group_key)s AS column_group_key,
                        credit_line.move_id,
                        credit_line.account_id,
                        -SUM(account_partial_reconcile.amount_usd) AS balance
                    FROM account_move_line AS debit_line
                    LEFT JOIN account_partial_reconcile
                        ON account_partial_reconcile.debit_move_id = debit_line.id
                    INNER JOIN account_move_line AS credit_line
                        ON credit_line.id = account_partial_reconcile.credit_move_id
                    WITH payment_move_ids AS (%(move_ids)s)
                    WHERE debit_line.move_id IN (SELECT unnest(payment_move_ids.move_id) FROM payment_move_ids)
                        AND debit_line.account_id NOT IN %(payment_accounts)s
                        AND debit_line.debit_usd > 0.0
                        AND credit_line.move_id NOT IN (SELECT unnest(payment_move_ids.move_id) FROM payment_move_ids)
                        AND account_partial_reconcile.max_date BETWEEN %(date_from)s AND %(date_to)s
                    GROUP BY credit_line.move_id, credit_line.account_id
                """,
                    column_group_key=column_group_key,
                    move_ids=SQL(move_ids_subquery),
                    payment_accounts=payment_account_ids,
                    date_from=column_group_options['date']['date_from'],
                    date_to=column_group_options['date']['date_to']
                ))

        self._cr.execute(SQL(" UNION ALL ").join(queries)) if queries else None
        for aml_data in self._cr.dictfetchall():
            reconciled_percentage_per_move[aml_data['column_group_key']].setdefault(aml_data['move_id'], {})
            reconciled_percentage_per_move[aml_data['column_group_key']][aml_data['move_id']].setdefault(aml_data['account_id'], [0.0, 0.0])
            reconciled_percentage_per_move[aml_data['column_group_key']][aml_data['move_id']][aml_data['account_id']][0] += aml_data['balance']
            reconciled_account_ids[aml_data['column_group_key']].add(aml_data['account_id'])

        if not reconciled_percentage_per_move:
            return []

        # Second part: Fetch base balances
        queries = []
        for column in options['columns']:
            cgk = column['column_group_key']
            if currency_dif == self.env.company.currency_id.symbol:
                queries.append(SQL("""
                    SELECT
                        %(column_group_key)s AS column_group_key,
                        account_move_line.move_id,
                        account_move_line.account_id,
                        SUM(account_move_line.balance) AS balance
                    FROM account_move_line
                    JOIN %(ct_query)s
                        ON currency_table.company_id = account_move_line.company_id
                    WHERE account_move_line.move_id IN %(move_ids)s
                        AND account_move_line.account_id IN %(account_ids)s
                    GROUP BY account_move_line.move_id, account_move_line.account_id
                """,
                    column_group_key=cgk,
                    ct_query=currency_table_query,
                    move_ids=tuple(reconciled_percentage_per_move[cgk].keys()) or (None,),
                    account_ids=tuple(reconciled_account_ids[cgk]) or (None,)
                ))
            else:
                queries.append(SQL("""
                    SELECT
                        %(column_group_key)s AS column_group_key,
                        account_move_line.move_id,
                        account_move_line.account_id,
                        SUM(account_move_line.balance_usd) AS balance
                    FROM account_move_line
                    JOIN %(ct_query)s
                        ON currency_table.company_id = account_move_line.company_id
                    WHERE account_move_line.move_id IN %(move_ids)s
                        AND account_move_line.account_id IN %(account_ids)s
                    GROUP BY account_move_line.move_id, account_move_line.account_id
                """,
                    column_group_key=cgk,
                    ct_query=currency_table_query,
                    move_ids=tuple(reconciled_percentage_per_move[cgk].keys()) or (None,),
                    account_ids=tuple(reconciled_account_ids[cgk]) or (None,)
                ))

        self._cr.execute(SQL(" UNION ALL ").join(queries))
        for aml_data in self._cr.dictfetchall():
            if aml_data['account_id'] in reconciled_percentage_per_move[aml_data['column_group_key']][aml_data['move_id']]:
                reconciled_percentage_per_move[aml_data['column_group_key']][aml_data['move_id']][aml_data['account_id']][1] += aml_data['balance']

        # Third part: Final details
        reconciled_aml_per_account = {}
        queries = []
        if self.pool['account.account'].name.translate:
            lang = self.env.user.lang or get_lang(self.env).code
            account_name_str = f"COALESCE(account_account.name->>'{lang}', account_account.name->>'en_US')"
        else:
            account_name_str = 'account_account.name'

        for column in options['columns']:
            cgk = column['column_group_key']
            if currency_dif == self.env.company.currency_id.symbol:
                queries.append(SQL("""
                    SELECT
                        %(column_group_key)s AS column_group_key,
                        account_move_line.move_id,
                        account_move_line.account_id,
                        account_account.code AS account_code,
                        %(account_name)s AS account_name,
                        account_account.account_type AS account_account_type,
                        account_account_account_tag.account_account_tag_id AS account_tag_id,
                        SUM(ROUND(account_move_line.balance * currency_table.rate, currency_table.precision)) AS balance
                    FROM account_move_line
                    LEFT JOIN %(ct_query)s
                        ON currency_table.company_id = account_move_line.company_id
                    JOIN account_account
                        ON account_account.id = account_move_line.account_id
                    LEFT JOIN account_account_account_tag
                        ON account_account_account_tag.account_account_id = account_move_line.account_id
                        AND account_account_account_tag.account_account_tag_id IN %(tags)s
                    WHERE account_move_line.move_id IN %(move_ids)s
                    GROUP BY account_move_line.move_id, account_move_line.account_id, account_account.code, account_name, account_account.account_type, account_account_account_tag.account_tag_id
                """,
                    column_group_key=cgk,
                    account_name=SQL(account_name_str),
                    ct_query=currency_table_query,
                    tags=tuple(cash_flow_tag_ids) or (None,),
                    move_ids=tuple(reconciled_percentage_per_move[cgk].keys()) or (None,)
                ))
            else:
                queries.append(SQL("""
                    SELECT
                        %(column_group_key)s AS column_group_key,
                        account_move_line.move_id,
                        account_move_line.account_id,
                        account_account.code AS account_code,
                        %(account_name)s AS account_name,
                        account_account.account_type AS account_account_type,
                        account_account_account_tag.account_account_tag_id AS account_tag_id,
                        SUM(ROUND(account_move_line.balance_usd, currency_table.precision)) AS balance
                    FROM account_move_line
                    LEFT JOIN %(ct_query)s
                        ON currency_table.company_id = account_move_line.company_id
                    JOIN account_account
                        ON account_account.id = account_move_line.account_id
                    LEFT JOIN account_account_account_tag
                        ON account_account_account_tag.account_account_id = account_move_line.account_id
                        AND account_account_account_tag.account_account_tag_id IN %(tags)s
                    WHERE account_move_line.move_id IN %(move_ids)s
                    GROUP BY account_move_line.move_id, account_move_line.account_id, account_account.code, account_name, account_account.account_type, account_account_account_tag.account_tag_id
                """,
                    column_group_key=cgk,
                    account_name=SQL(account_name_str),
                    ct_query=currency_table_query,
                    tags=tuple(cash_flow_tag_ids) or (None,),
                    move_ids=tuple(reconciled_percentage_per_move[cgk].keys()) or (None,)
                ))

        self._cr.execute(SQL(" UNION ALL ").join(queries))
        for aml_data in self._cr.dictfetchall():
            cgk = aml_data['column_group_key']
            move_id = aml_data['move_id']
            acc_id = aml_data['account_id']
            
            total_reconciled_amount = 0.0
            total_amount = 0.0
            for r_amt, amt in reconciled_percentage_per_move[cgk][move_id].values():
                total_reconciled_amount += r_amt
                total_amount += amt

            aml_balance = aml_data['balance']
            if total_amount and acc_id not in reconciled_percentage_per_move[cgk][move_id]:
                aml_balance *= (total_reconciled_amount / total_amount)
            elif not total_amount and acc_id in reconciled_percentage_per_move[cgk][move_id]:
                aml_balance = -reconciled_percentage_per_move[cgk][move_id][acc_id][0]
            else:
                continue

            reconciled_aml_per_account.setdefault(acc_id, {})
            reconciled_aml_per_account[acc_id].setdefault(cgk, {
                'column_group_key': cgk,
                'account_id': acc_id,
                'account_code': aml_data['account_code'],
                'account_name': aml_data['account_name'],
                'account_account_type': aml_data['account_account_type'],
                'account_tag_id': aml_data['account_tag_id'],
                'balance': 0.0,
            })
            reconciled_aml_per_account[acc_id][cgk]['balance'] -= aml_balance

        return list(reconciled_aml_per_account.values())