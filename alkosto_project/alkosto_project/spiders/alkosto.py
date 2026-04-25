import scrapy
from scrapy_playwright.page import PageMethod
from alkosto_project.items import AlkostoProjectItem
import sys
import asyncio

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

class AlkostoSpider(scrapy.Spider):
    name = 'alkosto'
    
    def start_requests(self):
        # URLs de las categorías principales
        urls = [
            'https://www.alkosto.com/computadores-tablet/c/BI_COMP_ALKOS',
            'https://www.alkosto.com/celulares/smartphones/c/BI_101_ALKOS',
            'https://www.alkosto.com/tv-video/televisores/c/BI_120_ALKOS',
            'https://www.alkosto.com/computadores-tablet/impresoras-suministros/c/BI_105_ALKOS'
        ]
        
        # Script para manejar el scroll infinito y el botón "Cargar más"
        load_more_script = """
        async () => {
            while (true) {
                const button = document.querySelector('button.js-load-more');
                if (button && !button.disabled && button.offsetParent !== null) {
                    button.scrollIntoView();
                    button.click();
                    await new Promise(r => setTimeout(r, 3500));
                } else {
                    break;
                }
            }
        }
        """
        
        for url in urls:
            yield scrapy.Request(
                url,
                meta={
                    "playwright": True,
                    "playwright_include_page": True,
                    "playwright_page_methods": [
                        PageMethod("wait_for_selector", "li.ais-InfiniteHits-item"),
                        PageMethod("evaluate", load_more_script),
                        PageMethod("wait_for_timeout", 5000),
                    ],
                }
            )

    def parse(self, response):
        productos = response.css('li.ais-InfiniteHits-item')
        
        for p in productos:
            nombre = p.css('.js-algolia-product-title::text').get() or p.css('h3::text').get()

            if nombre:
                item = AlkostoProjectItem()
                
                img_url = p.css('img::attr(src)').get() or p.css('img::attr(data-src)').get()
                item['imagen'] = response.urljoin(img_url) if img_url else None
                
                # 2. Extracción de Marca
                marca_directa = p.css('.product_item_information_brand::text').get()
                marcas_comunes = [
                    'HP', 'LENOVO', 'ASUS', 'APPLE', 'ACER', 'DELL', 'SAMSUNG', 'LG',
                    'XIAOMI', 'MOTOROLA', 'HUAWEI', 'REALME', 'OPPO', 'EPSON', 'CANON', 'KALLEY', 'VIVO'
                ]
                
                nombre_upper = nombre.upper()
                marca_encontrada = next((m for m in marcas_comunes if m in nombre_upper), None)
                
                if marca_directa and marca_directa.strip():
                    item['marca'] = marca_directa.strip().upper()
                elif marca_encontrada:
                    item['marca'] = marca_encontrada
                else:
                    item['marca'] = "GENÉRICA"

                # 3. Datos básicos
                precio_raw = p.css('span.price::text').get() or p.css('.ais-hit--price::text').get()
                link = p.css('a::attr(href)').get()
                
                item['nombre'] = nombre.strip()
                item['precio'] = f"{self.limpiar_precio(precio_raw):,.0f}".replace(",", ".") + " COP"
                item['enlace'] = response.urljoin(link) if link else None
                item['tienda'] = 'Alkosto'
                
                # 4. Categorización Corregida
                item['categoria'] = self.categorizar(item['nombre'], item['enlace'], item['imagen'])
                
                yield item

    def limpiar_precio(self, texto):
        solo_numeros = ''.join(filter(str.isdigit, str(texto or '')))
        return int(solo_numeros) if solo_numeros else 0

    def categorizar(self, nombre, enlace, imagen):
        """
        Clasifica el producto basándose en el texto del nombre y el enlace.
        """
        t = (str(nombre) + ' ' + str(enlace)).lower()
        
        # Prioridad 1: Celulares
        if any(k in t for k in ['celular', 'smartphone', 'iphone', 'telefono', 'teléfono', 'moto g', 'galaxy a']):
            return 'celulares'
        
        # Prioridad 2: Pantallas / TV
        if any(k in t for k in ['tv', 'televisor', 'monitor', 'pantalla']):
            return 'pantallas'
        
        # Prioridad 3: Impresoras
        if any(k in t for k in ['impresora', 'multifuncional', 'epson', 'canon']):
            return 'impresoras'
        
        # Prioridad 4: Tablets
        if any(k in t for k in ['tablet', 'tableta', 'ipad']):
            return 'tablets'
        
        # Prioridad 5: Computadores
        if any(k in t for k in ['laptop', 'notebook', 'portátil', 'computador', 'pc']):
            return 'computadores'
        
        return 'otros'