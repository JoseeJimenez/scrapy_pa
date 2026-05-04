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
        n = self.eliminar_tildes(nombre.lower())
        
        marcas_celulares = ['samsung galaxy', 'iphone', 'motorola', 'xiaomi redmi', 'huawei', 'celular', 'smartphone', 'telefono']
        if any(x in n for x in marcas_celulares):
            if not any(t in n for t in ['tablet', 'ipad', 'tv', 'televisor']):
                return 'celulares'

        palabras_pc = ['portatil', 'laptop', 'desktop', 'computador', 'all in one', 'pc gamer', 'macbook', 'mac book']
        if any(x in n for x in palabras_pc) or ('torre' in n and 'cpu' in n):
            return 'computadores'

        palabras_audio = ['parlante', 'bafle', 'audifonos', 'diadema', 'soundbar', 'jbl', 'barra de sonido', 'airpods', 'buds']
        if any(p in n for p in palabras_audio) or ('torre' in n and 'sonido' in n):
            if not any(r in n for r in ['reloj', 'smartwatch', 'watch']):
                return 'audio'

        if any(x in n for x in ['tablet', 'ipad', 'galaxy tab', 'apple pencil', 'lapiz para tablet']):
            return 'tablets'

        if any(x in n for x in ['televisor', 'tv', 'monitor', 'pantalla']):
            if 'proyector' not in n:
                return 'pantallas'

        palabras_consolas = ['playstation', 'ps5', 'ps4', 'xbox', 'nintendo', 'switch', 'consola', 'control para', 'joystick']
        if any(x in n for x in palabras_consolas):
            return 'consolas'

        accesorios_y_otros = [
            'cargador', 'cable usb', 'cubo', 'power bank', 'funda', 
            'reloj', 'smartwatch', 'watch', 'smart band', 
            'proyector', 'camara', 'estufa', 'nevera'
        ]
        
        if any(o in n for o in accesorios_y_otros):
            return 'otros'
            
        return 'otros'
    
    async def errback_close_page(self, failure):
        page = failure.request.meta.get("playwright_page")
        if page: await page.close()

    def closed(self, reason):
        os.kill(os.getpid(), signal.SIGINT)