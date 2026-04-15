from itemadapter import ItemAdapter
from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError
from urllib.parse import urlparse
import os
import re

# Mapeo por defecto de spiders a bases de datos. Añadir nuevos spiders aquí.
SPIDER_DB_MAP = {
    'alkosto': 'alkosto',
    'exito': 'exito',
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

class AlkostoPipeline:
    
    load_dotenv() 

    def open_spider(self, spider):
        # Conexión a tu clúster de MongoDB Atlas
        uri = spider.settings.get('MONGO_URI') or os.environ.get('MONGO_URI')
        if not uri:
            spider.logger.error('MONGO_URI no está configurado en settings o en variables de entorno')
            raise RuntimeError('MONGO_URI no configurado')
        # configurar un timeout razonable para selección de servidor y verificar conexión
        try:
            self.client = MongoClient(uri, serverSelectionTimeoutMS=20000)
            # ping para forzar la selección de servidor y detectar problemas temprano
            self.client.admin.command('ping')
            # determinar y guardar la DB por defecto para este spider (para diagnóstico)
            self.default_db_name = get_database_name_for_spider(spider)
            spider.logger.info('Conexión abierta con MongoDB Atlas; DB por defecto: %s', self.default_db_name)
            # contador para limitar logs de diagnóstico
            self._items_logged = 0
            # contadores de operaciones
            self._inserted = 0
            self._updated = 0
            self._failed = 0
            # colecciones indexadas para evitar recrear índices
            self._indexed_collections = set()
            # colecciones indexadas para evitar recrear índices
            self._indexed_collections = set()
        except Exception:
            spider.logger.exception('No fue posible conectar a MongoDB Atlas usando la URI proporcionada')
            raise

    def close_spider(self, spider):
        self.client.close()
        spider.logger.info("Conexión con MongoDB Atlas cerrada")
        # resumen de operaciones en esta ejecución
        try:
            spider.logger.info('Mongo resumen: insertados=%d, actualizados=%d, fallidos=%d', self._inserted, self._updated, self._failed)
        except Exception:
            pass

    def process_item(self, item, spider):
        linea = ItemAdapter(item).asdict()
        try:
            enlace = linea.get('enlace')
            # Determinar la base de datos usando la función helper
            db_name = get_database_name_for_spider(spider)
            db = self.client[db_name]
            coleccion_name = linea.get('categoria') or 'sin_categoria'
            coleccion = db[coleccion_name]

            # Normalizar enlace: quitar query y fragmento para evitar upserts duplicados
            enlace_normalized = None
            if enlace:
                try:
                    p = urlparse(enlace)
                    enlace_normalized = f"{p.scheme}://{p.netloc}{p.path}"
                    linea['enlace_normalized'] = enlace_normalized
                except Exception:
                    enlace_normalized = enlace

            # usar enlace_normalized como identificador preferido; si no existe, usar nombre
            if enlace_normalized:
                filtro = {'enlace_normalized': enlace_normalized}
            else:
                filtro = {'nombre': linea.get('nombre')}

            # Logueo de diagnóstico limitado para entender si el filtro es el mismo repetidamente
            if getattr(self, '_items_logged', 0) < 10:
                spider.logger.info('DB=%s | Colección=%s | Filtro=%s | Nombre=%s', db_name, coleccion_name, {k: (v[:80] + '...' if isinstance(v, str) and len(v) > 80 else v) for k, v in filtro.items()}, linea.get('nombre'))
                self._items_logged += 1

            # crear índice único en enlace_normalized para evitar duplicados, la primera vez por colección
            try:
                if coleccion_name not in self._indexed_collections:
                    # solo crear el índice si usamos enlace_normalized como campo
                    if 'enlace_normalized' in linea:
                        try:
                            coleccion.create_index([('enlace_normalized', 1)], unique=True, sparse=True)
                        except Exception:
                            # índice pudo existir o no haberse creado, continuar
                            pass
                    else:
                        try:
                            coleccion.create_index([('nombre', 1)], unique=False)
                        except Exception:
                            pass
                    self._indexed_collections.add(coleccion_name)
            except Exception:
                spider.logger.debug('No se pudo crear índice para %s/%s (continuando)', db_name, coleccion_name)

            # Si tenemos enlace_normalized, hacemos upsert por ese campo
            try:
                if enlace_normalized:
                    result = coleccion.update_one(
                        filtro,
                        {'$set': linea},
                        upsert=True
                    )
                    if getattr(result, 'upserted_id', None):
                        self._inserted += 1
                    else:
                        self._updated += 1
                else:
                    # si no hay enlace, insertamos un nuevo documento para no sobrescribir por nombre
                    try:
                        coleccion.insert_one(linea)
                        self._inserted += 1
                    except DuplicateKeyError:
                        # si por alguna razón existe la clave única, actualizamos
                        coleccion.update_one(filtro, {'$set': linea}, upsert=True)
                        self._updated += 1
            except Exception as e:
                self._failed += 1
                spider.logger.exception('Fallo insert/update en MongoDB para filtro=%s: %s', filtro, e)
                return item

            # Log de resultado limitado para diagnóstico
            if getattr(self, '_items_logged', 0) < 20:
                spider.logger.info('Mongo: DB=%s | Colección=%s | Filtro=%s', db_name, coleccion_name, filtro)
                self._items_logged += 1
        except Exception:
            spider.logger.exception('Error al procesar item y guardarlo en MongoDB')
        return item