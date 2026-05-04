import scrapy
from scrapy_playwright.page import PageMethod
from alkosto_project.items import TouretItem
import asyncio
import platform

if platform.system() == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


class TauretSpider(scrapy.Spider):
    name = 'tauret'
    allowed_domains = ['tauretcomputadores.com']

    CATEGORIAS = [
        ('computadores', 'https://tauretcomputadores.com/products/category?cat=computadores'),
        ('gamers',       'https://tauretcomputadores.com/products/category?cat=gamers'),
        ('portatiles',   'https://tauretcomputadores.com/products/category?cat=portatiles'),
        ('pantallas',    'https://tauretcomputadores.com/products/category?cat=pantallas'),
        ('perifericos',  'https://tauretcomputadores.com/products/category?cat=perifericos'),
    ]

    custom_settings = {
        'CONCURRENT_REQUESTS': 1,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 1,
        'DUPEFILTER_CLASS': 'scrapy.dupefilters.BaseDupeFilter',
    }

    def start_requests(self):
        categoria_destino, url_base = self.CATEGORIAS[0]
        self.logger.info(f'\n{"="*60}')
        self.logger.info(f'INICIANDO: {url_base} -> [{categoria_destino.upper()}] (1/{len(self.CATEGORIAS)})')
        self.logger.info(f'{"="*60}')
        yield self._make_request(url_base, categoria_destino, url_base, pagina=1, idx_categoria=0, enlaces_pagina_anterior=set())

    def _make_request(self, url, categoria_destino, url_base, pagina, idx_categoria, enlaces_pagina_anterior):
        url_paginada = url_base if pagina == 1 else f"{url_base}&page={pagina}"
        return scrapy.Request(
            url=url_paginada,
            meta={
                'playwright': True,
                'playwright_page_methods': [
                    PageMethod('wait_for_selector', 'ul.listado-productos', timeout=15000),
                    PageMethod('evaluate', """
                        async () => {
                            window.scrollTo(0, document.body.scrollHeight);
                            await new Promise(r => setTimeout(r, 2000));
                            window.scrollTo(0, 0);
                            await new Promise(r => setTimeout(r, 500));
                        }
                    """),
                    PageMethod('wait_for_timeout', 2000),
                ],
                'categoria_destino':        categoria_destino,
                'url_base':                 url_base,
                'pagina':                   pagina,
                'idx_categoria':            idx_categoria,
                'enlaces_pagina_anterior':  enlaces_pagina_anterior,
            },
            callback=self.parse_category,
            dont_filter=True,
        )

    def parse_category(self, response):
        categoria_destino          = response.meta['categoria_destino']
        url_base                   = response.meta['url_base']
        pagina                     = response.meta['pagina']
        idx_categoria              = response.meta['idx_categoria']
        enlaces_pagina_anterior    = response.meta['enlaces_pagina_anterior']

        productos = response.css('ul.listado-productos li')
        self.logger.info(f'Pagina {pagina}: {len(productos)} productos [{categoria_destino}]')

        # --- Detectar loop: si los enlaces son iguales a la pagina anterior, parar ---
        enlaces_actuales = set(
            p.css('div.name a::attr(href)').get('') for p in productos
        )
        if enlaces_actuales and enlaces_actuales == enlaces_pagina_anterior:
            self.logger.info(f'  -> Contenido identico a pagina anterior. Fin de [{categoria_destino}]')
            self._avanzar_categoria(idx_categoria, pagina)
            yield from self._request_siguiente_categoria(idx_categoria, pagina)
            return

        for idx, producto in enumerate(productos):
            try:
                nombre = producto.css('div.name h2::text').get('').strip()
                if not nombre:
                    continue

                enlace_rel = producto.css('div.name a::attr(href)').get('').strip()
                enlace     = response.urljoin(enlace_rel)
                imagen     = producto.css('a.image-link img::attr(src)').get('').strip()
                precio_raw = producto.css('span.price1::text').get('').strip()

                categoria_final = self.categorizar(nombre, categoria_destino)

                item = TouretItem()
                item['nombre']    = nombre
                item['precio']    = self.formatear_precio(precio_raw)
                item['enlace']    = enlace
                item['marca']     = self.extraer_marca(nombre)
                item['imagen']    = imagen
                item['categoria'] = categoria_final
                item['tienda']    = 'Tauret Computadores'
                self.logger.info(f'  #{idx} [{categoria_final}] {nombre[:45]} | {item["precio"]}')
                yield item

            except Exception as e:
                self.logger.error(f'Error #{idx}: {e}')

        # --- Paginacion: detectar si hay siguiente pagina real ---
        todas  = response.css('ul.pagination li.number a.page-link::text').getall()
        activa = response.css('ul.pagination li.active a.page-link::text').get(str(pagina))
        try:
            numeros       = [int(x.strip()) for x in todas if x.strip().isdigit()]
            pagina_actual = int(activa.strip()) if activa.strip().isdigit() else pagina
            hay_siguiente = bool(numeros) and pagina_actual < max(numeros)
        except Exception:
            hay_siguiente = False

        if productos and hay_siguiente:
            siguiente = pagina + 1
            self.logger.info(f'  -> pagina {siguiente}')
            yield self._make_request(
                url_base, categoria_destino, url_base,
                siguiente, idx_categoria,
                enlaces_pagina_anterior=enlaces_actuales
            )
            return

        # --- Categoria terminada ---
        self.logger.info(f'URL [{categoria_destino}] completada en {pagina} paginas')
        yield from self._request_siguiente_categoria(idx_categoria, pagina)

    def _request_siguiente_categoria(self, idx_categoria, pagina_final):
        idx_siguiente = idx_categoria + 1
        if idx_siguiente < len(self.CATEGORIAS):
            cat_sig, url_sig = self.CATEGORIAS[idx_siguiente]
            self.logger.info(f'\n{"="*60}')
            self.logger.info(f'INICIANDO: {url_sig} -> [{cat_sig.upper()}] ({idx_siguiente+1}/{len(self.CATEGORIAS)})')
            self.logger.info(f'{"="*60}')
            yield self._make_request(
                url_sig, cat_sig, url_sig,
                pagina=1, idx_categoria=idx_siguiente,
                enlaces_pagina_anterior=set()
            )
        else:
            self.logger.info('✅ TODAS LAS CATEGORIAS COMPLETADAS.')

    def categorizar(self, nombre, categoria_destino):
        n = nombre.lower()
        if categoria_destino == 'computadores':
            return 'computadores'
        if categoria_destino == 'portatiles':
            return 'computadores'
        if categoria_destino == 'pantallas':
            return 'pantallas'
        if categoria_destino == 'gamers':
            if any(k in n for k in ('control', 'joystick', 'mando', 'ps5', 'ps4', 'ps3', 'xbox', 'nintendo')):
                return 'consolas'
            return 'otros'
        if categoria_destino == 'perifericos':
            if any(k in n for k in (
                'altavoz', 'altavoces', 'parlante', 'speaker', 'bocina',
                'audifono', 'audifonos', 'auricular', 'headset', 'earphone',
                'soundbar', 'barra de sonido', 'subwoofer'
            )):
                return 'audio'
            return 'otros'
        return 'otros'

    def formatear_precio(self, texto):
        if not texto:
            return '0 COP'
        solo = ''.join(filter(str.isdigit, texto))
        try:
            return f"{int(solo):,}".replace(',', '.') + ' COP'
        except ValueError:
            return '0 COP'

    def extraer_marca(self, nombre):
        u = nombre.upper()
        for m in [
            'HP', 'LENOVO', 'ASUS', 'APPLE', 'ACER', 'DELL', 'SAMSUNG', 'LG',
            'XIAOMI', 'MOTOROLA', 'INTEL', 'AMD', 'GIGABYTE', 'MSI', 'CORSAIR',
            'RAZER', 'LOGITECH', 'STEELSERIES', 'HYPERX', 'NVIDIA', 'TAURET',
            'XPG', 'GAMDIAS', 'VIEWSONIC', 'BENQ', 'AOC', 'SONY', 'JBL',
            'EDIFIER', 'CREATIVE', 'ANKER', 'SENNHEISER', 'JABRA', 'PIONEER',
        ]:
            if m in u:
                return m
        return 'GENERICA'