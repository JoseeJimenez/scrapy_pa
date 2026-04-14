import scrapy
from scrapy_playwright.page import PageMethod

class AlkostoSpider(scrapy.Spider):
    name = 'alkosto'
    
    custom_settings = {
        'USER_AGENT': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
        'PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT': 120000,
        'ROBOTSTXT_OBEY': False, # Para asegurar que no te bloquee por política
    }

    def start_requests(self):
        url = 'https://www.alkosto.com/computadores-tablet/c/BI_COMP_ALKOS'
        
        # Script optimizado: hace scroll y clic hasta que el botón desaparezca
        load_more_script = """
        async () => {
            while (true) {
                const button = document.querySelector('button.js-load-more');
                if (button && !button.disabled && button.offsetParent !== null) {
                    button.scrollIntoView();
                    button.click();
                    // Espera generosa para que Algolia renderice los precios nuevos
                    await new Promise(r => setTimeout(r, 3500));
                } else {
                    break;
                }
            }
        }
        """

        yield scrapy.Request(
            url,
            meta={
                "playwright": True,
                "playwright_include_page": True,
                "playwright_page_methods": [
                    PageMethod("wait_until", "networkidle"),
                    PageMethod("wait_for_selector", "li.ais-InfiniteHits-item"),
                    PageMethod("evaluate", load_more_script),
                    # Espera final crucial para que los últimos precios se dibujen
                    PageMethod("wait_for_timeout", 5000),
                ],
            }
        )

    def parse(self, response):
        # Seleccionamos todos los items de la lista de Algolia
        productos = response.css('li.ais-InfiniteHits-item')
        
        self.logger.info(f"🚀 Procesando {len(productos)} productos encontrados.")

        for p in productos:
            # Selector de nombre (múltiples opciones por si cambia el DOM)
            nombre = p.css('.js-algolia-product-title::text').get() or p.css('h3::text').get()
            
            # --- MEJORA EN PRECIOS ---
            # Intentamos capturar el texto del precio desde diferentes clases posibles en Alkosto
            precio_raw = (
                p.css('span.price::text').get() or 
                p.css('.ais-hit--price::text').get() or 
                p.xpath('.//span[contains(@class, "price")]//text()').get()
            )
            
            link = p.css('a::attr(href)').get()

            if nombre:
                yield {
                    'nombre': nombre.strip(),
                    'precio': self.limpiar_precio(precio_raw),
                    'enlace': response.urljoin(link) if link else None,
                    'tienda': 'Alkosto'
                }

    def limpiar_precio(self, texto):
        if texto:
            # Quitamos todo lo que no sea un número ($, puntos, espacios, comas)
            solo_numeros = ''.join(filter(str.isdigit, str(texto)))
            if solo_numeros:
                return int(solo_numeros)
        return 0