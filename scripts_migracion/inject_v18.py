import json
import xmlrpc.client
import ssl
import logging

# Config
SRC_DATA = '/tmp/v16_audit_full.json'
DST_URL = 'https://tbriceno65-animalc.odoo.com'
DST_DB = 'tbriceno65-animalc-produccion-29159705'
DST_USER = 'migration_api'
DST_PASS = 'migration_password_123'

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('injection_v18')

class InjectionV18:
    def __init__(self):
        self.ctx = ssl._create_unverified_context()
        self.common = xmlrpc.client.ServerProxy(f'{DST_URL}/xmlrpc/2/common', context=self.ctx)
        self.uid = self.common.authenticate(DST_DB, DST_USER, DST_PASS, {})
        self.models = xmlrpc.client.ServerProxy(f'{DST_URL}/xmlrpc/2/object', context=self.ctx)
        
        self.company_cache = {}
        self.account_cache = {}
        
        with open(SRC_DATA, 'r') as f:
            self.data = json.load(f)
            
    def get_company_id(self, name):
        if not name: return False
        if name in self.company_cache: return self.company_cache[name]
        
        ids = self.models.execute_kw(DST_DB, self.uid, DST_PASS, 'res.company', 'search', [[['name', '=', name]]])
        res = ids[0] if ids else False
        self.company_cache[name] = res
        return res

    def get_account_id(self, code, company_id):
        if not code or not company_id: return False
        key = (code, company_id)
        if key in self.account_cache: return self.account_cache[key]
        
        # In Odoo 18, searching on many2many company_ids
        ids = self.models.execute_kw(DST_DB, self.uid, DST_PASS, 'account.account', 'search', [[['code', '=', code], ['company_ids', 'in', [company_id]]]])
        res = ids[0] if ids else False
        self.account_cache[key] = res
        return res

    def get_journal_id(self, code, company_id):
        ids = self.models.execute_kw(DST_DB, self.uid, DST_PASS, 'account.journal', 'search', [[['code', '=', code], ['company_id', '=', company_id]]])
        return ids[0] if ids else False

    def migrate_users(self):
        logger.info("Migrating Users...")
        # Get all dst companies for multi-company assignation
        all_companies = self.models.execute_kw(DST_DB, self.uid, DST_PASS, 'res.company', 'search', [[]])
        
        for u in self.data.get('users', []):
            if u['login'] in ['admin', 'migration_api']: continue
            
            existing = self.models.execute_kw(DST_DB, self.uid, DST_PASS, 'res.users', 'search', [[['login', '=', u['login']]]])
            if existing:
                # Update company access just in case
                self.models.execute_kw(DST_DB, self.uid, DST_PASS, 'res.users', 'write', [existing, {'company_ids': [([6, 0, all_companies])]}] )
                logger.info(f"User {u['login']} updated with multi-company access.")
                continue
            
            company_name = u['company_id'][1] if isinstance(u['company_id'], list) else u['company_id']
            company_id = self.get_company_id(company_name)
            if not company_id: company_id = 1
            
            vals = {
                'name': u['name'],
                'login': u['login'],
                'email': u['login'] if '@' in u['login'] else f"{u['login']}@example.com",
                'company_id': company_id,
                'company_ids': [([6, 0, all_companies])],
                'password': 'MigrationTemp123!' 
            }
            try:
                new_uid = self.models.execute_kw(DST_DB, self.uid, DST_PASS, 'res.users', 'create', [vals])
                logger.info(f"Created User: {u['login']} (UID: {new_uid})")
            except Exception as e:
                logger.error(f"Error creating user {u['login']}: {e}")

    def migrate_accounts(self):
        logger.info("Migrating Accounts...")
        for acc in self.data.get('accounts', []):
            company_name = acc['company_id'][1] if isinstance(acc['company_id'], list) else acc['company_id']
            company_id = self.get_company_id(company_name)
            if not company_id: continue
            
            existing = self.get_account_id(acc['code'], company_id)
            if existing: continue
            
            vals = {
                'code': acc['code'],
                'name': acc['name'],
                'account_type': acc['account_type'],
                'reconcile': acc['reconcile'],
                'company_ids': [([6, 0, [company_id]])]
            }
            try:
                self.models.execute_kw(DST_DB, self.uid, DST_PASS, 'account.account', 'create', [vals])
                logger.info(f"Created Account: {acc['code']} for company {company_name}")
            except Exception as e:
                logger.error(f"Error creating account {acc['code']}: {e}")

    def migrate_warehouses(self):
        logger.info("Migrating Warehouses...")
        for wh in self.data.get('warehouses', []):
            company_id = self.get_company_id(wh['company_id'][1])
            if not company_id: continue
            
            existing = self.models.execute_kw(DST_DB, self.uid, DST_PASS, 'stock.warehouse', 'search', [[['code', '=', wh['code']], ['company_id', '=', company_id]]])
            if not existing:
                vals = {
                    'name': wh['name'],
                    'code': wh['code'],
                    'company_id': company_id
                }
                self.models.execute_kw(DST_DB, self.uid, DST_PASS, 'stock.warehouse', 'create', [vals])
                logger.info(f"Created Warehouse: {wh['name']}")

    def migrate_fiscal_printers(self):
        logger.info("Migrating Fiscal Printers...")
        for fp in self.data.get('fiscal_printers', []):
            # Check if model exists
            try:
                self.models.execute_kw(DST_DB, self.uid, DST_PASS, 'x.pos.fiscal.printer', 'search', [[]], {'limit':1})
            except:
                logger.error("Model x.pos.fiscal.printer NOT found in DST. Skipping.")
                return
            
            existing = self.models.execute_kw(DST_DB, self.uid, DST_PASS, 'x.pos.fiscal.printer', 'search', [[['serial', '=', fp['serial']]]])
            if not existing:
                vals = {
                    'name': fp['name'],
                    'serial': fp['serial'],
                    'connection_type': fp['connection_type'],
                    'serial_port': fp['serial_port'],
                }
                # Attempt to get company_id if possible (defaulting to 1 for now if not in audit)
                vals['company_id'] = 1 
                
                try:
                    self.models.execute_kw(DST_DB, self.uid, DST_PASS, 'x.pos.fiscal.printer', 'create', [vals])
                    logger.info(f"Created Fiscal Printer: {fp['name']}")
                except Exception as e:
                    logger.error(f"Error creating printer {fp['name']}: {e}")

    def migrate_journals(self):
        logger.info("Migrating Journals...")
        for j in self.data.get('journals', []):
            company_name = j['company_id'][1] if isinstance(j['company_id'], list) else j['company_id']
            company_id = self.get_company_id(company_name)
            if not company_id: continue
            
            existing = self.get_journal_id(j['code'], company_id)
            if existing: continue
            
            vals = {
                'name': j['name'],
                'code': j['code'],
                'type': j['type'],
                'company_id': company_id
            }
            # Handle account
            if j.get('default_account_id'):
                acc_code = j['default_account_id'][1].split(' ')[0] # Heuristic attempt
                acc_id = self.get_account_id(acc_code, company_id)
                if acc_id:
                    vals['default_account_id'] = acc_id
            
            try:
                self.models.execute_kw(DST_DB, self.uid, DST_PASS, 'account.journal', 'create', [vals])
                logger.info(f"Created Journal: {j['code']} for company {company_name}")
            except Exception as e:
                logger.error(f"Error creating journal {j['code']}: {e}")

    def migrate_pos_payment_methods(self):
        logger.info("Migrating POS Payment Methods...")
        for pm in self.data.get('payment_methods', []):
            company_name = pm['company_id'][1] if isinstance(pm['company_id'], list) else pm['company_id']
            company_id = self.get_company_id(company_name)
            if not company_id: continue
            
            # Use localized name
            name = pm['name'].get('es_VE') or pm['name'].get('en_US') if isinstance(pm['name'], dict) else pm['name']
            
            # Small Victory Logic: If it is a CASH payment method, ensure a unique journal or check existing
            existing = self.models.execute_kw(DST_DB, self.uid, DST_PASS, 'pos.payment.method', 'search', [[['name', '=', name], ['company_id', '=', company_id]]])
            if existing: continue
            
            vals = {
                'name': name,
                'company_id': company_id
            }
            if pm.get('journal_id'):
                src_j_name = pm['journal_id'][1]
                j_id = False
                
                # Check journal type
                src_j_data = next((j for j in self.data.get('journals', []) if j['name'] == src_j_name), None)
                if src_j_data and src_j_data['type'] == 'cash':
                    # Create a UNIQUE cash journal for this specific payment method if needed
                    # Odoo 18 requirement: One cash journal per cash payment method
                    new_j_name = f"{src_j_name} - {name}"
                    new_j_code = f"CSH{str(company_id)}{name[:2].upper()}"[:5]
                    
                    # Search if we already created it
                    j_ids = self.models.execute_kw(DST_DB, self.uid, DST_PASS, 'account.journal', 'search', [[['name', '=', new_j_name], ['company_id', '=', company_id]]])
                    if not j_ids:
                        j_vals = {
                            'name': new_j_name,
                            'code': new_j_code,
                            'type': 'cash',
                            'company_id': company_id
                        }
                        j_id = self.models.execute_kw(DST_DB, self.uid, DST_PASS, 'account.journal', 'create', [j_vals])
                        logger.info(f"Created Unique Cash Journal: {new_j_name}")
                    else:
                        j_id = j_ids[0]
                else:
                    # Normal search by name
                    j_ids = self.models.execute_kw(DST_DB, self.uid, DST_PASS, 'account.journal', 'search', [[['name', '=', src_j_name], ['company_id', '=', company_id]]])
                    j_id = j_ids[0] if j_ids else False
                    
                if j_id:
                    vals['journal_id'] = j_id
            
            try:
                self.models.execute_kw(DST_DB, self.uid, DST_PASS, 'pos.payment.method', 'create', [vals])
                logger.info(f"Created Payment Method: {name} for company {company_name}")
            except Exception as e:
                logger.error(f"Error creating payment method {name}: {e}")

    def migrate_pos_configs(self):
        logger.info("Migrating POS Configs...")
        for cfg in self.data.get('pos_configs', []):
            company_name = cfg['company_id'][1] if isinstance(cfg['company_id'], list) else cfg['company_id']
            company_id = self.get_company_id(company_name)
            if not company_id: continue
            
            existing = self.models.execute_kw(DST_DB, self.uid, DST_PASS, 'pos.config', 'search', [[['name', '=', cfg['name']], ['company_id', '=', company_id]]])
            if existing: continue
            
            vals = {
                'name': cfg['name'],
                'company_id': company_id
            }

            # Map Journals
            src_j_name = cfg['journal_id'][1] if cfg.get('journal_id') else False
            if src_j_name:
                j_ids = self.models.execute_kw(DST_DB, self.uid, DST_PASS, 'account.journal', 'search', [[['name', '=', src_j_name], ['company_id', '=', company_id]]])
                if j_ids:
                    vals['journal_id'] = j_ids[0]
                else:
                    # Fallback to search any 'type'='sale' journal for this company
                    j_ids = self.models.execute_kw(DST_DB, self.uid, DST_PASS, 'account.journal', 'search', [[['type', '=', 'sale'], ['company_id', '=', company_id]]])
                    if j_ids: vals['journal_id'] = j_ids[0]

            src_inv_j_name = cfg['invoice_journal_id'][1] if cfg.get('invoice_journal_id') else False
            if src_inv_j_name:
                inv_j_ids = self.models.execute_kw(DST_DB, self.uid, DST_PASS, 'account.journal', 'search', [[['name', '=', src_inv_j_name], ['company_id', '=', company_id]]])
                if inv_j_ids:
                    vals['invoice_journal_id'] = inv_j_ids[0]
                else:
                    # Fallback
                    inv_j_ids = self.models.execute_kw(DST_DB, self.uid, DST_PASS, 'account.journal', 'search', [[['type', '=', 'sale'], ['company_id', '=', company_id]]])
                    if inv_j_ids: vals['invoice_journal_id'] = inv_j_ids[0]
            
            # Map payment methods
            pm_ids = []
            for src_pm in cfg.get('payment_method_ids', []):
                pm_name = src_pm[1].get('es_VE') or src_pm[1].get('en_US') if isinstance(src_pm[1], dict) else src_pm[1]
                dst_pm = self.models.execute_kw(DST_DB, self.uid, DST_PASS, 'pos.payment.method', 'search', [[['name', '=', pm_name], ['company_id', '=', company_id]]])
                if dst_pm:
                    pm_ids.append(dst_pm[0])
            
            if pm_ids:
                vals['payment_method_ids'] = [[6, 0, pm_ids]]
                
            try:
                self.models.execute_kw(DST_DB, self.uid, DST_PASS, 'pos.config', 'create', [vals])
                logger.info(f"Created POS Config: {cfg['name']}")
            except Exception as e:
                logger.error(f"Error creating POS Config {cfg['name']}: {e}")

    def run(self):
        self.migrate_users()
        self.migrate_accounts()
        self.migrate_warehouses()
        self.migrate_journals()
        self.migrate_pos_payment_methods()
        self.migrate_pos_configs()
        self.migrate_fiscal_printers()

if __name__ == "__main__":
    injector = InjectionV18()
    injector.run()
