import scrapy
from scrapy_playwright.page import PageMethod
from alkosto_project.items import AlkostoProjectItem # Importamos el item
import sys
import asyncio

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

class AlkostoSpider(scrapy.Spider):
    name = 'alkosto'
    
    def start_requests(self):
        url = 'https://www.alkosto.com/computadores-tablet/c/BI_COMP_ALKOS'
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
        yield scrapy.Request(
            url,
            meta={
                "playwright": True,
                "playwright_include_page": True,
                "playwright_page_methods": [
                    PageMethod("wait_until", "networkidle"),
                    PageMethod("wait_for_selector", "li.ais-InfiniteHits-item"),
                    PageMethod("evaluate", load_more_script),
                    PageMethod("wait_for_timeout", 5000),
                ],
            }
        )

    def parse(self, response):
        productos = response.css('li.ais-InfiniteHits-item')
        for p in productos:
            item = AlkostoProjectItem() # Instanciamos el Item
            
            nombre = p.css('.js-algolia-product-title::text').get() or p.css('h3::text').get()
            precio_raw = p.css('span.price::text').get() or p.css('.ais-hit--price::text').get()
            link = p.css('a::attr(href)').get()

            if nombre:
                valor_numerico = self.limpiar_precio(precio_raw)
                item['nombre'] = nombre.strip()
                item['precio'] = f"{valor_numerico:,.0f}".replace(",", ".") + " COP"
                item['enlace'] = response.urljoin(link) if link else None
                item['tienda'] = 'Alkosto'
                yield item # Enviamos el Item al Pipeline

    def limpiar_precio(self, texto):
        if texto:
            solo_numeros = ''.join(filter(str.isdigit, str(texto)))
            return int(solo_numeros) if solo_numeros else 0
        return 0