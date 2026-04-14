import scrapy

class AlkostoComputadoresSpider(scrapy.Spider):
    name = 'alkosto_compus'
    start_urls = ['https://www.alkosto.com/computadores-tablet/c/BI_COMP_ALKOS']

    def parse(self, response):
        # Cada tarjeta de producto
        for producto in response.css('li.product__item'):
            
            # 1. Información Básica
            nombre = producto.css('h3.product__item__top__title::text').get()
            
            # 2. Precios y Descuentos
            precio_actual = producto.css('span.price::text').get()
            precio_original = producto.css('p.product__price--discounts__price span::text').get() # Precio tachado
            descuento = producto.css('span.product__price--discounts__discount::text').get() # Ejemplo: -37%

            # 3. EXTRACCIÓN DE LA LISTA TÉCNICA (Lo que me mostraste en la imagen)
            # Vamos a guardar las specs en un diccionario
            specs = {}
            lista_features = producto.css('ul.product_item_information_key_features li.item')
            
            for feature in lista_features:
                clave = feature.css('div.item--key::text').get()
                valor = feature.css('div.item--value::text').get()
                if clave and valor:
                    # Limpiamos los dos puntos ":" si aparecen
                    clave_limpia = clave.replace(':', '').strip()
                    specs[clave_limpia] = valor.strip()

            yield {
                'tienda': 'Alkosto',
                'producto': nombre.strip() if nombre else None,
                'precio_final': self.limpiar_precio(precio_actual),
                'precio_base': self.limpiar_precio(precio_original),
                'descuento': descuento.strip() if descuento else None,
                'especificaciones': specs, # Aquí queda tu RAM, Disco, etc.
                'enlace': response.urljoin(producto.css('a::attr(href)').get())
            }

        # Paginación
        next_page = response.css('a.pagination__next::attr(href)').get()
        if next_page:
            yield response.follow(next_page, callback=self.parse)

    def limpiar_precio(self, texto):
        if texto:
            solo_numeros = ''.join(filter(str.isdigit, texto))
            return int(solo_numeros) if solo_numeros else 0
        return None