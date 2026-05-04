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
    calificacion = scrapy.Field()

class CompulagoItem(scrapy.Item):
    nombre          = scrapy.Field()
    precio          = scrapy.Field()   # precio original (puede ser calculado)
    promocion       = scrapy.Field()   # precio con descuento
    descuento       = scrapy.Field()   # porcentaje ej: "10%"
    marca           = scrapy.Field()
    categoria       = scrapy.Field()
    enlace          = scrapy.Field()
    imagen          = scrapy.Field()
    tienda          = scrapy.Field()


class ComputerworkingItem(scrapy.Item):
    nombre = scrapy.Field()
    precio = scrapy.Field()
    enlace = scrapy.Field()
    categoria = scrapy.Field()
    marca = scrapy.Field()
    tienda = scrapy.Field()
    imagen = scrapy.Field()

class TouretItem(scrapy.Item):
    nombre = scrapy.Field()
    precio = scrapy.Field()
    enlace = scrapy.Field()
    categoria = scrapy.Field()
    marca = scrapy.Field()
    tienda = scrapy.Field()
    imagen = scrapy.Field()
     
class FalabellaItem(scrapy.Item):
    nombre    = scrapy.Field()
    precio    = scrapy.Field()   # precio original
    promocion = scrapy.Field()   # precio con descuento
    descuento = scrapy.Field()   # porcentaje ej: "44%"
    marca     = scrapy.Field()
    categoria = scrapy.Field()
    enlace    = scrapy.Field()
    imagen    = scrapy.Field()
    vendedor  = scrapy.Field()
    tienda    = scrapy.Field()

