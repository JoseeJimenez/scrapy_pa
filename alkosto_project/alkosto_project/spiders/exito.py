import scrapy
from scrapy_playwright.page import PageMethod
from alkosto_project.items import ExitoProjectItem

class ExitoSpider(scrapy.Spider):
    name = 'exito'
    
    custom_settings = {
        'CONCURRENT_REQUESTS': 1, 
        'DOWNLOAD_DELAY': 2,
        'DOWNLOAD_TIMEOUT': 60,
        'PLAYWRIGHT_BROWSER_TYPE': 'chromium',
    }

    def start_requests(self):
        url = 'https://www.exito.com/tecnologia'
        yield scrapy.Request(
            url,
            meta=self._playwright_meta(),
            callback=self.parse,
            errback=self.errback_close_page,
        )

    def parse(self, response):
        productos = response.css('article.productCard_productCard__M0677')
        
        for p in productos:
            item = self._extraer_producto(p, response)
            if item['nombre']:
                yield item

        # Paginación
        next_page = response.css('a[aria-label="Siguiente"]::attr(href)').get() or \
                    response.css('a.Pagination_nextPreviousLink__f7_2J::attr(href)').get()
        
        if next_page:
            yield scrapy.Request(
                response.urljoin(next_page),
                meta=self._playwright_meta(),
                callback=self.parse,
                errback=self.errback_close_page,
            )

    def _playwright_meta(self):
        return {
            "playwright": True,
            "playwright_include_page": True,
            "playwright_page_methods": [
                PageMethod("wait_for_selector", "article.productCard_productCard__M0677", timeout=20000),
                PageMethod("evaluate", """
                    async () => {
                        const delay = ms => new Promise(resolve => setTimeout(resolve, ms));
                        for (let i = 0; i < document.body.scrollHeight; i += 1200) {
                            window.scrollTo(0, i);
                            await delay(250); 
                        }
                        window.scrollTo(0, 0);
                    }
                """),
                PageMethod("wait_for_timeout", 5000), 
            ],
        }

    def _extraer_producto(self, p, response):
        item = ExitoProjectItem()
        
        # Selectores más robustos para nombre y marca
        item['nombre'] = p.css('h3[class*="styles_name"]::text').get()
        item['marca'] = p.css('h3[class*="styles_brand"]::text').get()
        
        # --- LÓGICA DE PRECIOS MEJORADA ---
        # Buscamos todos los textos que tengan formato de precio dentro del contenedor
        precios_nodos = p.css('p[class*="ProductPrice_container_price"]::text').getall()
        
        # Limpiamos todos los posibles precios encontrados
        precios_limpios = [self.limpiar_precio(txt) for txt in precios_nodos if self.limpiar_precio(txt) > 0]
        
        if precios_limpios:
            # El precio más alto suele ser el base (tachado)
            # El precio más bajo suele ser la oferta (promoción)
            num_base = max(precios_limpios)
            num_promo = min(precios_limpios)
            
            item['precio'] = self._formatear_precio(num_base)
            item['promocion'] = self._formatear_precio(num_promo)
        else:
            # Intento de rescate si los selectores de clase fallaron
            fallback_precio = p.xpath('.//*[contains(text(), "$")]/text()').get()
            num_f = self.limpiar_precio(fallback_precio)
            item['precio'] = self._formatear_precio(num_f)
            item['promocion'] = self._formatear_precio(num_f)

        # --- IMAGEN Y ENLACE ---
        item['imagen'] = p.css('img::attr(src)').get()
        item['enlace'] = response.urljoin(p.css('a::attr(href)').get())
        item['tienda'] = 'Éxito'
        item['categoria'] = self.categorizar_simple(item['nombre']) if item['nombre'] else 'tecnologia'
        
        return item

    def limpiar_precio(self, texto):
        if texto:
            solo_numeros = ''.join(filter(str.isdigit, str(texto)))
            return int(solo_numeros) if solo_numeros else 0
        return 0

    def _formatear_precio(self, valor):
        if valor and valor > 0:
            return f"$ {valor:,.0f}".replace(",", ".") + " COP"
        return None

    async def errback_close_page(self, failure):
        page = failure.request.meta.get("playwright_page")
        if page:
            await page.close()

    def categorizar_simple(self, nombre):
        n = nombre.lower()
        if any(w in n for w in ['computador', 'portátil', 'laptop', 'vivobook', 'ideapad']): return 'computadores'
        if any(w in n for w in ['celular', 'smartphone', 'motorola', 'iphone']): return 'celulares'
        if any(w in n for w in ['televisor', 'tv', 'smart tv']): return 'pantallas'
        return 'tecnologia'