import scrapy
from scrapy_playwright.page import PageMethod
from alkosto_project.items import ExitoProjectItem

class ExitoSpider(scrapy.Spider):
    name = 'exito'
    max_pages = 40
    current_page = 1
    base_url = 'https://www.exito.com/tecnologia?page='

    custom_settings = {
        'CONCURRENT_REQUESTS': 1,
        'DOWNLOAD_DELAY': 3, # Un poco más de delay para evitar bloqueos en el bucle largo
        'PLAYWRIGHT_BROWSER_TYPE': 'chromium',
    }

    def start_requests(self):
        yield self.make_request(self.current_page)

    def make_request(self, page):
        return scrapy.Request(
            url=f"{self.base_url}{page}",
            meta={
                "playwright": True,
                "playwright_include_page": True,
                "playwright_page_methods": [
                    PageMethod("wait_for_selector", "article[class*='productCard']", timeout=30000),
                    # Scroll en dos tiempos para asegurar carga de datos
                    PageMethod("evaluate", "window.scrollTo(0, document.body.scrollHeight/2)"),
                    PageMethod("wait_for_timeout", 2000),
                    PageMethod("evaluate", "window.scrollTo(0, document.body.scrollHeight)"),
                    PageMethod("wait_for_timeout", 3000),
                ],
            },
            callback=self.parse,
            errback=self.errback_close_page,
            dont_filter=True # Vital para que Scrapy no bloquee las páginas del bucle
        )

    async def parse(self, response):
        page = response.meta.get("playwright_page")
        productos = response.css('article[class*="productCard"]')
        
        if not productos:
            self.logger.warning(f"Fin del catálogo o error en pág {self.current_page}")
            if page: await page.close()
            return

        self.logger.info(f"ÉXITO: Procesando página {self.current_page} de {self.max_pages}")

        for p in productos:
            item = self._extraer_producto(p, response)
            if item:
                yield item

        # Cerramos la página de Playwright para liberar RAM antes de la siguiente
        if page:
            await page.close()

        # Salto automático a la siguiente URL
        if self.current_page < self.max_pages:
            self.current_page += 1
            yield self.make_request(self.current_page)

    def _extraer_producto(self, p, response):
        item = ExitoProjectItem()
        nombre = p.css('h3[class*="name"]::text').get()
        if not nombre: return None
        
        item['nombre'] = nombre.strip()
        item['marca'] = p.css('h3[class*="brand"]::text').get('').strip()
        
        # Precios
        precio_raw = p.css('p[data-testid="virtuality-price"]::text').get()
        item['precio'] = self._formatear_precio(self.limpiar_precio(precio_raw))
        
        item['enlace'] = response.urljoin(p.css('a::attr(href)').get())
        item['tienda'] = 'Éxito'
        item['categoria'] = self.categorizar_estricto(item['nombre'])
        return item

    def categorizar_estricto(self, nombre):
        n = nombre.lower()
        if any(x in n for x in ['televisor', 'tv', 'pantalla']): return 'pantallas'
        if any(x in n for x in ['celular', 'smartphone', 'iphone']): return 'celulares'
        if any(x in n for x in ['portátil', 'laptop', 'computador']): return 'computadores'
        return 'otros'

    def limpiar_precio(self, t):
        if not t: return 0
        nums = ''.join(filter(str.isdigit, str(t)))
        return int(nums) if nums else 0

    def _formatear_precio(self, v):
        return f"$ {v:,.0f}".replace(",", ".") + " COP" if v > 0 else "No disponible"

    async def errback_close_page(self, failure):
        page = failure.request.meta.get("playwright_page")
        if page: await page.close()