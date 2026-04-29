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
        # URL de la categoría tecnología
        url = 'https://www.exito.com/tecnologia'
        yield scrapy.Request(
            url,
            meta=self._playwright_meta(),
            callback=self.parse,
            errback=self.errback_close_page,
        )

    def _playwright_meta(self):
        return {
            "playwright": True,
            "playwright_include_page": True,
            "playwright_page_methods": [
                # Esperar a que los artículos carguen en el DOM
                PageMethod("wait_for_selector", "article.productCard_productCard__M0677", timeout=15000),
                
                # Scroll progresivo para activar el Lazy Load de imágenes y precios
                PageMethod("evaluate", """
                    async () => {
                        const delay = ms => new Promise(resolve => setTimeout(resolve, ms));
                        for (let i = 0; i < document.body.scrollHeight; i += 1200) {
                            window.scrollTo(0, i);
                            await delay(200); 
                        }
                        window.scrollTo(0, 0);
                        await delay(500);
                    }
                """),
                
                # Tiempo extra para que el renderizado de etiquetas de descuento termine
                PageMethod("wait_for_timeout", 3000), 
            ],
        }

    def parse(self, response):
        # Seleccionamos todos los contenedores de productos basados en la clase observada
        productos = response.css('article.productCard_productCard__M0677')
        
        self.logger.info(f"Se encontraron {len(productos)} productos en esta página.")

        for p in productos:
            item = self._extraer_producto(p, response)
            if item['nombre']:
                yield item

        # Lógica de Paginación
        next_page = response.css('a[aria-label="Siguiente"]::attr(href)').get() or \
                    response.css('a.Pagination_nextPreviousLink__f7_2J::attr(href)').get()
        
        if next_page:
            yield scrapy.Request(
                response.urljoin(next_page),
                meta=self._playwright_meta(),
                callback=self.parse,
                errback=self.errback_close_page,
            )

    def _extraer_producto(self, p, response):
        item = ExitoProjectItem()
        
        # 1. Identificación básica (Nombre y Marca)
        item['nombre'] = p.css('h3[class*="styles_name"]::text').get()
        item['marca'] = p.css('h3[class*="styles_brand"]::text').get()
        
        # 2. Extracción de Descuento
        # Buscamos el texto dentro del span con data-percentage
        dto = p.css('span[data-percentage="true"]::text').get() or \
              p.xpath('.//span[contains(@data-percentage, "true")]//text()').get()
        item['descuento'] = dto.strip() if dto else "0%"

        # 3. Lógica Robusta de Precios (Evita el error de precio: null)
        # Buscamos todos los textos que contengan el símbolo "$"
        precios_encontrados = p.xpath('.//*[contains(text(), "$")]/text()').getall()
        valores = []
        for texto in precios_encontrados:
            num = self.limpiar_precio(texto)
            if num > 1000: # Filtrar basura del DOM que no sean precios reales
                valores.append(num)
        
        if valores:
            # El valor más alto es el precio original, el más bajo es la oferta
            item['precio'] = self._formatear_precio(max(valores))
            item['promocion'] = self._formatear_precio(min(valores))
        else:
            item['precio'] = "Precio no disponible"
            item['promocion'] = "Precio no disponible"

        # 4. Limpieza de Imagen (Filtra logos de envío y placeholders)
        img_url = p.css('img[src*="vtexassets"]::attr(src)').get() or \
                  p.css('img[data-src*="vtexassets"]::attr(data-src)').get() or \
                  p.css('img[class*="productCard"]::attr(src)').get()
        
        if img_url:
            if img_url.startswith('//'):
                img_url = 'https:' + img_url
            # Si capturó un logo de envío, intentamos buscar una imagen alternativa en el mismo bloque
            if "envio" in img_url.lower() or "logo" in img_url.lower():
                alt = p.xpath('.//img[contains(@src, "vtexassets")]/@src').get()
                if alt: img_url = 'https:' + alt if alt.startswith('//') else alt

        item['imagen'] = img_url
        item['enlace'] = response.urljoin(p.css('a::attr(href)').get())
        item['tienda'] = 'Éxito'
        item['categoria'] = self.categorizar_simple(item['nombre']) if item['nombre'] else 'tecnologia'
        
        return item

    async def errback_close_page(self, failure):
        page = failure.request.meta.get("playwright_page")
        if page:
            await page.close()

    def limpiar_precio(self, texto):
        if texto:
            nums = ''.join(filter(str.isdigit, str(texto)))
            return int(nums) if nums else 0
        return 0

    def _formatear_precio(self, valor):
        if valor and valor > 0:
            return f"$ {valor:,.0f}".replace(",", ".") + " COP"
        return "Precio no disponible"

    def categorizar_simple(self, nombre):
        n = nombre.lower()
        if any(w in n for w in ['computador', 'portátil', 'laptop']): return 'computadores'
        if any(w in n for w in ['celular', 'smartphone', 'iphone']): return 'celulares'
        if any(w in n for w in ['televisor', 'tv', 'smart tv']): return 'pantallas'
        if any(w in n for w in ['audifonos', 'diadema', 'parlante']): return 'audio'
        return 'tecnologia'