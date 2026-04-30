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

    MARCAS_COMUNES = [
        'HP', 'LENOVO', 'ASUS', 'APPLE', 'ACER', 'DELL', 'SAMSUNG', 'LG',
        'XIAOMI', 'MOTOROLA', 'HUAWEI', 'REALME', 'OPPO', 'EPSON', 'CANON',
        'KALLEY', 'VIVO', 'BROTHER', 'XEROX', 'RICOH', 'KYOCERA',
        'SONY', 'VIEWSONIC', 'BENQ', 'AOC', 'LOGITECH', 'GARMIN', 'MSI',
        'INTEL', 'MICROSOFT', 'STARLINK', 'TECHSPOT', 'COMPUMARKET',
        'JBL', 'BOSE', 'ANKER', 'BEATS', 'STEREN',
        'TCL', 'HISENSE', 'PANASONIC', 'SHARP', 'PHILIPS',
    ]

    # URL base con parametro de pagina
    BASE_URL = 'https://www.falabella.com.co/falabella-co/category/cat171006/Computadores?page={page}'
    TOTAL_PAGES = 200

    # Categorias basadas en texto del producto
    CATEGORIA_MAP = [
        (['tablet', 'tableta', 'ipad'],                                          'tablets'),
        (['celular', 'smartphone', 'iphone', 'moto ', 'galaxy', 'redmi'],        'celulares'),
        (['impresora', 'multifuncional', 'ecotank', 'tinta'],                    'impresoras'),
        (['monitor', 'pantalla', 'proyector', 'tv ', 'televisor'],               'pantallas'),
        (['laptop', 'portátil', 'portatil', 'notebook', 'computador portatil',
          'ideapad', 'thinkpad', 'vivobook', 'zenbook', 'inspiron', 'pavilion'], 'computadores'),
        (['desktop', 'all-in-one', 'todo en uno', 'torre', 'pc escritorio',
          'desktop', 'imac'],                                                     'computadores'),
        (['teclado', 'mouse', 'webcam', 'auricular', 'audifonos', 'parlante',
          'speaker', 'microfono', 'hub', 'cable', 'cargador', 'bateria',
          'memoria', 'disco duro', 'ssd', 'pendrive', 'router', 'switch'],       'accesorios'),
        (['software', 'licencia', 'antivirus', 'windows', 'office'],             'software'),
    ]

    # Script para esperar que carguen los productos
    wait_script = """
    async () => {
        await new Promise(r => setTimeout(r, 4000));
    }
    """

    def start_requests(self):
        # Paginar desde la 1 hasta TOTAL_PAGES
        for page in range(1, self.TOTAL_PAGES + 1):
            url = self.BASE_URL.format(page=page)
            yield scrapy.Request(
                url,
                meta={
                    'playwright': True,
                    'playwright_include_page': True,
                    'playwright_page_methods': [
                        PageMethod('set_default_timeout', 60000),
                        PageMethod('wait_for_selector', 'a[data-pod="catalyst-pod"]', timeout=30000),
                        PageMethod('evaluate', self.wait_script),
                    ],
                    'pagina': page,
                },
                callback=self.parse,
            )

    def parse(self, response):
        pagina = response.meta.get('pagina', '?')

        # Cada producto es un <a data-pod="catalyst-pod">
        pods = response.css('a[data-pod="catalyst-pod"]')

        self.logger.info(f'[Falabella] Página {pagina} — productos: {len(pods)}')

        if not pods:
            self.logger.warning(f'[Falabella] Página {pagina} sin productos — posible fin o bloqueo')
            return

        for pod in pods:
            # ── Enlace ───────────────────────────────────────────────────────
            href = pod.attrib.get('href', '')
            if href and not href.startswith('http'):
                href = 'https://www.falabella.com.co' + href

            # ── Nombre ───────────────────────────────────────────────────────
            nombre = (
                pod.css('[id*="displaySubTitle"]::text').get()
                or pod.css('[class*="subTitle"]::text').get()
                or pod.css('[class*="pod-title"]::text').get()
                or pod.css('[class*="copy2"]::text').get()
                or ''
            ).strip()
            if not nombre:
                continue

            # ── Imagen ───────────────────────────────────────────────────────
            img_url = (
                pod.css('img[src*="falabella"]::attr(src)').get()
                or pod.css('img::attr(src)').get()
                or pod.css('img::attr(data-src)').get()
            )

            # ── Vendedor ─────────────────────────────────────────────────────
            vendedor = pod.css('[class*="pod-sellerText"]::text').get() or 'Falabella'

            # ── Marca ────────────────────────────────────────────────────────
            # Falabella muestra la marca en un span sobre el nombre
            marca_tag = (
                pod.css('[class*="brand"]::text').get()
                or pod.css('[class*="pod-brand"]::text').get()
                or ''
            ).strip().upper()

            nombre_upper = nombre.upper()
            if marca_tag:
                marca = marca_tag
            else:
                marca = next((m for m in self.MARCAS_COMUNES if m in nombre_upper), 'GENERICA')

            # ── Precios ──────────────────────────────────────────────────────
            # li.prices-0  → precio oferta  (data-event-price)
            # li.prices-1  → precio original (data-normal-price, tachado)
            # descuento    → span.discount-badge-item texto "-44%"

            precio_oferta   = None
            precio_original = None
            descuento_pct   = None

            # Precio oferta
            li_oferta = pod.css('li[class*="prices-0"]')
            if li_oferta:
                val = li_oferta.attrib.get('data-event-price', '')
                if val:
                    precio_oferta = self._str_a_int(val)
                else:
                    # fallback: texto del span que no tiene clase "crossed"
                    precio_oferta = self._extraer_precio_span(
                        li_oferta.css('span[class*="primary"]:not([class*="crossed"])::text').get()
                    )

            # Precio original tachado
            li_original = pod.css('li[class*="prices-1"]')
            if li_original:
                val = li_original.attrib.get('data-normal-price', '')
                if val:
                    precio_original = self._str_a_int(val)
                else:
                    precio_original = self._extraer_precio_span(
                        li_original.css('span[class*="crossed"]::text').get()
                        or li_original.css('span::text').get()
                    )

            # Descuento
            desc_texto = pod.css('[class*="discount-badge-item"]::text').get() or ''
            pct = re.search(r'\d+', desc_texto)
            if pct:
                descuento_pct = pct.group() + '%'

            # Si no hay precio original pero hay oferta → el de oferta es el normal
            if precio_oferta and not precio_original:
                precio_original = precio_oferta
                precio_oferta   = None

            # ── Categoría ────────────────────────────────────────────────────
            categoria = self._categorizar(nombre)

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
            yield item

    # ─────────────────────────────────────────────────────────────────────────
    def _str_a_int(self, texto):
        """Convierte '1.699.900' o '1699900' a int."""
        if not texto:
            return None
        solo = re.sub(r'[^\d]', '', str(texto))
        return int(solo) if solo else None

    def _extraer_precio_span(self, texto):
        if not texto:
            return None
        solo = re.sub(r'[^\d]', '', str(texto))
        return int(solo) if solo else None

    def _fmt(self, valor):
        if valor is None:
            return 'N/D'
        return f"{int(valor):,}".replace(",", ".") + " COP"

    def _categorizar(self, nombre):
        t = nombre.lower()
        for keywords, cat in self.CATEGORIA_MAP:
            if any(k in t for k in keywords):
                return cat
        return 'computadores'   # default para esta categoria de Falabella