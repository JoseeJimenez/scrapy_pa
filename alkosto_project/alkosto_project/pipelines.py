import re
from itemadapter import ItemAdapter
from pymongo import MongoClient, ASCENDING
from urllib.parse import urlparse


class AlkostoPipeline:
    def open_spider(self, spider):
        uri = spider.settings.get('MONGO_URI')
        self.client = MongoClient(uri)
        self.db = self.client[spider.name]
        self.stats = {'insertados': 0, 'actualizados': 0, 'movidos': 0, 'fallidos': 0}

        # Cache de product_ids en memoria: {product_id: col_name}
        # Se construye UNA sola vez al arrancar el spider
        self._cache = {}
        for col_name in self.db.list_collection_names():
            # Crear índice si no existe
            self.db[col_name].create_index([('product_id', ASCENDING)])
            for doc in self.db[col_name].find({}, {'product_id': 1, '_id': 0}):
                pid = doc.get('product_id')
                if pid:
                    self._cache[pid] = col_name

        spider.logger.info(
            f"Conexión abierta con MongoDB Atlas; DB: {spider.name} | "
            f"Cache: {len(self._cache)} productos existentes"
        )

    def close_spider(self, spider):
        self.client.close()
        spider.logger.info(f"Mongo resumen: {self.stats}")

    def process_item(self, item, spider):
        try:
            linea = ItemAdapter(item).asdict()

            # ── Normalización del enlace ──────────────────────────────────
            url_original = linea.get('enlace', '')
            p = urlparse(url_original)
            enlace_clean = f"{p.scheme}://{p.netloc}{p.path}"
            if p.query:
                enlace_clean += f"?{p.query}"
            linea['enlace_normalized'] = enlace_clean

            # ── Clave única: ID numérico del producto en la URL ───────────
            match = re.search(r'/product/(\d+)/', url_original)
            product_id = match.group(1) if match else enlace_clean
            linea['product_id'] = product_id

            categoria_nueva = linea.get('categoria', 'otros')

            # ── Buscar en cache (sin tocar MongoDB) ───────────────────────
            col_existente_name = self._cache.get(product_id)

            # ── Caso 1: Producto nuevo ────────────────────────────────────
            if col_existente_name is None:
                self.db[categoria_nueva].insert_one(linea)
                self._cache[product_id] = categoria_nueva  # actualizar cache
                self.stats['insertados'] += 1

            # ── Caso 2: Cambió de categoría → mover entre colecciones ─────
            elif col_existente_name != categoria_nueva:
                self.db[categoria_nueva].insert_one(linea)
                self.db[col_existente_name].delete_one({'product_id': product_id})
                self._cache[product_id] = categoria_nueva  # actualizar cache
                self.stats['movidos'] += 1
                spider.logger.info(
                    f"Movido: '{linea.get('nombre', '')[:50]}' "
                    f"[{col_existente_name}] → [{categoria_nueva}]"
                )

            # ── Caso 3: Misma categoría → actualizar precio/datos ─────────
            else:
                self.db[categoria_nueva].update_one(
                    {'product_id': product_id},
                    {'$set': linea}
                )
                self.stats['actualizados'] += 1

        except Exception as e:
            spider.logger.error(f"Error en Pipeline: {e}")
            self.stats['fallidos'] += 1

        return item