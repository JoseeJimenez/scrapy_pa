import scrapy
from scrapy_playwright.page import PageMethod
from alkosto_project.items import ExitoProjectItem
import re
import unicodedata

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
    }

    def eliminar_tildes(self, texto):
        """Elimina acentos para mejorar el match de categorías."""
        if not texto: return ""
        return "".join(c for c in unicodedata.normalize('NFD', texto)
                  if unicodedata.category(c) != 'Mn')

    async def start(self):
        yield self.make_request(self.current_page)

    def make_request(self, page):
        return scrapy.Request(
            url=f"{self.base_url}{page}",
            meta={
                "playwright": True,
                "playwright_include_page": True,
                "playwright_page_methods": [
                    PageMethod("wait_for_selector", "article", timeout=60000),
                    PageMethod("evaluate", "window.scrollTo(0, document.body.scrollHeight)"),
                    PageMethod("wait_for_timeout", 10000), 
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

            todos_los_precios = p.xpath('.//*[contains(text(), "$")]//text()').getall()
            precios_numericos = []
            for texto in todos_los_precios:
                valor = self.limpiar_precio(texto)
                if valor > 0:
                    precios_numericos.append(valor)
            
            precios_numericos = list(dict.fromkeys(precios_numericos))

            if len(precios_numericos) >= 2:
                v_normal = max(precios_numericos)
                v_oferta = min(precios_numericos)
                item['precio'] = self._formatear_precio(v_normal)
                item['promocion'] = self._formatear_precio(v_oferta)
                
                pct_web = p.xpath('.//*[contains(text(), "%") and not(contains(text(), "IVA"))]/text()').get()
                item['descuento'] = pct_web.strip() if pct_web else f"-{round(100 - (v_oferta * 100 / v_normal))}%"
            elif len(precios_numericos) == 1:
                item['precio'] = self._formatear_precio(precios_numericos[0])
                item['promocion'] = None
                item['descuento'] = "0%"
            else:
                item['precio'] = "No disponible"
                item['promocion'] = None
                item['descuento'] = "0%"

            imgs = p.css('img::attr(src)').getall() + p.css('img::attr(data-src)').getall()
            img_final = next((i for i in imgs if i and not any(x in i.upper() for x in ['ENVIO', 'CIUDADES', 'PUNTOS'])), None)
            
            item['imagen'] = response.urljoin(img_final) if img_final else None
            item['tienda'] = 'Éxito'
            item['categoria'] = self.categorizar_estricto(item['nombre'])
            
            return item
        except Exception as e:
            self.logger.error(f"Error parseando producto: {e}")
            return None

    def limpiar_precio(self, texto):
        if not texto: return 0
        numeros = re.sub(r'[^\d]', '', texto)
        return int(numeros) if numeros else 0

    def _formatear_precio(self, valor):
        return f"$ {valor:,} COP".replace(',', '.')

    def categorizar_estricto(self, nombre):
        # Limpieza para ignorar tildes y mayúsculas
        n = self.eliminar_tildes(nombre.lower())
        
        # 1. Prioridades Críticas (Lo que suele colarse)
        if any(x in n for x in ['monitor', 'pantalla', 'display']):
            return 'monitores'
        if any(x in n for x in ['televisor', 'tv', 'smart tv']):
            return 'televisores'

        # 2. Diccionario de búsqueda refinado
        categorias = {
            'audio': ['parlante', 'bafle', 'audifonos', 'diadema', 'soundbar', 'jbl', 'alexa', 'echo dot'],
            'celulares': ['celular', 'smartphone', 'iphone', 'samsung galaxy', 'motorola', 'xiaomi'],
            'computadores': ['portatil', 'portátil', 'laptop', 'desktop', 'all in one', 'pc', 'computador'],
            'tablets': ['tablet', 'ipad', 'galaxy tab'],
            'consolas': ['playstation', 'xbox', 'nintendo', 'switch'],
            # Nueva categoría específica para Impresoras
            'impresoras': ['impresora', 'multifuncional', 'smart tank', 'ecotank', 'laserjet'],
            # Nueva categoría para Tintas e Insumos
            'tintas_insumos': ['tinta', 'cartucho', 'toner', 'botella de tinta', 'consumible'],
            # Periféricos queda para el resto de accesorios
            'perifericos': ['mouse', 'teclado', 'webcam', 'disco duro externo', 'memoria usb']
        }

        # 3. Mapeo lógico
        for cat, palabras in categorias.items():
            if any(p in n for p in palabras):
                return cat
        
        # 4. Si no encaja en nada
        return 'otros'

    async def errback_close_page(self, failure):
        page = failure.request.meta.get("playwright_page")
        if page:
            await page.close()