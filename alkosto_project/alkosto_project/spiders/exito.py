import scrapy
from scrapy_playwright.page import PageMethod
from alkosto_project.items import ExitoProjectItem

class ExitoSpider(scrapy.Spider):
    name = 'exito'
    max_pages = 49
    current_page = 1
    base_url = 'https://www.exito.com/tecnologia?page='

    custom_settings = {
        'CONCURRENT_REQUESTS': 1,
        'DOWNLOAD_DELAY': 3,
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
                    PageMethod("evaluate", "window.scrollTo(0, document.body.scrollHeight/2)"),
                    PageMethod("wait_for_timeout", 2000), # Subimos de 1500 a 2000
                    PageMethod("evaluate", "window.scrollTo(0, document.body.scrollHeight)"),
                    PageMethod("wait_for_timeout", 4000), # Subimos de 3000 a 4000
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
        try:
            nombre = p.css('h3[class*="name"]::text').get()
            if not nombre: return None
            
            item['nombre'] = nombre.strip()
            item['marca'] = p.css('h3[class*="brand"]::text').get('').strip()
            
            # --- MEJORA DE PRECIOS ---
            # Buscamos el precio principal (el que tú ves en grande)
            # Intentamos varios selectores comunes en el Éxito para evitar el null
            p_actual = p.css('p[data-testid="virtuality-price"]::text').get() or \
                       p.css('p[class*="Price_price"]::text').get() or \
                       p.xpath('.//p[contains(@class, "price")]/text()').get()

            # Buscamos el precio tachado (el original)
            p_tachado = p.css('p[class*="dashed"]::text').get() or \
                        p.css('p[class*="ListPrice"]::text').get()

            v_actual = self.limpiar_precio(p_actual)
            v_tachado = self.limpiar_precio(p_tachado)

            if v_tachado > v_actual and v_actual > 0:
                item['promocion'] = self._formatear_precio(v_actual)
                item['precio'] = self._formatear_precio(v_tachado)
                item['descuento'] = f"-{round(100 - (v_actual * 100 / v_tachado))}%"
            else:
                item['precio'] = self._formatear_precio(v_actual)
                item['promocion'] = None
                item['descuento'] = "0%"

            # --- MEJORA DE IMAGEN (Evitar la de "Envío") ---
            # Priorizamos 'data-src' que es donde guardan la imagen real antes de cargarla
            imagen = p.css('img::attr(data-src)').get() or \
                     p.css('img::attr(src)').get()
            
            # Si la imagen contiene "envio-gratis" o "ciudades", es que no ha cargado la real
            if imagen and ("ENVIO" in imagen.upper() or "CIUDADES" in imagen.upper()):
                # Intentamos buscar otra imagen dentro del mismo article
                imagen = p.css('img[class*="product"]::attr(src)').get() or imagen

            item['imagen'] = response.urljoin(imagen)
            item['enlace'] = response.urljoin(p.css('a::attr(href)').get())
            item['tienda'] = 'Éxito'
            item['categoria'] = self.categorizar_estricto(item['nombre'])
            
            return item
        except Exception as e:
            self.logger.error(f"Error parseando producto: {e}")
            return None

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