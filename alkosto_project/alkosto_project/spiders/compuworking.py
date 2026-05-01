import scrapy
from scrapy_playwright.page import PageMethod
from alkosto_project.items import ComputerworkingItem
import asyncio
import platform

if platform.system() == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


class ComputerworkingSpider(scrapy.Spider):
    name = 'compuworking'
    allowed_domains = ['computerworking.com.co']

    CATEGORIAS = [
        ('computadores',  'https://www.computerworking.com.co/categorias/222/true'),
        ('computadores',  'https://www.computerworking.com.co/categorias/310/true'),
        ('accesorios_pc', 'https://www.computerworking.com.co/categorias/169/true'),
        ('mouse_teclado', 'https://www.computerworking.com.co/categorias/124/true'),
        ('celulares',     'https://www.computerworking.com.co/categorias/230/true'),
        ('pantallas',     'https://www.computerworking.com.co/categorias/390/true'),
        ('audio',         'https://www.computerworking.com.co/categorias/241/true'),
        ('consolas',      'https://www.computerworking.com.co/categorias/243/true'),
        ('impresoras',    'https://www.computerworking.com.co/categorias/9/true'),
        ('impresoras',    'https://www.computerworking.com.co/categorias/301/true'),
    ]

    custom_settings = {
        'CONCURRENT_REQUESTS': 1,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 1,
        'DUPEFILTER_CLASS': 'scrapy.dupefilters.BaseDupeFilter',
    }

    def start_requests(self):
        nombre, url_base = self.CATEGORIAS[0]
        self.logger.info(f'\n{"="*60}')
        self.logger.info(f'INICIANDO: {url_base} -> [{nombre.upper()}] (1/{len(self.CATEGORIAS)})')
        self.logger.info(f'{"="*60}')
        yield self._make_request(url_base + '/1', nombre, url_base, pagina=1, idx_categoria=0)

    def _make_request(self, url, categoria_destino, url_base, pagina, idx_categoria):
        return scrapy.Request(
            url=url,
            meta={
                'playwright': True,
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
                'categoria_destino': categoria_destino,
                'url_base':          url_base,
                'pagina':            pagina,
                'idx_categoria':     idx_categoria,
            },
            callback=self.parse_category,
            dont_filter=True,
        )

    def parse_category(self, response):
        categoria_destino = response.meta['categoria_destino']
        url_base          = response.meta['url_base']
        pagina            = response.meta['pagina']
        idx_categoria     = response.meta['idx_categoria']

        productos = response.css('div.col-sm-3 div.productBox')
        self.logger.info(f'Pagina {pagina}: {len(productos)} productos [{categoria_destino}]')

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

                categoria_final = self.categorizar(nombre, categoria_destino)

                item = ComputerworkingItem()
                item['nombre']    = nombre
                item['precio']    = self.formatear_precio(precio_raw)
                item['enlace']    = response.urljoin(enlace)
                item['marca']     = self.extraer_marca(nombre)
                item['imagen']    = response.urljoin(imagen)
                item['categoria'] = categoria_final
                item['tienda']    = 'Computerworking'
                self.logger.info(f'  #{idx} [{categoria_final}] {nombre[:45]} | {item["precio"]}')
                yield item

            except Exception as e:
                self.logger.error(f'Error #{idx}: {e}')

        next_href = response.css('a.next::attr(href)').get()
        if productos and next_href:
            siguiente_pagina = pagina + 1
            self.logger.info(f'  -> pagina {siguiente_pagina}')
            yield self._make_request(
                f"{url_base}/{siguiente_pagina}",
                categoria_destino, url_base,
                pagina=siguiente_pagina,
                idx_categoria=idx_categoria,
            )
            return

        self.logger.info(f'URL [{categoria_destino}] completada en {pagina} paginas')
        idx_siguiente = idx_categoria + 1
        if idx_siguiente < len(self.CATEGORIAS):
            nombre_sig, url_sig = self.CATEGORIAS[idx_siguiente]
            self.logger.info(f'\n{"="*60}')
            self.logger.info(f'INICIANDO: {url_sig} -> [{nombre_sig.upper()}] ({idx_siguiente+1}/{len(self.CATEGORIAS)})')
            self.logger.info(f'{"="*60}')
            yield self._make_request(
                url_sig + '/1',
                nombre_sig, url_sig,
                pagina=1,
                idx_categoria=idx_siguiente,
            )
        else:
            self.logger.info('✅ TODAS LAS CATEGORIAS COMPLETADAS.')

    def categorizar(self, nombre, categoria_destino):
        n = nombre.lower()

        # --- COMPUTADORES ---
        if categoria_destino == 'computadores':
            if any(k in n for k in (
                'accesorios portátil', 'morral', 'funda', 'cargador',
                'base refrigerante', 'refrigeración', 'base', 'protector', 'lampara', 'guaya'
            )):
                return 'otros'
            return 'computadores'

        # --- CELULARES / TABLETS ---
        if categoria_destino == 'celulares':
            if any(k in n for k in ('tablet', 'tableta', 'ipad', 'tab ', 'tab+', 'samsung galaxy tab')):
                # FIX 1: quitamos 'lapiz' de aquí — un bundle "tablet + lapiz" sigue siendo tablet
                if any(k in n for k in (
                    'base para', 'soporte', 'funda', 'cargador', 'cable', 'protector', 'stylus'
                )):
                    return 'otros'
                return 'tablets'

            if any(k in n for k in (
                'smartwatch', 'power bank', 'powerbank', 'selfie', 'aro de luz',
                'panel de luz', 'tripode', 'tripié', 'cargador', 'base para',
                'smart band', 'control remoto', 'bateria', 'cable', 'soporte', 'lapiz'
            )):
                return 'otros'
            return 'celulares'

        # --- PANTALLAS ---
        if categoria_destino == 'pantallas':
            # FIX 2: agregamos 'soporte para televisor', 'soporte pedestal', 'splitter', 'antena'
            if any(k in n for k in (
                'soporte para tv',
                'soporte tv',
                'soporte televisor',
                'soporte para televisor',   # ← nuevo: "soporte para televisores flexible"
                'soporte de techo',
                'soporte pedestal',         # ← nuevo: "soporte pedestal mobile tv trolley"
                'tv stick',
                'tv box',
                'decodificador',
                'receptor',
                'game stick',
                'splitter',                 # ← nuevo: "splitter hdmi X puertos"
                'antena',                   # ← nuevo: "antena tdt"
            )):
                return 'otros'

            if any(k in n for k in ('televisor', 'monitor', 'pantalla', 'tv ', 'smart tv')):
                return 'pantallas'

            return 'otros'

        # --- AUDIO ---
        if categoria_destino == 'audio':
            return 'audio'

        # --- CONSOLAS ---
        if categoria_destino == 'consolas':
            return 'consolas'

        # --- IMPRESORAS ---
        if categoria_destino == 'impresoras':
            return 'impresoras'

        # accesorios_pc, mouse_teclado → otros
        if categoria_destino in (
            'accesorios_pc', 'mouse_teclado', 'accesorios_portatil',
            'morral', 'fundas', 'cargadores', 'bases_refrigerantes'
        ):
            return 'otros'

        return 'otros'

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
            'JALTECH','NUC','HYUNDAI','HISENSE','SONY','PANASONIC','SHARP','TCL',
            'PHILIPS','SENNHEISER','BOSE','BEATS','JBL','SKULLCANDY','PLANTRONICS',
            'CORSAIR','RAZER','STEELSERIES','BROTHER','RICOH','XEROX','KYOCERA',
        ]:
            if m in u:
                return m
        return 'GENERICA'