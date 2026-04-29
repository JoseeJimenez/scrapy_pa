from itemadapter import ItemAdapter
from pymongo import MongoClient
from urllib.parse import urlparse
import os

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

        col_name = linea.get('categoria', 'otros')
        coleccion = self.db[col_name]

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