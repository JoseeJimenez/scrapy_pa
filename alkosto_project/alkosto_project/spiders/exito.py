import scrapy
from scrapy_playwright.page import PageMethod
from alkosto_project.items import ExitoProjectItem
import re
import unicodedata
import os
import signal

class ExitoSpider(scrapy.Spider):
    name = 'exito'
    allowed_domains = ['exito.com']
    base_url = 'https://www.exito.com/tecnologia?page='
    current_page = 1
    total_pages = 49

    custom_settings = {
        'CONCURRENT_REQUESTS': 1,
        'DOWNLOAD_DELAY': 3,
        'PLAYWRIGHT_BROWSER_TYPE': 'chromium',
        'TWISTED_REACTOR': 'twisted.internet.asyncioreactor.AsyncioSelectorReactor', 
    }

    def eliminar_tildes(self, texto):
        if not texto: return ""
        return "".join(c for c in unicodedata.normalize('NFD', texto)
                  if unicodedata.category(c) != 'Mn')

    def start_requests(self):
        yield self.make_request(self.current_page)

    def make_request(self, page):
        return scrapy.Request(
            url=f"{self.base_url}{page}",
            meta={
                "playwright": True,
                "playwright_include_page": True,
                "playwright_page_methods": [
                    PageMethod("wait_for_selector", "article", timeout=60000),
                    # Scroll progresivo para disparar carga de estrellas
                    PageMethod("evaluate", "window.scrollBy(0, 2000)"),
                    PageMethod("wait_for_timeout", 5000),
                    PageMethod("evaluate", "window.scrollTo(0, document.body.scrollHeight)"),
                    PageMethod("wait_for_timeout", 15000), 
                ],
            },
            callback=self.parse,
            errback=self.errback_close_page,
            dont_filter=True
        )

    async def parse(self, response):
        page_obj = response.meta["playwright_page"]
        productos = response.css('article')
        
        self.logger.info(f"ÉXITO: Procesando página {self.current_page}")

        for p in productos:
            item = self._extraer_producto(p, response)
            if item:
                yield item

        await page_obj.close()
        if self.current_page < self.total_pages:
            self.current_page += 1
            yield self.make_request(self.current_page)

    def _extraer_producto(self, p, response):
        item = ExitoProjectItem()
        try:
            nombre = p.css('h3[class*="name"]::text').get()
            if not nombre: return None
            
            item['nombre'] = nombre.strip()
            item['marca'] = p.css('h3[class*="brand"]::text').get('').strip()
            item['enlace'] = response.urljoin(p.css('a::attr(href)').get())

            precios_raw = p.xpath('.//*[contains(text(), "$")]/text()').getall()
            precios_num = sorted(list(set(self.limpiar_precio(t) for t in precios_raw if self.limpiar_precio(t) > 1000)), reverse=True)
            
            val_precio, val_promo = (None, None)
            if len(precios_num) >= 2:
                val_precio, val_promo = precios_num[0], precios_num[-1]
                item['precio'] = self._formatear_precio(val_precio)
                item['promocion'] = self._formatear_precio(val_promo)
            elif len(precios_num) == 1:
                val_precio = precios_num[0]
                item['precio'] = self._formatear_precio(val_precio)
                item['promocion'] = None

            if val_precio and val_promo and val_promo < val_precio:
                calculo = round(100 - (val_promo * 100 / val_precio))
                item['descuento'] = f"-{calculo}%"
            else:
                item['descuento'] = None

            calif_selector = p.css('[class*="ratings-calification"]::text, [class*="ratingInline"]::text').get()
            
            item['calificacion'] = None
            if calif_selector:
                match = re.search(r'(\d[\.,]\d)', calif_selector)
                if match:
                    val = float(match.group(1).replace(',', '.'))
                    if 0 < val <= 5.0:
                        item['calificacion'] = val
            
            if item['calificacion'] is None:
                bloque_estrellas = p.xpath('.//*[contains(@class, "rating") or contains(@class, "star")]//text()').getall()
                match_alt = re.search(r'(\d[\.,]\d)', " ".join(bloque_estrellas))
                if match_alt:
                    val_alt = float(match_alt.group(1).replace(',', '.'))
                    if 0 < val_alt <= 5.0:
                        item['calificacion'] = val_alt

            imgs = p.css('img::attr(src)').getall() + p.css('img::attr(data-src)').getall()
            img_final = next((i for i in imgs if i and 'vtexassets' in i), None)
            item['imagen'] = response.urljoin(img_final) if img_final else None
            item['tienda'] = 'Éxito'
            item['categoria'] = self.categorizar_estricto(item['nombre'])
            
            return item
        except Exception:
            return None
        
    def limpiar_precio(self, texto):
        if not texto: return 0
        numeros = re.sub(r'[^\d]', '', texto)
        return int(numeros) if numeros else 0

    def _formatear_precio(self, valor):
        return f"$ {valor:,} COP".replace(',', '.')

    def categorizar_estricto(self, nombre):
        # Normalizamos el nombre eliminando tildes y pasando a minúsculas
        n = self.eliminar_tildes(nombre.lower())
        
        # Prioridad para Pantallas/TV
        if any(x in n for x in ['monitor', 'pantalla', 'televisor', 'tv']):
            return 'pantallas'

        # Definición de categorías con palabras clave expandidas
        categorias = {
            'audio': [
                'parlante', 'bafle', 'audifonos', 'diadema', 'soundbar', 
                'jbl', 'alexa', 'airpods', 'buds', 'bocina', 
                'barra de sonido', 'teatro en casa', 'home theater', 
                'torre de sonido', 'microfono', 'subwoofer'
            ],
            'celulares': [
                'celular', 'smartphone', 'iphone', 'samsung galaxy', 
                'motorola', 'reloj inteligente', 'apple watch', 'galaxy watch'
            ],
            'computadores': [
                'portatil', 'laptop', 'desktop', 'pc', 'computador', 
                'macbook', 'todo en uno', 'aio'
            ],
            'impresoras': [
                'impresora', 'multifuncional', 'epson', 'hp', 
                'canon', 'smart tank', 'ecotank', 'laserjet'
            ],
            'consolas': [
                'playstation', 'xbox', 'nintendo', 'switch', 'consola', 'joystick'
            ],
            'tablets': [
                'tablet', 'ipad', 'galaxy tab'
            ]
        }

        # Buscamos coincidencias
        for cat, palabras in categorias.items():
            if any(p in n for p in palabras):
                return cat
                
        return 'otros'
    
    async def errback_close_page(self, failure):
        page = failure.request.meta.get("playwright_page")
        if page: await page.close()

    def closed(self, reason):
        os.kill(os.getpid(), signal.SIGINT)