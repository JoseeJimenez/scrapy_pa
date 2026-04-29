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
        'POWER GROUP',
    ]

    # (url_slug, categoria_fija)  — None = decidir por nombre
    URLS = [
        ('https://compulago.com/categoria/portatiles/',                                                    'computadores'),
        ('https://compulago.com/categoria/tablets-y-celulares-corporativo/',                               None),
        ('https://compulago.com/categoria/imagen-y-video-corporativo/',                                    'pantallas'),
        ('https://compulago.com/categoria/impresoras-corporativo/',                                        'impresoras'),
        ('https://compulago.com/categoria/pc-escritorio-corporativo/pc-todo-en-uno-corporativo/',          'computadores'),
        ('https://compulago.com/categoria/pc-escritorio-corporativo/pc-clon-completo-corporativo-hogar/', 'computadores'),
        ('https://compulago.com/categoria/pc-escritorio-corporativo/pc-clon-cpu/',                        'computadores'),
        ('https://compulago.com/categoria/pc-escritorio-corporativo/pc-de-marca-corporativo/',            'computadores'),
    ]

    # Hace clic en #button-mas (y variantes) hasta que no aparezcan nuevos productos
    load_more_script = """
    async () => {
        const SELECTORES = [
            '#button-mas',
            '#portatilesbutton',
            '#portatiles2button',
            '#tablets-y-celulares2button',
            '#impresorasbutton',
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

        # --- NOMBRES ---
        enlaces = []
        vistos = set()
        for a in response.css('a[href*="/producto/"]'):
            href   = a.attrib.get('href', '')
            nombre = ' '.join(a.css('::text').getall()).strip()
            if href and nombre and href not in vistos:
                vistos.add(href)
                enlaces.append({'href': href, 'nombre': nombre})

        # --- PRECIOS: nodo de texto con dígitos dentro del span ---
        precios = []
        for span in response.css('span.woocommerce-Price-amount.amount'):
            textos = span.css('::text').getall()
            numero = next((t.strip() for t in textos if re.search(r'\d', t)), None)
            precios.append(numero)

        # --- IMAGENES ---
        imagenes = response.css('div.jet-woo-product-thumbs__inner img:first-of-type')

        self.logger.info(
            f'[Compulago] {response.url} — '
            f'nombres:{len(enlaces)} precios:{len(precios)} imgs:{len(imagenes)}'
        )

        for i, enlace in enumerate(enlaces):
            precio_raw = precios[i]  if i < len(precios)  else None
            img_url    = imagenes[i].attrib.get('src') if i < len(imagenes) else None

            nombre_upper = enlace['nombre'].upper()
            marca = next((m for m in self.MARCAS_COMUNES if m in nombre_upper), 'GENERICA')

            if categoria_fija:
                categoria = categoria_fija
            else:
                categoria = self._categorizar_por_nombre(enlace['nombre'], enlace['href'])

            item = CompulagoItem()
            item['nombre']    = enlace['nombre']
            item['precio']    = self._formatear_precio(precio_raw)
            item['marca']     = marca
            item['categoria'] = categoria
            item['enlace']    = enlace['href']
            item['imagen']    = img_url or None
            item['tienda']    = 'Compulago'
            yield item

    # ------------------------------------------------------------------
    def _formatear_precio(self, texto):
        if not texto:
            return 'N/D'
        solo_numeros = re.sub(r'[^\d]', '', str(texto))
        if not solo_numeros:
            return 'N/D'
        return f"{int(solo_numeros):,}".replace(",", ".") + " COP"

    def _categorizar_por_nombre(self, nombre, enlace):
        """Solo se llama cuando categoria_fija es None (ej: tablets-y-celulares)."""
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