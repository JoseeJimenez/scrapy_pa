import scrapy
from scrapy_playwright.page import PageMethod
from alkosto_project.items import AlkostoProjectItem
import sys
import asyncio

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

class ComputerworkingSpider(scrapy.Spider):
    name = 'compuworking'
    allowed_domains = ['computerworking.com.co']
    
    def start_requests(self):
        # URLs de categorías de computerworking
        urls = [
            'https://www.computerworking.com.co/categoria/computadores',
            'https://www.computerworking.com.co/categoria/celulares',
            'https://www.computerworking.com.co/categoria/tablets',
            # ... más categorías
        ]
        
        load_more_script = """
        async () => {
            // Script específico para computerworking
            while (true) {
                const button = document.querySelector('button.load-more-selector');
                if (button && !button.disabled) {
                    button.click();
                    await new Promise(r => setTimeout(r, 2000));
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
                        PageMethod("wait_for_selector", "div.product-item"),
                        PageMethod("evaluate", load_more_script),
                    ],
                }
            )
    
    def parse(self, response):
        productos = response.css('div.product-item')  # Selector específico
        
        for p in productos:
            nombre = p.css('h2.product-name::text').get()
            
            if nombre:
                item = AlkostoProjectItem()
                item['nombre'] = nombre.strip()
                item['precio'] = self.limpiar_precio(p.css('span.price::text').get())
                item['enlace'] = response.urljoin(p.css('a::attr(href)').get())
                item['tienda'] = 'Computerworking'
                item['marca'] = self.extraer_marca(nombre)
                item['imagen'] = p.css('img::attr(src)').get()
                item['categoria'] = self.categorizar(nombre, item['enlace'])
                
                yield item
    
    def limpiar_precio(self, texto):
        solo_numeros = ''.join(filter(str.isdigit, str(texto or '')))
        return int(solo_numeros) if solo_numeros else 0
    
    def extraer_marca(self, nombre):
        marcas = ['HP', 'LENOVO', 'ASUS', 'DELL', 'APPLE', 'SAMSUNG', 'LG', 'ACER']
        return next((m for m in marcas if m in nombre.upper()), "GENÉRICA")
    
    def categorizar(self, nombre, enlace):
        t = (nombre + ' ' + enlace).lower()
        if 'celular' in t or 'smartphone' in t: return 'celulares'
        if 'tablet' in t: return 'tablets'
        if 'laptop' in t or 'notebook' in t: return 'computadores'
        if 'monitor' in t: return 'pantallas'
        return 'otros'