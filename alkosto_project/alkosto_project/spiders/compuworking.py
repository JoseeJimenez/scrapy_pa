import scrapy
from scrapy_playwright.page import PageMethod
from alkosto_project.items import AlkostoProjectItem
import sys
import asyncio
import platform

if platform.system() == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# este spider es el mas duro que todos 99%%
class ComputerworkingSpider(scrapy.Spider):
    name = 'compuworking'
    allowed_domains = ['computerworking.com.co']

    CATEGORIAS = [
        ('portatiles',        'https://www.computerworking.com.co/categorias/222/true'),
        ('computadores',      'https://www.computerworking.com.co/categorias/310/true'),
        ('accesorios_pc',     'https://www.computerworking.com.co/categorias/169/true'),
        ('mouse_teclado',     'https://www.computerworking.com.co/categorias/124/true'),
        ('celulares_tablets', 'https://www.computerworking.com.co/categorias/230/true'),
        ('televisores',       'https://www.computerworking.com.co/categorias/390/true'),
        ('audio',             'https://www.computerworking.com.co/categorias/241/true'),
        ('consolas',          'https://www.computerworking.com.co/categorias/243/true'),
    ]

    custom_settings = {
        'CONCURRENT_REQUESTS': 1,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 1,
        'DUPEFILTER_CLASS': 'scrapy.dupefilters.BaseDupeFilter',
    }

    def start_requests(self):
        nombre, url_base = self.CATEGORIAS[0]
        self.logger.info(f'\n{"="*60}')
        self.logger.info(f'INICIANDO CATEGORIA: {nombre.upper()} (1/{len(self.CATEGORIAS)})')
        self.logger.info(f'{"="*60}')
        yield self._make_request(url_base + '/1', nombre, url_base, pagina=1, idx_categoria=0)

    def _make_request(self, url, categoria_nombre, url_base, pagina, idx_categoria):
        return scrapy.Request(
            url=url,
            meta={
                'playwright': True,
                # Sin playwright_include_page — Scrapy-Playwright cierra la pagina automaticamente
                'playwright_page_methods': [
                    PageMethod('wait_for_selector', 'div.col-sm-3 div.productBox', timeout=15000),
                    PageMethod('evaluate', """
                        async () => {
                            window.scrollTo(0, document.body.scrollHeight);
                            await new Promise(r => setTimeout(r, 2000));
                            window.scrollTo(0, 0);
                            await new Promise(r => setTimeout(r, 1000));
                        }
                    """),
                    PageMethod('wait_for_timeout', 3000),
                ],
                'categoria_url': categoria_nombre,
                'url_base': url_base,
                'pagina': pagina,
                'idx_categoria': idx_categoria,
            },
            callback=self.parse_category,
            dont_filter=True,
        )

    def parse_category(self, response):
        categoria_url = response.meta['categoria_url']
        url_base      = response.meta['url_base']
        pagina        = response.meta['pagina']
        idx_categoria = response.meta['idx_categoria']

        productos = response.css('div.col-sm-3 div.productBox')
        self.logger.info(f'Pagina {pagina}: {len(productos)} productos en {categoria_url}')

        if not productos:
            self.logger.warning(f'Sin productos en {categoria_url} p{pagina}')

        for idx, producto in enumerate(productos):
            try:
                nombre = (
                    producto.css('div.productCaption h5::text').get('') or
                    producto.css('div.productCaption h5 span::text').get('')
                ).strip()
                if not nombre:
                    continue

                enlace     = (producto.css('div.productCaption a::attr(href)').get('') or
                               producto.css('div.productImage a::attr(href)').get('') ).strip()
                imagen     = producto.css('div.productImage img::attr(src)').get('').strip()
                precio_raw = (producto.css('div.productCaption h3::text').get('') or
                               producto.css('h3::text').get('') ).strip()

                item = AlkostoProjectItem()
                item['nombre']    = nombre
                item['precio']    = self.formatear_precio(precio_raw)
                item['enlace']    = response.urljoin(enlace)
                item['marca']     = self.extraer_marca(nombre)
                item['imagen']    = response.urljoin(imagen)
                item['categoria'] = self.categorizar(nombre, enlace, categoria_url)
                item['tienda']    = 'Computerworking'
                self.logger.info(f'  #{idx} {nombre[:45]} | {item["precio"]}')
                yield item

            except Exception as e:
                self.logger.error(f'Error #{idx}: {e}')

        # --- Siguiente pagina de esta misma categoria ---
        next_href = response.css('a.next::attr(href)').get()
        if productos and next_href:
            siguiente_pagina = pagina + 1
            self.logger.info(f'  -> pagina {siguiente_pagina} de {categoria_url}')
            yield self._make_request(
                f"{url_base}/{siguiente_pagina}",
                categoria_url, url_base,
                pagina=siguiente_pagina,
                idx_categoria=idx_categoria,
            )
            return

        # --- Categoria terminada: pasar a la siguiente ---
        self.logger.info(f'CATEGORIA {categoria_url.upper()} COMPLETADA ({pagina} paginas)')
        idx_siguiente = idx_categoria + 1
        if idx_siguiente < len(self.CATEGORIAS):
            nombre_sig, url_sig = self.CATEGORIAS[idx_siguiente]
            self.logger.info(f'\n{"="*60}')
            self.logger.info(f'INICIANDO CATEGORIA: {nombre_sig.upper()} ({idx_siguiente+1}/{len(self.CATEGORIAS)})')
            self.logger.info(f'{"="*60}')
            yield self._make_request(
                url_sig + '/1',
                nombre_sig, url_sig,
                pagina=1,
                idx_categoria=idx_siguiente,
            )
        else:
            self.logger.info('TODAS LAS CATEGORIAS COMPLETADAS.')

    def formatear_precio(self, texto):
        if not texto:
            return '0 COP'
        texto = texto.replace('$', '').replace(' ', '').strip()
        puntos = texto.count('.')
        comas  = texto.count(',')
        if comas == 1 and puntos == 0:
            texto = texto.replace(',', '')
        elif puntos >= 1 and comas == 0:
            texto = texto.replace('.', '')
        elif puntos == 1 and comas == 1:
            if texto.rindex(',') > texto.rindex('.'):
                texto = texto.replace('.', '').replace(',', '.')
            else:
                texto = texto.replace(',', '')
        solo = ''.join(filter(str.isdigit, texto))
        try:
            return f"{int(solo):,}".replace(',', '.') + ' COP'
        except ValueError:
            return '0 COP'

    def extraer_marca(self, nombre):
        u = nombre.upper()
        for m in [
            'HP','LENOVO','ASUS','APPLE','ACER','DELL','SAMSUNG','LG','XIAOMI',
            'MOTOROLA','HUAWEI','REALME','OPPO','EPSON','CANON','KALLEY','VIVO',
            'INTEL','AMD','RYZEN','CORE','GENIUS','LOGITECH','COUGAR','EASY',
            'FORZA','JAITECH','KAISE','MACSYSTEM','MACON','NICOMAR','POWEST',
            'UNITEC','VARIOS','WACOM','WATTANA','DRACO','DIGITAL','POWER GROUP',
            'JALTECH','NUC','GAMER','TORRE','MINI PC','HYUNDAI','HISENSE','SONY',
            'PANASONIC','SHARP','TCL','PHILIPS','SENNHEISER','BOSE','BEATS','JBL',
            'SKULLCANDY','PLANTRONICS','CORSAIR','RAZER','STEELSERIES','TURTLE BEACH',
        ]:
            if m in u:
                return m
        return 'GENERICA'

    def categorizar(self, nombre, enlace, categoria_url):
        n = nombre.lower().replace(' ', '')
        if categoria_url == 'celulares_tablets':
            return 'tablets' if any(k in n for k in ('tablet','tableta','ipad')) else 'celulares'
        if categoria_url == 'televisores':
            return 'pantallas'
        if categoria_url in ('audio', 'consolas'):
            return categoria_url
        if 'gamer' in n:
            return 'computadores'
        if categoria_url == 'computadores':
            return 'computadores'
        if categoria_url == 'portatiles':
            return 'portatiles'
        if any(k in n for k in ('portátil','laptop','notebook')):
            return 'portatiles'
        if 'accesorios' in n:
            return 'accesorios_pc'
        if any(k in n for k in ('mouse','teclado')):
            return 'mouse_teclado'
        if categoria_url == 'accesorios_pc':
            return 'accesorios_pc'
        if categoria_url == 'mouse_teclado':
            return 'mouse_teclado'
        return 'otros'