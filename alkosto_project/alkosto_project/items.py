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
    promocion = scrapy.Field()
    descuento = scrapy.Field()  
    imagen = scrapy.Field()
    enlace = scrapy.Field()
    tienda = scrapy.Field()
    categoria = scrapy.Field()

class CompulagoItem(scrapy.Item):
    nombre    = scrapy.Field()
    precio    = scrapy.Field()
    marca     = scrapy.Field()
    categoria = scrapy.Field()
    enlace    = scrapy.Field()
    imagen    = scrapy.Field()
    tienda    = scrapy.Field()
 
