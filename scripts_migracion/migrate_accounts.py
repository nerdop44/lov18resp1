import xmlrpc.client
import logging
import ssl
import time

# Configure Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class AccountMigrator:
    def __init__(self):
        # Source (v16)
        self.src_url = 'http://148.113.183.253:8069'
        self.src_db = 'kantal.mi-erp.app'
        self.src_user = 'migration_api'
        self.src_pass = 'migration_password_123'
        
        # Destination (v18)
        self.dst_url = 'https://tbriceno65-animalc.odoo.com'
        self.dst_db = 'tbriceno65-animalc-produccion-29159705'
        self.dst_user = 'migration_api'
        self.dst_pass = 'migration_password_123'
        
        self.ctx = ssl._create_unverified_context()
        self.connect()

    def connect(self):
        self.src_common = xmlrpc.client.ServerProxy(f'{self.src_url}/xmlrpc/2/common', context=self.ctx, allow_none=True)
        self.src_uid = self.src_common.authenticate(self.src_db, self.src_user, self.src_pass, {})
        self.src_models = xmlrpc.client.ServerProxy(f'{self.src_url}/xmlrpc/2/object', context=self.ctx, allow_none=True)
        
        self.dst_common = xmlrpc.client.ServerProxy(f'{self.dst_url}/xmlrpc/2/common', context=self.ctx, allow_none=True)
        self.dst_uid = self.dst_common.authenticate(self.dst_db, self.dst_user, self.dst_pass, {})
        self.dst_models = xmlrpc.client.ServerProxy(f'{self.dst_url}/xmlrpc/2/object', context=self.ctx, allow_none=True)
        
        logger.info("Connected to both instances.")

    def migrate_accounts(self):
        logger.info("Fetching accounts from v16...")
        src_accounts = []
        offset = 0
        limit = 500
        while True:
            batch = self.src_models.execute_kw(self.src_db, self.src_uid, self.src_pass, 'account.account', 'search_read', [[]], {'fields': ['code', 'name', 'account_type', 'reconcile', 'currency_id', 'company_id'], 'offset': offset, 'limit': limit})
            if not batch:
                break
            src_accounts.extend(batch)
            offset += limit
            logger.info(f"Fetched {len(src_accounts)} accounts from SRC...")
        
        logger.info("Fetching accounts from v18 to avoid duplicates...")
        dst_accounts = []
        offset = 0
        while True:
            batch = self.dst_models.execute_kw(self.dst_db, self.dst_uid, self.dst_pass, 'account.account', 'search_read', [[]], {'fields': ['code', 'company_ids'], 'offset': offset, 'limit': limit})
            if not batch:
                break
            dst_accounts.extend(batch)
            offset += limit
            logger.info(f"Fetched {len(dst_accounts)} accounts from DST...")
        
        # Mapping: (code, company_id) -> id
        # Since company_ids is a list, we iterate through it
        dst_map = {}
        for a in dst_accounts:
            for c_id in a['company_ids']:
                dst_map[(a['code'], c_id)] = a['id']
        
        total = 0
        to_create = []
        
        for a in src_accounts:
            src_company_id = a['company_id'][0] if isinstance(a['company_id'], list) else False
            if not src_company_id: continue
            
            if (a['code'], src_company_id) not in dst_map:
                to_create.append({
                    'code': a['code'],
                    'name': a['name'],
                    'account_type': a['account_type'],
                    'reconcile': a.get('reconcile', False),
                    'company_ids': [([6, 0, [src_company_id]])]
                })
        
        logger.info(f"Preparing to create {len(to_create)} accounts...")
        
        batch_size = 50
        for i in range(0, len(to_create), batch_size):
            batch = to_create[i:i+batch_size]
            try:
                self.dst_models.execute_kw(self.dst_db, self.dst_uid, self.dst_pass, 'account.account', 'create', [batch])
                total += len(batch)
                logger.info(f"Created {total}/{len(to_create)} accounts.")
            except Exception as e:
                logger.error(f"Error creating batch starting at {i}: {e}")
                # Fallback to single create
                for item in batch:
                    try:
                        self.dst_models.execute_kw(self.dst_db, self.dst_uid, self.dst_pass, 'account.account', 'create', [item])
                        total += 1
                    except: pass

        logger.info(f"Migration Finished. Total accounts created: {total}")

if __name__ == "__main__":
    migrator = AccountMigrator()
    migrator.migrate_accounts()
