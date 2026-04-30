from itemadapter import ItemAdapter
from pymongo import MongoClient
from urllib.parse import urlparse

class AlkostoPipeline:
    def open_spider(self, spider):
        # Conexión a Atlas
        uri = spider.settings.get('MONGO_URI')
        self.client = MongoClient(uri)
        self.db = self.client[spider.name]
        self.stats = {'insertados': 0, 'actualizados': 0, 'fallidos': 0}
        spider.logger.info(f"Conexión abierta con MongoDB Atlas; DB: {spider.name}")

    def close_spider(self, spider):
        self.client.close()
        spider.logger.info(f"Mongo resumen: {self.stats}")

    def process_item(self, item, spider):
        try:
            linea = ItemAdapter(item).asdict()
            
            # Normalización del enlace con p.query (TU SOLUCIÓN)
            url_original = linea.get('enlace', '')
            p = urlparse(url_original)
            enlace_clean = f"{p.scheme}://{p.netloc}{p.path}"
            if p.query:
                enlace_clean += f"?{p.query}"
            
            linea['enlace_normalized'] = enlace_clean
            
            # Colección por categoría
            col_name = linea.get('categoria', 'otros')
            coleccion = self.db[col_name]

            # Upsert para evitar duplicados y actualizar precios
            result = coleccion.update_one(
                {'enlace_normalized': enlace_clean},
                {'$set': linea},
                upsert=True
            )

            if result.upserted_id:
                self.stats['insertados'] += 1
            else:
                self.stats['actualizados'] += 1

        except Exception as e:
            spider.logger.error(f"Error en Pipeline: {e}")
            self.stats['fallidos'] += 1
            
        return item