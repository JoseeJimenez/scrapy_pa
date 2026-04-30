import scrapy
from scrapy_playwright.page import PageMethod
from alkosto_project.items import ExitoProjectItem
import re
import json


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
        'CLOSESPIDER_TIMEOUT': 0, # Ayuda a que cierre más limpio en Windows
    }

    # Nuevo método recomendado por Scrapy 2.13+
    async def start(self):
        yield self.make_request(self.current_page)

    def make_request(self, page):
        return scrapy.Request(
            url=f"{self.base_url}{page}",
            meta={
                "playwright": True,
                "playwright_include_page": True,
                "playwright_page_methods": [
                    # Espera amplia para evitar el TimeoutError en conexiones lentas
                    PageMethod("wait_for_selector", "article", timeout=60000),
                    # Scroll para disparar el lazy loading de imágenes y precios
                    PageMethod("evaluate", "window.scrollTo(0, document.body.scrollHeight)"),
                    # Tiempo de "asentamiento" para que el JS del Éxito renderice los precios reales
                    PageMethod("wait_for_timeout", 10000), 
                ],
            },
            callback=self.parse,
            errback=self.errback_close_page,
            dont_filter=True
        )

    async def parse(self, response):
        page_obj = response.meta["playwright_page"]
        
        # Extraemos los productos usando selectores CSS y XPath combinados
        productos = response.css('article')
        self.logger.info(f"ÉXITO: Procesando página {self.current_page} de {self.total_pages}")

        for p in productos:
            item = self._extraer_producto(p, response)
            if item:
                yield item

        await page_obj.close()

        # Lógica de paginación
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

            # --- ESTRATEGIA DE BARRIDO: Traemos todos los textos que tengan "$" ---
            todos_los_precios = p.xpath('.//*[contains(text(), "$")]//text()').getall()
            # Limpiamos y convertimos a números
            precios_numericos = []
            for texto in todos_los_precios:
                valor = self.limpiar_precio(texto)
                if valor > 0:
                    precios_numericos.append(valor)
            
            # Eliminamos duplicados manteniendo el orden
            precios_numericos = list(dict.fromkeys(precios_numericos))

            # --- LÓGICA DE ASIGNACIÓN SEGÚN LOS VALORES ENCONTRADOS ---
            if len(precios_numericos) >= 2:
                # Si hay dos o más, el mayor es el normal y el menor es la oferta
                v_normal = max(precios_numericos)
                v_oferta = min(precios_numericos)
                item['precio'] = self._formatear_precio(v_normal)
                item['promocion'] = self._formatear_precio(v_oferta)
                item['descuento'] = f"-{round(100 - (v_oferta * 100 / v_normal))}%"
            elif len(precios_numericos) == 1:
                # Solo hay un precio (sin descuento)
                item['precio'] = self._formatear_precio(precios_numericos[0])
                item['promocion'] = None
                item['descuento'] = "0%"
            else:
                # Fallback total: buscar en cualquier parte del article
                item['precio'] = "No disponible"
                item['promocion'] = None
                item['descuento'] = "0%"

            # --- REFUERZO DE DESCUENTO (Si el Éxito tiene el globo de %) ---
            pct_web = p.xpath('.//*[contains(text(), "%") and not(contains(text(), "IVA"))]/text()').get()
            if pct_web and item['descuento'] == "0%":
                item['descuento'] = pct_web.strip()

            # --- IMAGEN ---
            imgs = p.css('img::attr(src)').getall() + p.css('img::attr(data-src)').getall()
            img_final = next((i for i in imgs if i and not any(x in i.upper() for x in ['ENVIO', 'CIUDADES', 'PUNTOS'])), None)
            
            item['imagen'] = response.urljoin(img_final) if img_final else None
            item['tienda'] = 'Éxito'
            item['categoria'] = self.categorizar_estricto(item['nombre'])
            
            return item
        except Exception as e:
            self.logger.error(f"Error crítico en producto: {e}")
            return None

    def limpiar_precio(self, texto):
        if not texto: return 0
        numeros = re.sub(r'[^\d]', '', texto)
        return int(numeros) if numeros else 0

    def _formatear_precio(self, valor):
        return f"$ {valor:,} COP".replace(',', '.')

    def categorizar_estricto(self, nombre):
        n = nombre.lower()
        if any(x in n for x in ['celular', 'smartphone', 'iphone']): return 'celulares'
        if any(x in n for x in ['televisor', 'smart tv', 'pantalla']): return 'pantallas'
        if any(x in n for x in ['portatil', 'laptop', 'computador', 'desktop']): return 'computadores'
        if any(x in n for x in ['audifono', 'parlante', 'barra de sonido', 'sonido']): return 'audio'
        if 'tablet' in n: return 'tablets'
        return 'tecnologia'

    async def errback_close_page(self, failure):
        page = failure.request.meta.get("playwright_page")
        if page:
            await page.close()
        self.logger.error(f"Error en solicitud: {failure}")