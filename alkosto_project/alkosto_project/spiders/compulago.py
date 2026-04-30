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
        'PANASONIC', 'SHARP', 'PHILIPS',
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
        ('https://compulago.com/categoria/parlantes/',                                                     'audio'),
    ]

    load_more_script = """
    async () => {
        const SELECTORES = [
            '#button-mas', '#portatilesbutton', '#portatiles2button',
            '#tablets-y-celulares2button', '#impresorasbutton', '#monitoresbutton',
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
            if (actual === ultimaCantidad) { sinCambios++; }
            else { sinCambios = 0; ultimaCantidad = actual; }
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

        productos = (
            response.css('div.e-loop-item')
            or response.css('div[class*="e-loop-item"]')
            or response.css('div.e-con.e-child')
            or response.css('article.product')
            or response.css('li.product')
        )
        productos = [p for p in productos if p.css('a[href*="/producto/"]')]

        self.logger.info(
            f'[Compulago] {response.url} — '
            f'categoria={categoria_fija} | productos={len(productos)}'
        )

        if not productos:
            clases = [s.attrib.get('class', '') for s in response.css('div[class]')[:25]]
            self.logger.warning(f'[Compulago] SIN CONTENEDORES. Clases: {clases}')
            return

        vistos = set()

        for producto in productos:
            # ── Enlace y nombre ──────────────────────────────────────────────
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

            # ── Imagen ───────────────────────────────────────────────────────
            img_url = (
                producto.css('div.jet-woo-product-thumbs__inner img::attr(src)').get()
                or producto.css('img.attachment-full::attr(src)').get()
                or producto.css('img::attr(src)').get()
            )

            # ── Porcentaje de descuento ──────────────────────────────────────
            # div.porcentaje-ahorro → "-10%" o "10%"
            pct_texto = producto.css('div.porcentaje-ahorro::text').get()
            descuento_pct = None
            if pct_texto:
                pct_num = re.search(r'\d+', pct_texto)
                if pct_num:
                    descuento_pct = int(pct_num.group())

            # ── Precios ──────────────────────────────────────────────────────
            # Recoger TODOS los span de precio dentro del producto
            todos_spans = producto.css('span.woocommerce-Price-amount.amount')
            valores = []
            for span in todos_spans:
                textos = span.css('::text').getall()
                numero = next((t.strip() for t in textos if re.search(r'\d', t)), None)
                if numero:
                    solo = re.sub(r'[^\d]', '', numero)
                    if solo:
                        valores.append(int(solo))

            precio_original  = None
            precio_promocion = None

            if len(valores) == 2:
                # DOS spans: mayor = original tachado, menor = oferta
                precio_original  = max(valores)
                precio_promocion = min(valores)

            elif len(valores) == 1 and descuento_pct:
                # 1 span = precio original, calculamos promocion
                precio_original  = valores[0]
                precio_promocion = round(precio_original * (1 - descuento_pct / 100) / 1000) * 1000

            elif len(valores) == 1:
                # 1 span sin descuento = precio normal
                precio_original = valores[0]

            # ── Item ─────────────────────────────────────────────────────────
            nombre_upper = nombre.upper()
            marca     = next((m for m in self.MARCAS_COMUNES if m in nombre_upper), 'GENERICA')
            categoria = categoria_fija or self._categorizar_por_nombre(nombre, href)

            item = CompulagoItem()
            item['nombre']    = nombre
            item['precio']    = self._fmt(precio_original)
            item['promocion'] = self._fmt(precio_promocion) if precio_promocion else None
            item['descuento'] = f"{descuento_pct}%" if descuento_pct else None
            item['marca']     = marca
            item['categoria'] = categoria
            item['enlace']    = href
            item['imagen']    = img_url or None
            item['tienda']    = 'Compulago'
            yield item

    # ─────────────────────────────────────────────────────────────────────────
    def _fmt(self, valor):
        if valor is None:
            return 'N/D'
        return f"{int(valor):,}".replace(",", ".") + " COP"

    def _categorizar_por_nombre(self, nombre, enlace):
        t = (nombre + ' ' + enlace).lower()
        if any(k in t for k in ['tablet', 'tableta', 'ipad', ' tab ']):
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