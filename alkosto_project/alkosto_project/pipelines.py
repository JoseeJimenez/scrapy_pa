from itemadapter import ItemAdapter
from pymongo import MongoClient
from urllib.parse import urlparse
import os
<<<<<<< HEAD
=======
import re

# Mapeo por defecto de spiders a bases de datos. Añadir nuevos spiders aquí.
SPIDER_DB_MAP = {
    'alkosto': 'alkosto',
    'exito': 'exito',
    'compulago': 'compulago',
    'compuworking': 'computerworking',
}


def get_database_name_for_spider(spider):
    """Devuelve el nombre de la base de datos para el spider dado.

    Prioridad:
    1. Variable de entorno `MONGO_DATABASE` si está definida y no es 'AUTO'.
    2. `SPIDER_DB_MAP` mapeo por nombre de spider.
    3. Nombre del spider sanitizado (caracteres no alfanuméricos -> '_').
    """
    # 1) override desde settings del spider (recomendado)
    try:
        s_db = spider.settings.get('MONGO_DATABASE')
    except Exception:
        s_db = None
    if s_db and str(s_db).strip() and str(s_db).strip().lower() != 'auto':
        return str(s_db).strip()

    # 2) override desde variable de entorno
    env_db = os.environ.get('MONGO_DATABASE')
    if env_db and env_db.strip() and env_db.strip().lower() != 'auto':
        return env_db.strip()

    name = spider.name if hasattr(spider, 'name') else str(spider)
    if name in SPIDER_DB_MAP:
        return SPIDER_DB_MAP[name]

    # fallback: usar el nombre del spider sanitizado
    return re.sub(r'[^0-9a-zA-Z_]', '_', name)
>>>>>>> 7530ab414e4288a0e710d8bb4f94c83723ec9f95

class AlkostoPipeline:
    def open_spider(self, spider):
        # Asegúrate de tener tu MONGO_URI en settings o como variable de entorno
        uri = spider.settings.get('MONGO_URI') or "tu_mongodb_uri_aqui"
        self.client = MongoClient(uri)
        self.db = self.client[spider.name]
        self.stats = {'insertados': 0, 'actualizados': 0}
        spider.logger.info(f"Conectado a MongoDB: {spider.name}")

    def close_spider(self, spider):
        self.client.close()
        spider.logger.info(f"Mongo Resumen: {self.stats}")

    def process_item(self, item, spider):
        linea = ItemAdapter(item).asdict()
        url_original = linea.get('enlace', '')
        
        # --- TU SOLUCIÓN DE NORMALIZACIÓN ---
        p = urlparse(url_original)
        enlace_clean = f"{p.scheme}://{p.netloc}{p.path}"
        if p.query:
            enlace_clean += f"?{p.query}"
        
        linea['enlace_normalized'] = enlace_clean
        # ------------------------------------

<<<<<<< HEAD
        col_name = linea.get('categoria', 'otros')
        coleccion = self.db[col_name]
=======
            # Normalizar enlace: quitar query y fragmento para evitar upserts duplicados
            enlace_normalized = None
            if enlace:
                try:
                    p = urlparse(enlace)
                    enlace_normalized = f"{p.scheme}://{p.netloc}{p.path}?{p.query}"
                    linea['enlace_normalized'] = enlace_normalized
                except Exception:
                    enlace_normalized = enlace
>>>>>>> 7530ab414e4288a0e710d8bb4f94c83723ec9f95

        # Upsert para no duplicar y mantener datos frescos
        result = coleccion.update_one(
            {'enlace_normalized': enlace_clean},
            {'$set': linea},
            upsert=True
        )

        if result.upserted_id:
            self.stats['insertados'] += 1
        else:
            self.stats['actualizados'] += 1
            
        return item