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

    MARCAS_COMUNES = [
        'HP', 'LENOVO', 'ASUS', 'APPLE', 'ACER', 'DELL', 'SAMSUNG', 'LG',
        'XIAOMI', 'MOTOROLA', 'HUAWEI', 'REALME', 'OPPO', 'EPSON', 'CANON',
        'KALLEY', 'VIVO', 'BROTHER', 'XEROX', 'RICOH', 'KYOCERA',
        'SONY', 'VIEWSONIC', 'BENQ', 'AOC', 'LOGITECH', 'GARMIN', 'MSI',
        'COMPUMAX', 'INTEL', 'INFINIX', 'NUBIA', 'JALTECH', 'ESENSES', 'IORA',
        'POWER GROUP', 'CHALLENGER', 'SANKEY', 'HYUNDAI', 'HISENSE', 'TCL',
        'KALLEY', 'PANASONIC', 'SHARP', 'PHILIPS',
        'JBL', 'BOSE', 'STEREN', 'MARSHALL', 'HARMAN', 'PIONEER', 'YAMAHA',
        'EDIFIER', 'CREATIVE', 'ANKER', 'BEATS', 'KLIPSCH',
    ]

    URLS = [
        ('https://compulago.com/categoria/portatiles/',                                                    'computadores'),
        ('https://compulago.com/categoria/tablets-y-celulares-corporativo/tablets-corporativo/',           'tablets'),
        ('https://compulago.com/categoria/tablets-y-celulares-corporativo/celulares/',                     'celulares'),
        ('https://compulago.com/categoria/imagen-y-video-corporativo/televisores/',                        'pantallas'),
        ('https://compulago.com/categoria/pc-utilitarios/monitores-corporativo/',                          'pantallas'),
        ('https://compulago.com/categoria/impresoras-corporativo/',                                        'impresoras'),
        ('https://compulago.com/categoria/pc-escritorio-corporativo/pc-todo-en-uno-corporativo/',          'computadores'),
        ('https://compulago.com/categoria/pc-escritorio-corporativo/pc-clon-completo-corporativo-hogar/', 'computadores'),
        ('https://compulago.com/categoria/pc-escritorio-corporativo/pc-clon-cpu/',                        'computadores'),
        ('https://compulago.com/categoria/pc-escritorio-corporativo/pc-de-marca-corporativo/',            'computadores'),
        ('https://compulago.com/categoria/parlantes/',                                                         'audio'),
    ]

    load_more_script = """
    async () => {
        const SELECTORES = [
            '#button-mas',
            '#portatilesbutton',
            '#portatiles2button',
            '#tablets-y-celulares2button',
            '#impresorasbutton',
            '#monitoresbutton',
            'a.elementor-button-link[href="#"][id]',
        ];

        let sinCambios = 0;
        let ultimaCantidad = document.querySelectorAll('a[href*="/producto/"]').length;

        while (sinCambios < 3) {
            window.scrollTo(0, document.body.scrollHeight);
            await new Promise(r => setTimeout(r, 1500));

            let clicHecho = false;
            for (const sel of SELECTORES) {
                const btns = document.querySelectorAll(sel);
                for (const btn of btns) {
                    const rect = btn.getBoundingClientRect();
                    if (rect.width > 0 && rect.height > 0) {
                        btn.scrollIntoView({ behavior: 'smooth', block: 'center' });
                        await new Promise(r => setTimeout(r, 600));
                        btn.click();
                        clicHecho = true;
                        break;
                    }
                }
                if (clicHecho) break;
            }

            await new Promise(r => setTimeout(r, 3000));

            const actual = document.querySelectorAll('a[href*="/producto/"]').length;
            if (actual === ultimaCantidad) {
                sinCambios++;
            } else {
                sinCambios = 0;
                ultimaCantidad = actual;
            }
        }
    }
    """

    def start_requests(self):
        for url, categoria in self.URLS:
            yield scrapy.Request(
                url,
                meta={
                    'playwright': True,
                    'playwright_include_page': True,
                    'categoria_fija': categoria,
                    'playwright_page_methods': [
                        PageMethod('set_default_timeout', 120000),
                        PageMethod('wait_for_selector', 'a[href*="/producto/"]'),
                        PageMethod('evaluate', self.load_more_script),
                        PageMethod('wait_for_timeout', 3000),
                    ],
                },
                callback=self.parse,
            )

    def parse(self, response):
        categoria_fija = response.meta.get('categoria_fija')

        # ── Estructura real confirmada en dev tools ───────────────────────────
        #
        # div.e-loop-item                    ← contenedor de cada producto
        #   div (imagen)
        #   div (marca - widget heading)
        #   div.productdescriptioncomputo    ← widget con el nombre + enlace
        #     div.elementor-widget-container
        #       p.elementor-heading-title
        #         a[href*="/producto/"]      ← enlace y nombre
        #   div (shortcode - descripcion)
        #   div (precio - widget heading)
        #     div.elementor-widget-container
        #       p.elementor-heading-title
        #         span.woocommerce-Price-amount.amount
        #           span.woocommerce-Price-currencySymbol  "$"
        #           "2.365.000"             ← texto del precio
        #
        # CLAVE: precio y nombre estan en widgets HERMANOS dentro de e-loop-item.
        # Al buscar dentro del e-loop-item con .get() ambos quedan vinculados
        # al mismo producto — sin desincronizacion posible.
        # ─────────────────────────────────────────────────────────────────────

        productos = (
            response.css('div.e-loop-item')        # confirmado en dev tools (imagen 4)
            or response.css('div[class*="e-loop-item"]')
            or response.css('div.e-con.e-child')   # fallback Elementor container hijo
            or response.css('article.product')
            or response.css('li.product')
        )

        # Quedarse solo con los que tienen enlace a producto real
        productos = [p for p in productos if p.css('a[href*="/producto/"]')]

        self.logger.info(
            f'[Compulago] {response.url} — '
            f'categoria={categoria_fija} | productos={len(productos)}'
        )

        if not productos:
            clases = [s.attrib.get('class', '') for s in response.css('div[class]')[:25]]
            self.logger.warning(
                f'[Compulago] {response.url} — SIN CONTENEDORES. '
                f'Primeras clases div: {clases}'
            )
            return

        vistos = set()

        for producto in productos:
            # ── Enlace y nombre ───────────────────────────────────────────────
            # Dentro de div.productdescriptioncomputo > p.elementor-heading-title > a
            # Usamos el selector mas especifico primero; si no existe, cualquier
            # a[href*="/producto/"] dentro del contenedor del producto.
            a_tag = (
                producto.css('div[class*="productdescription"] a[href*="/producto/"]')
                or producto.css('p.elementor-heading-title a[href*="/producto/"]')
                or producto.css('a[href*="/producto/"]')
            )
            if not a_tag:
                continue

            href = a_tag.attrib.get('href', '')
            if not href or href in vistos:
                continue
            vistos.add(href)

            nombre = ' '.join(a_tag.css('::text').getall()).strip()
            if not nombre:
                continue

            # ── Imagen ────────────────────────────────────────────────────────
            # .get() devuelve la primera imagen del contenedor (principal),
            # ignorando la imagen hover que va segunda en el DOM
            img_url = (
                producto.css('div.jet-woo-product-thumbs__inner img::attr(src)').get()
                or producto.css('img.attachment-full.size-full::attr(src)').get()
                or producto.css('img.wp-post-image::attr(src)').get()
                or producto.css('img::attr(src)').get()
            )

            # ── Precio ────────────────────────────────────────────────────────
            # span.woocommerce-Price-amount.amount esta dentro del ultimo
            # widget heading del e-loop-item (hermano del widget de nombre).
            # Al buscarlo dentro del mismo contenedor e-loop-item siempre
            # corresponde al precio de ese producto especifico.
            precio_raw   = self._extraer_precio(producto)
            nombre_upper = nombre.upper()
            marca        = next((m for m in self.MARCAS_COMUNES if m in nombre_upper), 'GENERICA')
            categoria    = categoria_fija or self._categorizar_por_nombre(nombre, href)

            item = CompulagoItem()
            item['nombre']    = nombre
            item['precio']    = self._formatear_precio(precio_raw)
            item['marca']     = marca
            item['categoria'] = categoria
            item['enlace']    = href
            item['imagen']    = img_url or None
            item['tienda']    = 'Compulago'
            yield item

    # -------------------------------------------------------------------------
    def _extraer_precio(self, nodo):
        """Extrae el precio numerico del span WooCommerce dentro del nodo."""
        for span in nodo.css('span.woocommerce-Price-amount.amount'):
            # El texto del precio es el texto directo del span (no del hijo
            # woocommerce-Price-currencySymbol que contiene el simbolo "$")
            textos = span.css('::text').getall()
            numero = next((t.strip() for t in textos if re.search(r'\d', t)), None)
            if numero:
                return numero
        return None

    def _formatear_precio(self, texto):
        if not texto:
            return 'N/D'
        solo_numeros = re.sub(r'[^\d]', '', str(texto))
        if not solo_numeros:
            return 'N/D'
        return f"{int(solo_numeros):,}".replace(",", ".") + " COP"

    def _categorizar_por_nombre(self, nombre, enlace):
        """Fallback — solo se usa si una URL no tiene categoria_fija."""
        t = (nombre + ' ' + enlace).lower()
        if any(k in t for k in ['tablet', 'tableta', 'ipad', ' tab ', 'tb3', 'tb5', 'tb7', 'tb9']):
            return 'tablets'
        if any(k in t for k in ['celular', 'smartphone', 'iphone', 'moto ',
                                  'galaxy', 'redmi', 'note ']):
            return 'celulares'
        if any(k in t for k in ['impresora', 'multifuncional']):
            return 'impresoras'
        if any(k in t for k in ['monitor', 'pantalla', 'proyector', 'tv ', 'televisor']):
            return 'pantallas'
        if any(k in t for k in ['laptop', 'portátil', 'portatil', 'notebook', 'computador']):
            return 'computadores'
        if any(k in t for k in ['audifonos', 'parlante', 'speaker', 'auricular']):
            return 'audio'
        if any(k in t for k in ['consola', 'playstation', 'xbox', 'nintendo']):
            return 'consolas'
        return 'otros'