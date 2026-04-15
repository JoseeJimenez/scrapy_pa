import scrapy
from scrapy_playwright.page import PageMethod
from alkosto_project.items import ExitoProjectItem
import sys
import asyncio

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


class ExitoSpider(scrapy.Spider):
    name = 'exito'

    def start_requests(self):
        url = 'https://www.exito.com/tecnologia'
        yield scrapy.Request(
            url,
            meta=self._playwright_meta(),
            callback=self.parse,
        )

    # ------------------------------------------------------------------ #
    #  Parseo de cada página                                               #
    # ------------------------------------------------------------------ #

    def parse(self, response):
        productos = response.css('article.productCard_productCard__M0677')
        self.logger.info(f"[Éxito] Página actual — productos encontrados: {len(productos)}")

        for p in productos:
            yield self._extraer_producto(p, response)

        # ---- Paginación: preferir seguir el href del enlace "Siguiente"
        # Muchas veces el control es un <a href="...">; seguir el href permite
        # que Scrapy encole URLs distintas y evita re-visitar la misma URL.
        next_href = response.css('a.Pagination_nextPreviousLink__f7_2J::attr(href)').get()
        if next_href:
            next_url = response.urljoin(next_href)
            self.logger.info("[Éxito] Yendo a la siguiente página: %s", next_url)
            yield scrapy.Request(
                next_url,
                meta=self._playwright_meta(),
                callback=self.parse,
            )
        else:
            # Fallback: si no existe href, intentamos usar click sobre el botón
            boton_siguiente = response.css('button.Pagination_nextPreviousLink__f7_2J:not([disabled])')
            if boton_siguiente:
                self.logger.info("[Éxito] Yendo a la siguiente página (click fallback)...")
                yield scrapy.Request(
                    response.url,
                    meta=self._playwright_meta(click_next=True),
                    callback=self.parse,
                    dont_filter=True,
                )

    # ------------------------------------------------------------------ #
    #  Meta de Playwright                                                  #
    # ------------------------------------------------------------------ #

    def _playwright_meta(self, click_next=False):
        """
        Construye el meta dict para Playwright.
        Si click_next=True, agrega el PageMethod que hace clic en "Siguiente"
        y espera a que los nuevos productos carguen.
        """
        # Reduce Playwright default timeout to 30s and wait for a reliable selector
        page_methods = [
            PageMethod("set_default_timeout", 30000),
            PageMethod("wait_for_selector", "article.productCard_productCard__M0677"),
        ]

        if click_next:
            page_methods += [
                # Clic en "Siguiente"
                PageMethod("click", "button.Pagination_nextPreviousLink__f7_2J"),
                # Esperamos que los nuevos productos estén en el DOM (usa el timeout reducido)
                PageMethod("wait_for_selector", "article.productCard_productCard__M0677"),
                # Pequeño buffer extra por si hay animaciones de carga
                PageMethod("wait_for_timeout", 1500),
            ]

        return {
            "playwright": True,
            "playwright_include_page": True,
            "playwright_page_methods": page_methods,
        }

    # ------------------------------------------------------------------ #
    #  Extracción de un producto                                           #
    # ------------------------------------------------------------------ #

    def _extraer_producto(self, p, response):
        # Nombre
        nombre = (
            p.css('h3.styles_name__qQJiK::text').get()
            or p.css('h3::text').get()
        )

        # Marca
        marca = p.css('h3.styles_brand__IdJcB::text').get()

        # Precio normal
        precio_raw = (
            p.css('p[data-fs-container-price-otros="true"]::text').get()
            or p.css('p.ProductPrice_container__price__XmMWA::text').get()
        )

        # Precio con promoción (si existe)
        precio_promo_raw = (
            p.css('[data-fs-product-card-container-promotion="true"] p::text').get()
        )

        # Enlace
        link = p.css('a[data-testid="product-link"]::attr(href)').get()

        # No extraemos ni almacenamos la URL de la imagen (omitido a propósito)

        # Especificaciones (lista de li > span)
        specs = p.css(
            'ul[data-fs-product-card-properties="true"] li span::text'
        ).getall()

        # Vendedor
        vendedor = self._extraer_vendedor(p)

        # ¿Es anuncio patrocinado?
        patrocinado = bool(p.css('p[data-fs-topsort="true"]').get())

        precio_num = self.limpiar_precio(precio_raw)
        precio_promo_num = self.limpiar_precio(precio_promo_raw)

        item = ExitoProjectItem()
        item['nombre'] = nombre.strip() if nombre else None
        item['marca'] = marca.strip() if marca else None
        item['precio'] = self._formatear_precio(precio_num)
        item['precio_promocion'] = self._formatear_precio(precio_promo_num)
        item['specs'] = [s.strip() for s in specs if s.strip()]
        item['enlace'] = response.urljoin(link) if link else None
        item['vendedor'] = vendedor
        item['patrocinado'] = patrocinado
        item['categoria'] = self.categorizar(nombre or '', link or '')
        item['tienda'] = 'Éxito'
        return item

    def _extraer_vendedor(self, p):
        """Extrae el nombre del vendedor del párrafo 'Vendido por: X'."""
        # Intento 1: texto directo del span hermano
        vendedor = p.css(
            'p[data-fs-product-name-container="true"] span:last-child::text'
        ).get()
        if vendedor:
            return vendedor.strip()

        # Intento 2: texto completo del párrafo, partir por ':'
        parrafo = p.css('p[data-fs-product-name-container="true"]::text').getall()
        texto = ' '.join(parrafo).strip()
        if ':' in texto:
            return texto.split(':', 1)[-1].strip()

        return None

    # ------------------------------------------------------------------ #
    #  Helpers                                                             #
    # ------------------------------------------------------------------ #

    def limpiar_precio(self, texto):
        if texto:
            solo_numeros = ''.join(filter(str.isdigit, str(texto)))
            return int(solo_numeros) if solo_numeros else 0
        return 0

    def _formatear_precio(self, valor):
        if valor:
            return f"{valor:,.0f}".replace(",", ".") + " COP"
        return None

    def categorizar(self, nombre, enlace=''):
        t = (nombre + ' ' + enlace).lower()
        if any(k in t for k in ['tablet', 'tableta', 'ipad']):
            return 'tablets'
        if any(k in t for k in ['laptop', 'notebook', 'portátil', 'portatil',
                                  'computador', 'pc', 'desktop', 'all-in-one']):
            return 'computadores'
        if any(k in t for k in ['celular', 'smartphone', 'iphone', 'galaxy',
                                  'teléfono', 'telefono']):
            return 'celulares'
        if any(k in t for k in ['monitor', 'pantalla', 'display', 'led', 'oled',
                                  'tv', 'televisor', 'televisión']):
            return 'pantallas'
        if any(k in t for k in ['consola', 'playstation', 'xbox', 'nintendo',
                                  'ps4', 'ps5']):
            return 'consolas'
        if any(k in t for k in ['audífono', 'audifonos', 'auricular', 'parlante',
                                  'speaker', 'sonido', 'headphone']):
            return 'audio'
        if any(k in t for k in ['impresora', 'escáner', 'scanner', 'tóner', 'toner']):
            return 'impresoras'
        if any(k in t for k in ['cámara', 'camara', 'foto', 'video', 'gopro']):
            return 'fotografía'
        return 'otros'