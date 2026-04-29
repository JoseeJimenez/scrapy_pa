import scrapy
from scrapy_playwright.page import PageMethod
from alkosto_project.items import ExitoProjectItem

class ExitoSpider(scrapy.Spider):
    name = 'exito'
    
    custom_settings = {
        'CONCURRENT_REQUESTS': 1, 
        'DOWNLOAD_DELAY': 2,
        'DOWNLOAD_TIMEOUT': 60, # Evita que el spider se quede pegado horas
        'PLAYWRIGHT_BROWSER_TYPE': 'chromium',
        # 'PLAYWRIGHT_LAUNCH_OPTIONS': {"headless": False}, # Cambia a False si quieres ver qué hace el navegador
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
        # Seleccionamos todos los contenedores de productos
        productos = response.css('article.productCard_productCard__M0677')
        
        self.logger.info(f"Se encontraron {len(productos)} productos en la página actual.")

        for p in productos:
            item = self._extraer_producto(p, response)
            if item['nombre']:
                yield item

        # Lógica de Paginación mejorada
        # Buscamos el botón "Siguiente" por el atributo aria-label o la clase
        next_page = response.css('a[aria-label="Siguiente"]::attr(href)').get() or \
                    response.css('a.Pagination_nextPreviousLink__f7_2J::attr(href)').get()
        
        if next_page:
            self.logger.info(f"Navegando a la siguiente página: {next_page}")
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
                # 1. Esperar a que el esqueleto de la página cargue
                PageMethod("wait_for_selector", "article.productCard_productCard__M0677", timeout=15000),
                
                # 2. Scroll quirúrgico: baja rápido pero con pausas para disparar el lazy load
                PageMethod("evaluate", """
                    async () => {
                        const delay = ms => new Promise(resolve => setTimeout(resolve, ms));
                        for (let i = 0; i < document.body.scrollHeight; i += 1200) {
                            window.scrollTo(0, i);
                            await delay(150); 
                        }
                        window.scrollTo(0, 0);
                        await delay(500);
                    }
                """),
                
                # 3. Pausa final de renderizado
                PageMethod("wait_for_timeout", 3000), 
            ],
        }

    def _extraer_producto(self, p, response):
        item = ExitoProjectItem()
        
        # Nombre y Marca
        item['nombre'] = p.css('h3.styles_name__qQJiK::text').get()
        item['marca'] = p.css('h3.styles_brand__IdJcB::text').get()
        
        # Precio con fallback
        precio_raw = p.css('div.styles_price__S9_q3::text').get() or \
                     p.css('p[data-fs-container-price-others="true"]::text').get()
        
        valor_limpio = self.limpiar_precio(precio_raw)
        item['precio'] = self._formatear_precio(valor_limpio)

        # Lógica de Imagen (Priorizando vtexassets)
        img_url = p.css('img[src*="vtexassets"]::attr(src)').get() or \
                  p.css('img[data-src*="vtexassets"]::attr(data-src)').get() or \
                  p.css('div.styles_productCardImage__RBIdI img::attr(src)').get()

        # Limpieza de URL de imagen
        if img_url:
            if img_url.startswith('//'):
                img_url = 'https:' + img_url
            # Si es un logo de envío o similar, intentamos buscar más profundo
            if any(x in img_url.lower() for x in ['envio', 'logo', 'placeholder']):
                alt_img = p.xpath('.//img[contains(@src, "vtexassets")]/@src').get()
                if alt_img:
                    img_url = 'https:' + alt_img if alt_img.startswith('//') else alt_img

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