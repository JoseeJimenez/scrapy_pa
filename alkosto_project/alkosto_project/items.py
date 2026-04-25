import scrapy
class AlkostoProjectItem(scrapy.Item):
    nombre = scrapy.Field()
    precio = scrapy.Field()
    enlace = scrapy.Field()
    categoria = scrapy.Field()
    marca = scrapy.Field()
    tienda = scrapy.Field()
    imagen = scrapy.Field()
class ExitoProjectItem(scrapy.Item):
    nombre = scrapy.Field()
    marca = scrapy.Field()
    precio = scrapy.Field()
    precio_promocion = scrapy.Field()
    specs = scrapy.Field()
    enlace = scrapy.Field()
    vendedor = scrapy.Field()
    patrocinado = scrapy.Field()
    categoria = scrapy.Field()
    tienda = scrapy.Field()
    