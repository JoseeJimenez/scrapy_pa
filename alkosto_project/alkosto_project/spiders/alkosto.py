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
        # Bucle para recorrer computadores y celulares
        urls = [
            'https://www.alkosto.com/computadores-tablet/c/BI_COMP_ALKOS',
            'https://www.alkosto.com/celulares/smartphones/c/BI_101_ALKOS'
        ]
        
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
            item = AlkostoProjectItem()
            
            nombre = p.css('.js-algolia-product-title::text').get() or p.css('h3::text').get()
            
            if nombre:
                # 1. Extracción de Marca con lógica de respaldo inteligente
                marca_directa = p.css('.product_item_information_brand::text').get()
                marcas_comunes = [
                    'HP', 'LENOVO', 'ASUS', 'APPLE', 'ACER', 'DELL', 'SAMSUNG', 
                    'XIAOMI', 'MOTOROLA', 'HUAWEI', 'REALME', 'OPPO', 'IPHONE', 'VIVO'
                ]
                
                marca_encontrada = next((m for m in marcas_comunes if m in nombre.upper()), None)
                
                if marca_directa and marca_directa.strip():
                    item['marca'] = marca_directa.strip().upper()
                elif marca_encontrada:
                    item['marca'] = marca_encontrada
                else:
                    item['marca'] = "GENÉRICA"

                # 2. Datos básicos de precio y enlace
                precio_raw = p.css('span.price::text').get() or p.css('.ais-hit--price::text').get()
                link = p.css('a::attr(href)').get()
                
                valor_numerico = self.limpiar_precio(precio_raw)
                item['nombre'] = nombre.strip()
                item['precio'] = f"{valor_numerico:,.0f}".replace(",", ".") + " COP"
                item['enlace'] = response.urljoin(link) if link else None
                item['tienda'] = 'Alkosto'
                
                # 3. Categorización (Computadores, Tablets, Celulares y Otros)
                item['categoria'] = self.categorizar(item['nombre'], item['enlace'])
                
                yield item

    def limpiar_precio(self, texto):
        if texto:
            solo_numeros = ''.join(filter(str.isdigit, str(texto)))
            return int(solo_numeros) if solo_numeros else 0
        return 0

    def categorizar(self, nombre, enlace):
        t = (str(nombre) + ' ' + str(enlace)).lower()
        
        if any(k in t for k in ['celular', 'smartphone', 'iphone', 'telefono', 'teléfono']):
            return 'celulares'
        if any(k in t for k in ['tablet', 'tableta', 'ipad']):
            return 'tablets'
        if any(k in t for k in ['laptop', 'notebook', 'portátil', 'portatil', 'computador', 'pc', 'desktop', 'all in one']):
            return 'computadores'
        
        return 'otros'