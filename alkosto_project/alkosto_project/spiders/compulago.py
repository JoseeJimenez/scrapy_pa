import scrapy
import re
import sys
import asyncio
from scrapy_playwright.page import PageMethod
from alkosto_project.items import CompulagoItem

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


class CompulagoSpider(scrapy.Spider):
    name = 'compulago'

    CATEGORY_MAP = {
        'portatiles':                      'computadores',
        'tablets-y-celulares-corporativo': 'celulares_tablets',
        'imagen-y-video-corporativo':      'imagen_video',
        'impresoras-corporativo':          'impresoras',
    }

    MARCAS_COMUNES = [
        'HP', 'LENOVO', 'ASUS', 'APPLE', 'ACER', 'DELL', 'SAMSUNG', 'LG',
        'XIAOMI', 'MOTOROLA', 'HUAWEI', 'REALME', 'OPPO', 'EPSON', 'CANON',
        'KALLEY', 'VIVO', 'BROTHER', 'XEROX', 'RICOH', 'KYOCERA',
        'SONY', 'VIEWSONIC', 'BENQ', 'AOC', 'LOGITECH', 'GARMIN', 'MSI',
        'COMPUMAX', 'INTEL',
    ]

    load_more_script = """
    async () => {
        let intentos = 0;
        while (intentos < 30) {
            await new Promise(r => setTimeout(r, 2500));
            const btn = document.querySelector(
                'a.load_more_products, button.load_more_products, ' +
                'a[class*="load_more"], button[class*="load_more"]'
            );
            if (btn && btn.offsetParent !== null) {
                btn.scrollIntoView({ behavior: 'smooth', block: 'center' });
                btn.click();
                intentos++;
            } else {
                break;
            }
        }
    }
    """

    def start_requests(self):
        urls = [
            'https://compulago.com/categoria/portatiles/',
            'https://compulago.com/categoria/tablets-y-celulares-corporativo/',
            'https://compulago.com/categoria/imagen-y-video-corporativo/',
            'https://compulago.com/categoria/impresoras-corporativo/',
        ]
        for url in urls:
            yield scrapy.Request(
                url,
                meta={
                    'playwright': True,
                    'playwright_include_page': True,
                    'playwright_page_methods': [
                        PageMethod('set_default_timeout', 60000),
                        PageMethod('wait_for_selector', 'a[href*="/producto/"]'),
                        PageMethod('evaluate', self.load_more_script),
                        PageMethod('wait_for_timeout', 3000),
                    ],
                },
                callback=self.parse,
            )

    def parse(self, response):
        # La estructura Elementor es:
        # div.elementor-element (fila de producto)
        #   div.productdescriptioncomputo > div > div > a[href=/producto/] -> NOMBRE
        #   div.elementor-element (precio) > div > p.elementor-heading-title > span.woocommerce-Price-amount -> PRECIO
        #   div.elementor-element (imagen) > div > ... > img -> IMAGEN
        #   div.elementor-element (marca) > div > p.elementor-heading-title -> MARCA

        # Estrategia: iterar sobre cada bloque de fila de producto
        # El contenedor de cada producto es un div con clase e-con-full que agrupa todo
        filas = response.css('div.e-con-full, div[class*="e-con"][class*="e-child"]')

        items_extraidos = []
        vistos = set()

        for fila in filas:
            # Buscar el enlace /producto/ dentro de esta fila
            a = fila.css('a[href*="/producto/"]')
            if not a:
                continue

            href = a.attrib.get('href', '')
            if not href or href in vistos:
                continue
            vistos.add(href)

            # Nombre: texto del <a>
            nombre = ' '.join(a.css('::text').getall()).strip()
            if not nombre:
                continue

            # Precio: span.woocommerce-Price-amount dentro de la misma fila
            precio_raw = fila.css('span.woocommerce-Price-amount.amount::text').get()

            # Imagen: img dentro de la misma fila
            img_url = (
                fila.css('img::attr(src)').get()
                or fila.css('img::attr(data-src)').get()
            )

            items_extraidos.append((nombre, precio_raw, href, img_url))

        # Fallback: si no encontramos nada con e-con-full,
        # emparejar nombres y precios por posicion
        if not items_extraidos:
            nombres = response.css('a[href*="/producto/"]')
            precios = response.css('span.woocommerce-Price-amount.amount')

            vistos = set()
            enlaces_unicos = []
            for a in nombres:
                href = a.attrib.get('href', '')
                nombre = ' '.join(a.css('::text').getall()).strip()
                if href and href not in vistos and nombre:
                    vistos.add(href)
                    enlaces_unicos.append((nombre, href, a))

            for i, (nombre, href, a) in enumerate(enlaces_unicos):
                precio_raw = precios[i].css('::text').get() if i < len(precios) else None
                img_url = None
                items_extraidos.append((nombre, precio_raw, href, img_url))

        self.logger.info(f'[Compulago] {response.url} — productos a guardar: {len(items_extraidos)}')

        for nombre, precio_raw, href, img_url in items_extraidos:
            nombre_upper = nombre.upper()
            marca = next((m for m in self.MARCAS_COMUNES if m in nombre_upper), 'GENERICA')

            item = CompulagoItem()
            item['nombre']    = nombre
            item['precio']    = self._formatear_precio(precio_raw)
            item['marca']     = marca
            item['categoria'] = self._categorizar(response.url, nombre, href)
            item['enlace']    = href
            item['imagen']    = response.urljoin(img_url) if img_url else None
            item['tienda']    = 'Compulago'
            yield item

    def _formatear_precio(self, texto):
        if not texto:
            return 'N/D'
        solo_numeros = re.sub(r'[^\d]', '', str(texto))
        if not solo_numeros:
            return 'N/D'
        return f"{int(solo_numeros):,}".replace(",", ".") + " COP"

    def _categorizar(self, url, nombre, enlace):
        for slug, cat in self.CATEGORY_MAP.items():
            if slug in url:
                return cat
        t = (nombre + ' ' + enlace).lower()
        if any(k in t for k in ['celular', 'smartphone', 'iphone', 'moto g', 'galaxy']):
            return 'celulares_tablets'
        if any(k in t for k in ['tablet', 'tableta', 'ipad', 'smartwatch']):
            return 'celulares_tablets'
        if any(k in t for k in ['impresora', 'multifuncional']):
            return 'impresoras'
        if any(k in t for k in ['camara', 'cámara', 'proyector', 'video']):
            return 'imagen_video'
        if any(k in t for k in ['laptop', 'portátil', 'portatil', 'notebook', 'computador']):
            return 'computadores'
        return 'otros'