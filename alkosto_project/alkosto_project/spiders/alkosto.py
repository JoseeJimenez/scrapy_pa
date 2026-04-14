import scrapy
from scrapy_playwright.page import PageMethod

class AlkostoSpider(scrapy.Spider):
    name = 'alkosto'
    
    # Configuramos el User-Agent para que parezca un navegador real
    custom_settings = {
        'USER_AGENT': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
        'PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT': 120000, # 2 minutos por si el internet molesta
    }

    def start_requests(self):
        url = 'https://www.alkosto.com/computadores-tablet/c/BI_COMP_ALKOS'
        
        # Script JS para hacer clic en "Mostrar más" hasta que no haya más productos
        # Usamos el selector .js-load-more que vimos en tu consola
        load_more_script = """
        async () => {
            while (true) {
                const button = document.querySelector('button.js-load-more');
                if (button && !button.disabled) {
                    button.scrollIntoView();
                    button.click();
                    // Esperamos a que Algolia cargue el siguiente lote
                    await new Promise(r => setTimeout(r, 3000));
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
                    # 1. Esperar a que la red esté tranquila
                    PageMethod("wait_until", "networkidle"),
                    # 2. Esperar a que al menos un producto sea visible
                    PageMethod("wait_for_selector", "li.ais-InfiniteHits-item"),
                    # 3. Ejecutar el loop de clics para cargar los 501 productos
                    PageMethod("evaluate", load_more_script),
                    # 4. Una espera final técnica para el renderizado
                    PageMethod("wait_for_timeout", 2000),
                ],
            }
        )

    def parse(self, response):
        # Usamos el selector de Algolia que confirmamos en tu imagen
        productos = response.css('li.ais-InfiniteHits-item')
        
        self.logger.info(f"🚀 Se encontraron {len(productos)} productos en total.")

        for p in productos:
            # Los nombres suelen estar en un h3 o h2 dentro del item
            nombre = p.css('.js-algolia-product-title::text').get() or p.css('h3::text').get()
            
            # El precio final (el que está en naranja en tu captura)
            precio = p.css('.price span::text').get() or p.css('.ais-hit--price::text').get()
            
            link = p.css('a::attr(href)').get()

            if nombre:
                yield {
                    'nombre': nombre.strip(),
                    'precio': self.limpiar_precio(precio),
                    'enlace': response.urljoin(link) if link else None,
                    'tienda': 'Alkosto'
                }

    def limpiar_precio(self, texto):
        if texto:
            # Quitamos puntos, signos de peso y espacios
            solo_numeros = ''.join(filter(str.isdigit, texto))
            return int(solo_numeros) if solo_numeros else 0
        return 0