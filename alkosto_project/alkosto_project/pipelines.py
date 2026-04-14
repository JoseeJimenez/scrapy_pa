from itemadapter import ItemAdapter
from pymongo import MongoClient

class AlkostoPipeline:

    def open_spider(self, spider):
        # Conexión a tu clúster de MongoDB Atlas
        self.client = MongoClient("mongodb+srv://cesarjimenezf_db_user:Cesar0929*@scrapy.5knfwvt.mongodb.net/?appName=Scrapy")
        self.db = self.client["tecnoradar"]
        spider.logger.info("Conexión abierta con MongoDB Atlas: Base de datos 'tecnoradar'")

    def close_spider(self, spider):
        self.client.close()
        spider.logger.info("Conexión con MongoDB Atlas cerrada")

    def process_item(self, item, spider):
        coleccion = self.db[spider.name]
        linea = ItemAdapter(item).asdict()

        coleccion.update_one(
            {"nombre": linea["nombre"]},  # busca por nombre en vez de enlace
            {"$set": linea},
            upsert=True
        )
        return item