
import xmlrpc.client
import logging

# Configuración de Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class PriceRestorer:
    def __init__(self):
        # Origen (v16) - Datos obtenidos del migrador previo
        self.src_url = 'http://148.113.183.253:8069'
        self.src_db = 'kantal.mi-erp.app'
        self.src_user = 'migration_api'
        self.src_pass = 'migration_password_123'
        
        # Destino (v18)
        self.dst_url = 'https://tbriceno65-animalc.odoo.com'
        self.dst_db = 'tbriceno65-animalc-produccion-29159705'
        self.dst_user = 'migration_api'
        self.dst_pass = 'migration_password_123'
        
        self.src_models = None
        self.dst_models = None
        self.src_uid = None
        self.dst_uid = None

    def connect(self):
        import ssl
        ctx = ssl._create_unverified_context()
        try:
            logger.info("Conectando al ORIGEN (v16)...")
            common_src = xmlrpc.client.ServerProxy(f'{self.src_url}/xmlrpc/2/common', context=ctx)
            self.src_uid = common_src.authenticate(self.src_db, self.src_user, self.src_pass, {})
            self.src_models = xmlrpc.client.ServerProxy(f'{self.src_url}/xmlrpc/2/object', context=ctx)
            logger.info(f"Conectado al Origen. UID: {self.src_uid}")
            
            logger.info("Conectando al DESTINO (v18)...")
            common_dst = xmlrpc.client.ServerProxy(f'{self.dst_url}/xmlrpc/2/common', context=ctx)
            self.dst_uid = common_dst.authenticate(self.dst_db, self.dst_user, self.dst_pass, {})
            self.dst_models = xmlrpc.client.ServerProxy(f'{self.dst_url}/xmlrpc/2/object', context=ctx)
            logger.info(f"Conectado al Destino. UID: {self.dst_uid}")
            return True
        except Exception as e:
            logger.error(f"Error de conexión: {e}")
            return False

    def run_restoration(self):
        logger.info("Iniciando restauración de precios...")
        
        # 1. Obtener todos los productos del destino (v18) que tienen precios astronómicos (> 1M por ejemplo)
        # O simplemente procesar todos los productos para asegurar consistencia.
        # Filtramos por aquellos que tienen código de barras o referencia interna para hacer el match.
        
        offset = 0
        limit = 500
        total_migrated = 0
        
        while True:
            logger.info(f"Procesando lote de productos v18 (offset {offset})...")
            dst_products = self.dst_models.execute_kw(self.dst_db, self.dst_uid, self.dst_pass,
                'product.template', 'search_read',
                [[('active', '=', True)]],
                {'fields': ['id', 'name', 'default_code', 'barcode', 'list_price'], 'offset': offset, 'limit': limit}
            )
            
            if not dst_products:
                break
                
            for p_v18 in dst_products:
                match_id_v16 = None
                domain_v16 = []
                
                if p_v18['default_code']:
                    domain_v16 = [('default_code', '=', p_v18['default_code'])]
                elif p_v18['barcode']:
                    domain_v16 = [('barcode', '=', p_v18['barcode'])]
                else:
                    # Si no hay código, intentamos por nombre exacto (riesgoso pero necesario en algunos casos)
                    domain_v16 = [('name', '=', p_v18['name'])]
                
                if domain_v16:
                    src_records = self.src_models.execute_kw(self.src_db, self.src_uid, self.src_pass,
                        'product.template', 'search_read',
                        [domain_v16],
                        {'fields': ['list_price_usd'], 'limit': 1}
                    )
                    
                    if src_records:
                        price_v16 = src_records[0]['list_price_usd']
                        # Actualizar en v18
                        if abs(p_v18['list_price'] - price_v16) > 0.01:
                            logger.info(f"Actualizando {p_v18['name']} ({p_v18['default_code']}): {p_v18['list_price']} -> {price_v16}")
                            self.dst_models.execute_kw(self.dst_db, self.dst_uid, self.dst_pass,
                                'product.template', 'write',
                                [[p_v18['id']], {'list_price': price_v16}]
                            )
                            total_migrated += 1
            
            offset += limit
            
        logger.info(f"Restauración completada. Total productos actualizados: {total_migrated}")

if __name__ == "__main__":
    restorer = PriceRestorer()
    if restorer.connect():
        restorer.run_restoration()
