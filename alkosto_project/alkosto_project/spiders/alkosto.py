import scrapy
from scrapy_playwright.page import PageMethod

class AlkostoComputadoresSpider(scrapy.Spider):
    name = 'alkosto_compus'
    
    def start_requests(self):
        url = 'https://www.alkosto.com/computadores-tablet/c/BI_COMP_ALKOS'
        
        # User agent de un navegador real para evitar bloqueos en Colombia
        user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"

        yield scrapy.Request(
            url,
            headers={'User-Agent': user_agent},
            meta={
                "playwright": True,
                "playwright_include_page": True,
                "playwright_page_methods": [
                    # Esperar a que la red esté ociosa (fundamental por los logs de JS que viste)
                    PageMethod("wait_until", "networkidle"),
                    # Scroll para activar el lazy loading de Alkosto
                    PageMethod("evaluate", "window.scrollTo(0, document.body.scrollHeight / 2)"),
                    # Tiempo extra de gracia para que los scripts de Algolia dibujen los items
                    PageMethod("wait_for_timeout", 8000), 
                    # Esperar a que el contenedor de productos exista
                    PageMethod("wait_for_selector", "li[class*='product-item'], .js-algolia-product-item"),
                ],
            }
        )

    def parse(self, response):
        # Intentamos con el selector específico de Algolia que detectamos en los logs
        productos = response.css('.js-algolia-product-item')
        
        # Si no lo encuentra, probamos con el selector genérico de lista
        if not productos:
            productos = response.css('li[class*="product-item"]')

        self.logger.info(f"✅ ANALIZANDO: {len(productos)} productos encontrados en el DOM.")

        for producto in productos:
            nombre = producto.css('h3.product__item__top__title::text, h3::text').get()
            precio_raw = producto.css('span.price::text').get()
            link = producto.css('a::attr(href)').get()

            if nombre:
                yield {
                    'tienda': 'Alkosto',
                    'producto': nombre.strip(),
                    'precio_final': self.limpiar_precio(precio_raw),
                    'url': response.urljoin(link) if link else None,
                }

    def limpiar_precio(self, texto):
        if texto:
            # Elimina todo lo que no sea número para que sea procesable
            solo_numeros = ''.join(filter(str.isdigit, texto))
            return int(solo_numeros) if solo_numeros else 0
        return 0