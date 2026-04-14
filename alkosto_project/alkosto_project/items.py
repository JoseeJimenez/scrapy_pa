import scrapy
class AlkostoProjectItem(scrapy.Item):
    nombre = scrapy.Field()
    precio = scrapy.Field()
    enlace = scrapy.Field()
    tienda = scrapy.Field()
