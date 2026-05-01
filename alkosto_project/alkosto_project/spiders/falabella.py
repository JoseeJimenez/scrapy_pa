import scrapy
import re
import sys
import asyncio
from scrapy_playwright.page import PageMethod
from alkosto_project.items import FalabellaItem

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


class FalabellaSpider(scrapy.Spider):
    name = 'falabella'

    custom_settings = {
        # Una request a la vez para no saturar Falabella y evitar bloqueos
        'CONCURRENT_REQUESTS':            2,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 2,
        'DOWNLOAD_DELAY':                 2,
        'RANDOMIZE_DOWNLOAD_DELAY':       True,
        'PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT': 60000,

        # ── FIX CRÍTICO: imágenes ──────────────────────────────────────────
        # settings.py tiene PLAYWRIGHT_ABORT_REQUEST bloqueando "image".
        # Eso hace que los <img> queden sin src en el HTML renderizado.
        # Sobreescribimos aquí para NO bloquear imágenes en este spider.
        'PLAYWRIGHT_ABORT_REQUEST': lambda req: req.resource_type in ('font', 'media'),
    }

    MARCAS_COMUNES = [
        'HP', 'LENOVO', 'ASUS', 'APPLE', 'ACER', 'DELL', 'SAMSUNG', 'LG',
        'XIAOMI', 'MOTOROLA', 'HUAWEI', 'REALME', 'OPPO', 'EPSON', 'CANON',
        'KALLEY', 'VIVO', 'BROTHER', 'XEROX', 'RICOH', 'KYOCERA',
        'SONY', 'VIEWSONIC', 'BENQ', 'AOC', 'LOGITECH', 'GARMIN', 'MSI',
        'INTEL', 'MICROSOFT', 'TCL', 'HISENSE', 'PANASONIC', 'SHARP',
        'JBL', 'BOSE', 'ANKER', 'BEATS', 'STEREN', 'PHILIPS', 'STARLINK',
        'RAZER', 'CORSAIR', 'GIGABYTE', 'AMD', 'NVIDIA', 'ALIENWARE',
    ]

    # Cada URL tiene su categoría fija — el spider avanza una por una
    URLS = [
        ('https://www.falabella.com.co/falabella-co/category/cat1361001/Computadores-Portatiles', 'computadores'),
        ('https://www.falabella.com.co/falabella-co/category/CATG36245/Portatiles-Gamer',         'computadores'),
        ('https://www.falabella.com.co/falabella-co/category/CATG34751/PC-Gamer',                 'computadores'),
        ('https://www.falabella.com.co/falabella-co/category/cat50611/Computadora-Todo-en-uno',   'computadores'),
        ('https://www.falabella.com.co/falabella-co/category/cat50666/Tablets',                   'tablets'),
        ('https://www.falabella.com.co/falabella-co/category/cat2571041/Monitores-para-pc',       'pantallas'),
        ('https://www.falabella.com.co/falabella-co/category/cat790955/Impresoras-y-Tintas',      'impresoras'),
        ('https://www.falabella.com.co/falabella-co/category/cat5420971/Smart-TV',                'pantallas'),
        ('https://www.falabella.com.co/falabella-co/category/cat1660941/Celulares-y-Telefonos',   'celulares'),
    ]

    MAX_PAGES_PER_URL = 10  # máximo de páginas por URL antes de pasar a la siguiente

    # Espera extra para asegurarse de que las imágenes lazy se carguen
    wait_script = "async () => { await new Promise(r => setTimeout(r, 4000)); }"

    # ──────────────────────────────────────────────────────────────────────────
    def start_requests(self):
        self._url_index = 0
        base_url, categoria = self.URLS[0]
        self.logger.info(f'[Falabella] Iniciando: {categoria} — {base_url}')
        yield self._make_request(base_url, categoria, page=1)

    def _make_request(self, base_url, categoria, page):
        url = f'{base_url}?page={page}'
        return scrapy.Request(
            url,
            meta={
                'playwright': True,
                'playwright_include_page': True,
                'playwright_page_methods': [
                    PageMethod('set_default_timeout', 60000),
                    PageMethod(
                        'wait_for_selector',
                        'a[data-pod="catalyst-pod"]',
                        timeout=45000,
                    ),
                    # Scroll para activar lazy-load de imágenes
                    PageMethod('evaluate', """
                        async () => {
                            window.scrollTo(0, document.body.scrollHeight);
                            await new Promise(r => setTimeout(r, 1500));
                            window.scrollTo(0, 0);
                            await new Promise(r => setTimeout(r, 2500));
                        }
                    """),
                ],
                'base_url':  base_url,
                'categoria': categoria,
                'pagina':    page,
            },
            callback=self.parse,
            errback=self.handle_error,
            dont_filter=True,
        )

    async def parse(self, response):
        # ── Cerrar la página de Playwright para liberar el pool ───────────────
        # Sin esto, con CONCURRENT_REQUESTS=1 el spider se congela después
        # de la primera página porque la Page queda abierta indefinidamente.
        page = response.meta.get('playwright_page')
        if page:
            await page.close()

        base_url  = response.meta['base_url']
        categoria = response.meta['categoria']
        pagina    = response.meta['pagina']
        pods      = response.css('a[data-pod="catalyst-pod"]')

        self.logger.info(
            f'[Falabella] {categoria} | pág {pagina} — pods: {len(pods)}'
        )

        # Página vacía → esta categoría terminó, pasar a la siguiente
        if not pods:
            self.logger.info(
                f'[Falabella] {categoria} | pág {pagina} vacía — fin de categoría.'
            )
            req = self._siguiente_categoria()
            if req:
                yield req
            return

        for pod in pods:
            item = self._extraer(pod, categoria)
            if item:
                yield item

        # Siguiente página — respetar el límite MAX_PAGES_PER_URL
        if pagina < self.MAX_PAGES_PER_URL:
            yield self._make_request(base_url, categoria, page=pagina + 1)
        else:
            self.logger.info(
                f'[Falabella] {categoria} | pág {pagina} — límite de '
                f'{self.MAX_PAGES_PER_URL} páginas alcanzado, pasando a la siguiente URL.'
            )
            req = self._siguiente_categoria()
            if req:
                yield req

    # ──────────────────────────────────────────────────────────────────────────
    def _siguiente_categoria(self):
        """Devuelve la Request de la primera página de la siguiente categoría, o None."""
        self._url_index += 1
        if self._url_index < len(self.URLS):
            base_url, categoria = self.URLS[self._url_index]
            self.logger.info(
                f'[Falabella] → Iniciando categoría {self._url_index + 1}/'
                f'{len(self.URLS)}: {categoria} — {base_url}'
            )
            return self._make_request(base_url, categoria, page=1)
        self.logger.info('[Falabella] ✅ Todas las categorías completadas.')
        return None

    # ──────────────────────────────────────────────────────────────────────────
    def _extraer(self, pod, categoria):
        # ── Nombre ───────────────────────────────────────────────────────────
        nombre = (
            pod.css('[id*="displaySubTitle"]::text').get()
            or pod.css('[class*="subTitle"]::text').get()
            or pod.css('[class*="copy2"]::text').get()
            or pod.css('[class*="pod-title"]::text').get()
            or ''
        ).strip()
        if not nombre:
            return None

        # ── Enlace ───────────────────────────────────────────────────────────
        href = pod.attrib.get('href', '')
        if href and not href.startswith('http'):
            href = 'https://www.falabella.com.co' + href

        # ── Imagen ───────────────────────────────────────────────────────────
        # DOM real:
        #   <source srcset="url_240,h=240,q=70 1x, url_480,h=480,q=70 2x">
        #   <img src="url_240..." id="testId-pod-image-..." loading="lazy|eager">
        #
        # Las URLs tienen comas en sus propios parámetros (width=240,height=240,...),
        # así que NO se puede partir simplemente por ",".
        # El separador entre entradas del srcset es ", https://" — se usa
        # re.split con lookahead para no romper las URLs.
        img_url = None

        srcset_raw = pod.css('picture source::attr(srcset)').get() or ''
        if srcset_raw:
            # Partir por ", " seguido de "https://" para respetar comas dentro de URLs
            entradas = re.split(r',\s+(?=https?://)', srcset_raw)
            # Cada entrada: "https://...url... Nx" — quitar el descriptor final (1x, 2x)
            urls = [e.strip().rsplit(' ', 1)[0] for e in entradas if e.strip()]
            # Tomar la última URL (mayor resolución, 2x = 480px)
            if urls:
                img_url = urls[-1]

        # Fallback: src del <img> — puede estar vacío si el pod era lazy
        if not img_url:
            img_url = (
                pod.css('img[id^="testId-pod-image"]::attr(src)').get()
                or pod.css('picture img::attr(src)').get()
                or pod.css('img::attr(src)').get()
            )

        # Descartar placeholders o URLs relativas
        if img_url and not img_url.startswith('http'):
            img_url = None

        # ── Vendedor ─────────────────────────────────────────────────────────
        vendedor = (
            pod.css('[class*="pod-sellerText"]::text').get()
            or pod.css('[class*="seller"]::text').get()
            or 'Falabella'
        ).strip()

        # ── Marca ────────────────────────────────────────────────────────────
        marca_tag = (
            pod.css('[class*="brand"]::text').get()
            or pod.css('[class*="pod-brand"]::text').get()
            or ''
        ).strip().upper()
        nombre_upper = nombre.upper()
        marca = marca_tag if marca_tag else next(
            (m for m in self.MARCAS_COMUNES if m in nombre_upper), 'GENERICA'
        )

        # ── Precios ──────────────────────────────────────────────────────────
        # li[class*="prices-0"] data-event-price  → precio oferta
        # li[class*="prices-1"] data-normal-price → precio original tachado
        # span[class*="discount-badge-item"]       → "-44%"
        precio_oferta   = None
        precio_original = None
        descuento_pct   = None

        li0 = pod.css('li[class*="prices-0"]')
        if li0:
            precio_oferta = (
                self._a_int(li0.attrib.get('data-event-price'))
                or self._a_int(
                    li0.css('span:not([class*="crossed"])::text').get()
                )
            )

        li1 = pod.css('li[class*="prices-1"]')
        if li1:
            precio_original = (
                self._a_int(li1.attrib.get('data-normal-price'))
                or self._a_int(
                    li1.css('span[class*="crossed"]::text').get()
                    or li1.css('span::text').get()
                )
            )

        desc_txt = pod.css('[class*="discount-badge-item"]::text').get() or ''
        pct = re.search(r'\d+', desc_txt)
        if pct:
            descuento_pct = pct.group() + '%'

        # Si solo hay precio oferta sin original → es el precio normal (sin descuento)
        if precio_oferta and not precio_original:
            precio_original = precio_oferta
            precio_oferta   = None

        # ── Item ─────────────────────────────────────────────────────────────
        item = FalabellaItem()
        item['nombre']    = nombre
        item['precio']    = self._fmt(precio_original)
        item['promocion'] = self._fmt(precio_oferta) if precio_oferta else None
        item['descuento'] = descuento_pct
        item['marca']     = marca
        item['categoria'] = categoria
        item['enlace']    = href or None
        item['imagen']    = img_url or None
        item['vendedor']  = vendedor
        item['tienda']    = 'Falabella'
        return item

    # ──────────────────────────────────────────────────────────────────────────
    async def handle_error(self, failure):
        # Cerrar la página también en caso de error
        page = failure.request.meta.get('playwright_page')
        if page:
            await page.close()
        request   = failure.request
        base_url  = request.meta.get('base_url', '')
        categoria = request.meta.get('categoria', '')
        pagina    = request.meta.get('pagina', 1)
        self.logger.warning(
            f'[Falabella] Error {categoria} pág {pagina}: '
            f'{failure.getErrorMessage()} — reintentando...'
        )
        yield self._make_request(base_url, categoria, pagina)

    # ──────────────────────────────────────────────────────────────────────────
    def _a_int(self, texto):
        if not texto:
            return None
        solo = re.sub(r'[^\d]', '', str(texto))
        return int(solo) if solo else None

    def _fmt(self, valor):
        if valor is None:
            return 'N/D'
        return f"{int(valor):,}".replace(",", ".") + " COP"