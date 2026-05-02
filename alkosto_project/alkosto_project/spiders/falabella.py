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
        'CONCURRENT_REQUESTS':            3,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 3,
        'DOWNLOAD_DELAY':                 2,
        'RANDOMIZE_DOWNLOAD_DELAY':       True,
        'PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT': 60000,
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
        'NINTENDO', 'PLAYSTATION', 'XBOX', 'STEELSERIES', 'HYPERX',
        'SENNHEISER', 'JABRA', 'SKULLCANDY', 'MARSHALL', 'HARMAN',
    ]

    MAX_PAGES   = 10
    MAX_RETRIES = 2

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
        ('https://www.falabella.com.co/falabella-co/category/cat50590/Gaming',                    'consolas'),
        ('https://www.falabella.com.co/falabella-co/category/cat10550940/Audio',                  'audio'),
    ]

    # =========================================================================
    # Categorías permitidas por URL de origen.
    # Si el clasificador por nombre da un resultado fuera de este set,
    # la URL gana y se usa categoria_origen.
    # 'otros' siempre está permitido (es el descarte universal).
    # =========================================================================
    _CATEGORIAS_PERMITIDAS = {
        'computadores': {'computadores', 'otros'},
        'tablets':      {'tablets',      'otros'},
        'celulares':    {'celulares',    'otros'},
        'impresoras':   {'impresoras',   'otros'},
        'pantallas':    {'pantallas',    'otros'},
        'consolas':     {'consolas',     'otros'},
        'audio':        {'audio',        'otros'},
    }

    # =========================================================================
    # Keywords de clasificación (minúsculas, sin tildes)
    # =========================================================================

    _EXCLUIR = [
        'proyector', 'videoproyector', 'mini proyector',
        'disco menstrual', 'copa menstrual', 'tampon', 'toalla higienica',
        'camiseta', 'camisa ', 'pantalon', 'zapato', 'tenis ',
        'reloj ', 'pulsera ', 'collar ', 'anillo ',
        'licuadora', 'batidora', 'cafetera', 'microondas',
        'aspiradora', 'plancha cabello', 'secador cabello',
        'muneca', 'peluche', 'lego ',
        'cuaderno', 'boligrafo', 'tijeras',
    ]

    _CABLES = [
        'cable ', 'cable hdmi', 'cable usb', 'cable vga', 'cable dp',
        'adaptador', 'convertidor', 'extension usb', 'extensor usb',
        'splitter', 'hub usb', 'bracket',
    ]

    _IMPRESORAS = [
        'impresora', 'multifuncional', 'plotter',
        'escaner', 'printer',
    ]

    _TABLETS = [
        'tablet', 'tableta', 'ipad',
        'galaxy tab', ' tab s', ' tab a', ' tab p',
        'mediapad', 'lenovo tab', 'fire tablet',
    ]

    _CELULARES = [
        'celular', 'smartphone', 'iphone',
        'galaxy s', 'galaxy a', 'galaxy z', 'galaxy m',
        'redmi ', ' poco ', 'moto g', 'moto e', ' pixel ',
        'find x', 'reno ',
    ]

    _CONSOLAS = [
        'playstation', 'ps5 ', 'ps4 ', 'ps3 ',
        'xbox series', 'xbox one',
        'nintendo switch', 'switch lite', 'switch oled',
        'steam deck', 'game boy',
    ]

    # Keywords inequívocos de computador (sin "portatil" suelto)
    _COMPUTADORES_DIRECTOS = [
        'laptop', 'notebook', 'macbook', 'chromebook', 'ultrabook',
        'todo en uno', 'todo-en-uno', 'all in one',
        'pc gamer', 'pc escritorio', 'pc de escritorio',
        'desktop pc', 'mini pc',
        'computador', 'computadora',
    ]

    # Contexto de hardware que confirma que "portatil" es un computador
    # y no una impresora/parlante/cámara portátil
    _CONTEXTO_HW = [
        'core i3', 'core i5', 'core i7', 'core i9',
        'ryzen 3', 'ryzen 5', 'ryzen 7', 'ryzen 9',
        'celeron', 'pentium', 'athlon',
        ' ram ', 'gb ram', ' ssd', ' hdd', ' nvme',
        'windows 11', 'windows 10', 'macos', 'chrome os',
        ' 8gb', ' 16gb', ' 32gb',
        'pantalla 13', 'pantalla 14', 'pantalla 15', 'pantalla 16',
        '13 pulgadas', '14 pulgadas', '15 pulgadas', '16 pulgadas',
        'gamer portatil', 'gaming portatil',
    ]

    _PANTALLAS = [
        'smart tv', 'television', 'televisor',
        'tv qled', 'tv oled', 'tv led', 'tv 4k', 'tv 8k',
        ' monitor ', 'monitor gamer', 'monitor curvo', 'monitor led',
        'monitor ips', 'monitor 4k', 'gaming monitor',
        'pantalla pc',
    ]

    _AUDIO = [
        'parlante', 'altavoz', 'bocina',
        'soundbar', 'barra de sonido',
        'home theater', 'teatro en casa',
        'audifono', 'audifonos', 'auricular',
        'headphone', 'earbud', 'earphone',
        'equipo de sonido', 'minicomponente', 'subwoofer',
        'speaker bluetooth', 'radio bluetooth', 'radio portatil',
        'tocadiscos', 'turntable',
    ]

    _PERIFERICOS = [
        'mouse ', 'raton ', 'teclado', 'keyboard',
        'webcam ', 'camara web',
        'mousepad', 'pad mouse', 'almohadilla',
        'headset gamer', 'headset gaming',
        'stylus ', 'lapiz optico', 'lapiz digital',
        'wrist rest', 'reposamuñecas',
    ]

    # =========================================================================
    # Normalización
    # =========================================================================
    @staticmethod
    def _norm(texto):
        """Minúsculas, sin tildes, con espacios en bordes para matching exacto."""
        return (
            ' ' + texto.lower()
            .replace('á', 'a').replace('é', 'e').replace('í', 'i')
            .replace('ó', 'o').replace('ú', 'u').replace('ü', 'u')
            .replace('ñ', 'n')
            + ' '
        )

    @staticmethod
    def _hit(n, keywords):
        return any(k in n for k in keywords)

    # =========================================================================
    # Reclasificación con sistema de prioridades + validación por URL
    # =========================================================================
    def _reclasificar(self, nombre, categoria_origen):
        n = self._norm(nombre)

        # ── Clasificador por nombre (10 niveles) ──────────────────────────────

        if self._hit(n, self._EXCLUIR):
            resultado = 'otros'
        elif self._hit(n, self._CABLES):
            resultado = 'otros'
        elif self._hit(n, self._IMPRESORAS):
            resultado = 'impresoras'
        elif self._hit(n, self._TABLETS):
            resultado = 'tablets'
        elif self._hit(n, self._CELULARES):
            resultado = 'celulares'
        elif self._hit(n, self._CONSOLAS):
            resultado = 'consolas'
        elif self._hit(n, self._COMPUTADORES_DIRECTOS):
            resultado = 'computadores'
        elif 'portatil' in n and self._hit(n, self._CONTEXTO_HW):
            # "portatil" suelto solo clasifica si hay contexto de hardware real.
            # Evita: "Impresora Portátil Bluetooth", "Parlante Portátil JBL".
            resultado = 'computadores'
        elif self._hit(n, self._PANTALLAS):
            # Va DESPUÉS de computadores: "PC Gamer con Monitor 27"
            # ya clasificó arriba y nunca llega aquí.
            resultado = 'pantallas'
        elif self._hit(n, self._AUDIO):
            resultado = 'audio'
        elif self._hit(n, self._PERIFERICOS):
            resultado = 'perifericos'
        else:
            self.logger.debug(f'[Falabella] SIN CATEGORIA: "{nombre[:60]}"')
            resultado = 'otros'

        # ── Validación por URL ────────────────────────────────────────────────
        # Si el clasificador por nombre da una categoría incompatible con la
        # URL de origen, la URL gana.
        # Ejemplo: un producto en la URL de computadores nunca puede salir
        # como 'pantallas' o 'audio' — forzamos a categoria_origen.
        # 'otros' siempre se respeta (descarte universal).
        permitidas = self._CATEGORIAS_PERMITIDAS.get(categoria_origen)
        if permitidas and resultado not in permitidas:
            self.logger.debug(
                f'[Falabella] URL-OVERRIDE: "{nombre[:50]}" '
                f'{resultado} → {categoria_origen} (forzado por URL)'
            )
            resultado = categoria_origen

        return resultado

    # =========================================================================
    # Start requests
    # =========================================================================
    def start_requests(self):
        for base_url, categoria in self.URLS:
            self.logger.info(f'[Falabella] ▶ {categoria} — {base_url}')
            yield self._make_request(base_url, categoria, page=1, retries=0)

    # =========================================================================
    # Make request (Playwright)
    # =========================================================================
    def _make_request(self, base_url, categoria, page, retries=0):
        return scrapy.Request(
            f'{base_url}?page={page}',
            meta={
                'playwright':              True,
                'playwright_include_page': True,
                'playwright_page_methods': [
                    PageMethod('set_default_timeout', 60000),
                    PageMethod(
                        'wait_for_selector',
                        'a[data-pod="catalyst-pod"]',
                        timeout=45000,
                    ),
                    PageMethod('evaluate', """
                        async () => {
                            const altura = document.body.scrollHeight;
                            const pasos  = 12;
                            for (let i = 1; i <= pasos; i++) {
                                window.scrollTo(0, (altura / pasos) * i);
                                await new Promise(r => setTimeout(r, 400));
                            }
                            let anterior = 0;
                            let estable  = 0;
                            for (let intento = 0; intento < 10; intento++) {
                                await new Promise(r => setTimeout(r, 500));
                                const actual = document.querySelectorAll(
                                    'a[data-pod="catalyst-pod"] img'
                                ).length;
                                if (actual === anterior) {
                                    estable++;
                                    if (estable >= 3) break;
                                } else {
                                    estable  = 0;
                                    anterior = actual;
                                }
                            }
                            await new Promise(r => setTimeout(r, 1000));
                        }
                    """),
                ],
                'base_url':  base_url,
                'categoria': categoria,
                'pagina':    page,
                'retries':   retries,
            },
            callback=self.parse,
            errback=self.handle_error,
            dont_filter=True,
        )

    # =========================================================================
    # Parse
    # =========================================================================
    async def parse(self, response):
        page = response.meta.get('playwright_page')
        if page:
            await page.close()

        base_url  = response.meta['base_url']
        categoria = response.meta['categoria']
        pagina    = response.meta['pagina']
        pods      = response.css('a[data-pod="catalyst-pod"]')

        self.logger.info(f'[Falabella] {categoria} | pág {pagina} — {len(pods)} pods')

        if not pods:
            self.logger.info(
                f'[Falabella] {categoria} | pág {pagina} — sin pods, fin de esta URL.'
            )
            return

        for pod in pods:
            item = self._extraer(pod, categoria)
            if item:
                yield item

        if pagina < self.MAX_PAGES:
            yield self._make_request(base_url, categoria, page=pagina + 1)
        else:
            self.logger.info(
                f'[Falabella] {categoria} | pág {pagina} — límite alcanzado.'
            )

    # =========================================================================
    # Handle error
    # =========================================================================
    async def handle_error(self, failure):
        page = failure.request.meta.get('playwright_page')
        if page:
            await page.close()

        request   = failure.request
        base_url  = request.meta.get('base_url', '')
        categoria = request.meta.get('categoria', '')
        pagina    = request.meta.get('pagina', 1)
        retries   = request.meta.get('retries', 0)

        self.logger.warning(
            f'[Falabella] ✗ {categoria} pág {pagina} '
            f'(intento {retries + 1}/{self.MAX_RETRIES}): '
            f'{failure.getErrorMessage()[:100]}'
        )

        if retries < self.MAX_RETRIES:
            self.logger.info(f'[Falabella] ↺ Reintentando {categoria} pág {pagina}...')
            yield self._make_request(base_url, categoria, pagina, retries=retries + 1)
        else:
            self.logger.warning(
                f'[Falabella] ⛔ {categoria} pág {pagina} — reintentos agotados.'
            )

    # =========================================================================
    # Extraer item de un pod
    # =========================================================================
    def _extraer(self, pod, categoria):
        nombre = (
            pod.css('[id*="displaySubTitle"]::text').get()
            or pod.css('[class*="subTitle"]::text').get()
            or pod.css('[class*="copy2"]::text').get()
            or pod.css('[class*="pod-title"]::text').get()
            or ''
        ).strip()
        if not nombre:
            return None

        href = pod.attrib.get('href', '')
        if href and not href.startswith('http'):
            href = 'https://www.falabella.com.co' + href

        # ── Imagen ───────────────────────────────────────────────────────────
        img_url = None

        for img in pod.css('img'):
            src = img.attrib.get('src', '')
            if 'media.falabella' in src and src.startswith('http'):
                img_url = src
                break

        if not img_url:
            for img in pod.css('img'):
                srcset = img.attrib.get('srcset', '')
                if 'media.falabella' in srcset:
                    entradas = re.split(r',\s+(?=https?://)', srcset)
                    urls = [e.strip().rsplit(' ', 1)[0] for e in entradas if e.strip()]
                    img_url = next((u for u in reversed(urls) if 'media.falabella' in u), None)
                    if img_url:
                        break

        if not img_url:
            for source in pod.css('picture source'):
                srcset = source.attrib.get('srcset', '')
                if 'media.falabella' in srcset:
                    entradas = re.split(r',\s+(?=https?://)', srcset)
                    urls = [e.strip().rsplit(' ', 1)[0] for e in entradas if e.strip()]
                    img_url = next((u for u in reversed(urls) if 'media.falabella' in u), None)
                    if img_url:
                        break

        if not img_url:
            self.logger.warning(f'[Falabella] SIN IMAGEN — {nombre[:60]}')

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
        precio_oferta   = None
        precio_original = None
        descuento_pct   = None

        li0 = pod.css('li[class*="prices-0"]')
        if li0:
            precio_oferta = (
                self._a_int(li0.attrib.get('data-event-price'))
                or self._a_int(li0.css('span:not([class*="crossed"])::text').get())
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

        if precio_oferta and not precio_original:
            precio_original = precio_oferta
            precio_oferta   = None

        # ── Reclasificación ──────────────────────────────────────────────────
        categoria_final = self._reclasificar(nombre, categoria)

        if categoria_final != categoria:
            self.logger.debug(
                f'[Falabella] RECLASIFICADO: "{nombre[:50]}" '
                f'{categoria} → {categoria_final}'
            )

        # ── Descartar productos sin categoría válida ──────────────────────────
        if categoria_final == 'otros':
            return None

        # ── Item ─────────────────────────────────────────────────────────────
        item = FalabellaItem()
        item['nombre']    = nombre
        item['precio']    = self._fmt(precio_original)
        item['promocion'] = self._fmt(precio_oferta) if precio_oferta else None
        item['descuento'] = descuento_pct
        item['marca']     = marca
        item['categoria'] = categoria_final
        item['enlace']    = href or None
        item['imagen']    = img_url or None
        item['vendedor']  = vendedor
        item['tienda']    = 'Falabella'
        return item

    # =========================================================================
    # Helpers
    # =========================================================================
    def _a_int(self, texto):
        if not texto:
            return None
        solo = re.sub(r'[^\d]', '', str(texto))
        return int(solo) if solo else None

    def _fmt(self, valor):
        if valor is None:
            return 'N/D'
        return f"{int(valor):,}".replace(",", ".") + " COP"