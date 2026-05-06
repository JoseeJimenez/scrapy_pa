import scrapy
from scrapy_playwright.page import PageMethod
from alkosto_project.items import ExitoProjectItem
import re
import unicodedata
import os
import signal

class ExitoSpider(scrapy.Spider):
    name = 'exito'
    allowed_domains = ['exito.com']
    base_url = 'https://www.exito.com/tecnologia?page='
    current_page = 1
    total_pages = 49
    custom_settings = {
        'CONCURRENT_REQUESTS': 1,
        'DOWNLOAD_DELAY': 3,
        'PLAYWRIGHT_BROWSER_TYPE': 'chromium',
        'TWISTED_REACTOR': 'twisted.internet.asyncioreactor.AsyncioSelectorReactor', 
    }

    def eliminar_tildes(self, texto):
        if not texto: return ""
        return "".join(c for c in unicodedata.normalize('NFD', texto)
                  if unicodedata.category(c) != 'Mn')

    def start_requests(self):
        yield self.make_request(self.current_page)

    def make_request(self, page):
        return scrapy.Request(
            url=f"{self.base_url}{page}",
            meta={
                "playwright": True,
                "playwright_include_page": True,
                "playwright_page_methods": [
                    PageMethod("wait_for_selector", "article", timeout=60000),
                    PageMethod("evaluate", "window.scrollBy(0, 2000)"),
                    PageMethod("wait_for_timeout", 5000),
                    PageMethod("evaluate", "window.scrollTo(0, document.body.scrollHeight)"),
                    PageMethod("wait_for_timeout", 15000), 
                ],
            },
            callback=self.parse,
            errback=self.errback_close_page,
            dont_filter=True
        )

    async def parse(self, response):
        page_obj = response.meta["playwright_page"]
        productos = response.css('article')
        
        self.logger.info(f"ÉXITO: Procesando página {self.current_page}")

        for p in productos:
            item = self._extraer_producto(p, response)
            if item:
                yield item

        await page_obj.close()
        if self.current_page < self.total_pages:
            self.current_page += 1
            yield self.make_request(self.current_page)

    def _extraer_producto(self, p, response):
        item = ExitoProjectItem()
        try:
            nombre = p.css('h3[class*="name"]::text').get()
            if not nombre: return None
            
            item['nombre'] = nombre.strip()
            item['marca'] = p.css('h3[class*="brand"]::text').get('').strip()
            item['enlace'] = response.urljoin(p.css('a::attr(href)').get())

            # Lógica de Precios
            precios_raw = p.xpath('.//*[contains(text(), "$")]/text()').getall()
            precios_num = sorted(list(set(self.limpiar_precio(t) for t in precios_raw if self.limpiar_precio(t) > 1000)), reverse=True)
            
            val_precio, val_promo = (None, None)
            if len(precios_num) >= 2:
                val_precio, val_promo = precios_num[0], precios_num[-1]
                item['precio'] = self._formatear_precio(val_precio)
                item['promocion'] = self._formatear_precio(val_promo)
            elif len(precios_num) == 1:
                val_precio = precios_num[0]
                item['precio'] = self._formatear_precio(val_precio)
                item['promocion'] = None

            if val_precio and val_promo and val_promo < val_precio:
                calculo = round(100 - (val_promo * 100 / val_precio))
                item['descuento'] = f"-{calculo}%"
            else:
                item['descuento'] = None

            # Calificación
            calif_selector = p.css('[class*="ratings-calification"]::text, [class*="ratingInline"]::text').get()
            item['calificacion'] = None
            if calif_selector:
                match = re.search(r'(\d[\.,]\d)', calif_selector)
                if match:
                    val = float(match.group(1).replace(',', '.'))
                    if 0 < val <= 5.0:
                        item['calificacion'] = val

            # Imagen y Tienda
            imgs = p.css('img::attr(src)').getall() + p.css('img::attr(data-src)').getall()
            img_final = next((i for i in imgs if i and 'vtexassets' in i), None)
            item['imagen'] = response.urljoin(img_final) if img_final else None
            item['tienda'] = 'Éxito'

            # --- CATEGORIZACIÓN FINAL ---
            cat = self.categorizar_estricto(item['nombre'])
            if cat is None: return None
            
            item['categoria'] = cat
            return item

        except Exception as e:
            self.logger.error(f"Error: {e}")
            return None
        
    def limpiar_precio(self, texto):
        if not texto: return 0
        numeros = re.sub(r'[^\d]', '', texto)
        return int(numeros) if numeros else 0

    def _formatear_precio(self, valor):
        return f"$ {valor:,} COP".replace(',', '.')

    def categorizar_estricto(self, nombre):
        n = self.eliminar_tildes(nombre.lower().strip())
        tiene_mas = '+' in n

        # ── EXCLUSIONES TOTALES ────────────────────────────────────────────
        if any(p in n for p in ['estufa', 'minibar', 'nevera', 'refrigerador',
                                'lavadora', 'secadora', 'microondas']):
            return None

        # ══════════════════════════════════════════════════════════════════
        # PASO 1: DETECTAR COMPONENTES PRESENTES EN EL NOMBRE
        # Cada función devuelve True si el producto ES de esa categoría
        # (no si solo la menciona de pasada)
        # ══════════════════════════════════════════════════════════════════

        def es_computador():
            return any(p in n for p in [
                'portatil', 'laptop', 'computador', 'macbook',
                'all in one', 'todo en uno', ' aio ',
                'pc gamer', 'torre cpu', 'torre pc',
                'vivobook', 'ideapad', 'thinkpad', 'pavilion',
                'inspiron', 'zenbook', 'chromebook', 'workstation',
                'imac', 'mac mini', 'mac pro',
                'nitro v', 'nitro 5', 'nitro 16', 'nitro an',
                'victus', 'omen ', 'legion ', 'predator ',
                'aspire ', 'swift ', 'spin ',
            ]) or n.startswith('aio ')

        def es_celular():
            # Solo patrones que inequívocamente son un teléfono
            patrones = [
                'celular ', 'smartphone',
                'iphone 1', 'iphone 2', 'iphone se', 'iphone pro', 'iphone plus',
                'galaxy s1', 'galaxy s2', 'galaxy s3', 'galaxy s4', 'galaxy s5',
                'galaxy s6', 'galaxy s7', 'galaxy s8', 'galaxy s9',
                'galaxy a0', 'galaxy a1', 'galaxy a2', 'galaxy a3', 'galaxy a4',
                'galaxy a5', 'galaxy a6', 'galaxy a7', 'galaxy a8', 'galaxy a9',
                'galaxy z flip', 'galaxy z fold',
                'redmi note ', 'redmi 1', 'redmi 2', 'redmi 3', 'redmi 4',
                'redmi 5', 'redmi 6', 'redmi 7', 'redmi 8', 'redmi 9',
                'poco x', 'poco m', 'poco f', 'poco c',
                'moto g', 'moto e', 'motorola edge', 'motorola moto',
                'infinix note ', 'infinix hot', 'infinix smart',
                'honor x', 'honor magic',
                'tecno spark', 'tecno camon',
                'realme ', 'oneplus ', 'oppo a', 'oppo reno',
            ]
            # Excluir si menciona "compatible con" o "para"
            es_ref = any(p in n for p in [
                'compatible con', 'para iphone', 'para samsung',
                'para celular', 'generacion compatible', 'gen compatible',
            ])
            return not es_ref and any(p in n for p in patrones)

        def es_tablet():
            return any(p in n for p in [
                'tablet ', 'ipad ', 'ipad pro', 'ipad air', 'ipad mini',
                'galaxy tab ', 'lenovo tab ', 'redmi pad ', 'xiaomi pad ',
                'tab lite', 'tab plus', 'tab ultra', 'tab active',
                'lapiz optico', 'apple pencil', 'stylus pen',
            ])

        def es_pantalla():
            return any(p in n for p in [
                'televisor ', 'smart tv', 'monitor ',
                'caixun', 'kalley tv',
                'qled', 'nanocell', 'miniled',
                'soporte tv', 'soporte para tv', 'soporte monitor',
                'soporte para monitor', 'base tv', 'base para tv',
                'brazo tv', 'brazo monitor', 'soporte de brazo',
                'control remoto tv', 'control smart tv', 'pedestal tv',
                'pedestal movil',
            ]) or ('oled' in n and 'televisor' in n)

        def es_audio():
            return any(p in n for p in [
                'parlante ', 'bafle ', 'audifonos', 'auriculares',
                'barra de sonido', 'torre de sonido', 'soundbar',
                'earbuds', 'earphones',
                'partybox', 'boombox', 'bocina ',
                # JBL — líneas de producto específicas
                'jbl flip', 'jbl charge', 'jbl xtreme', 'jbl go',
                'jbl pulse', 'jbl bar', 'jbl tune', 'jbl wave',
                'jbl vibe', 'jbl endurance', 'jbl reflect', 'jbl grip',
                # Otras marcas audio
                'bose quietcomfort', 'bose soundlink', 'bose sport',
                'bose s1', 'bose s2',
                'sony wh', 'sony wf', 'sony xb',
                'marshall ', 'soundcore', 'beats ',
                'microfono ',
                'xboom ',
                # Airpods / buds — líneas específicas
                'airpods pro', 'airpods max', 'airpods 4', 'airpods 3',
                'airpods 2', 'galaxy buds', 'buds pro', 'buds2', 'buds3',
                'freebuds', 'earfun', 'jabra ',
                'karaoke ',
            ])

        def es_consola():
            return any(p in n for p in [
                'consola ', 'playstation', 'ps5 ', 'ps4 ', ' ps5', ' ps4',
                'xbox series', 'xbox one',
                'nintendo switch', 'switch oled', 'switch lite',
                'mando ps', 'mando xbox', 'control ps4', 'control ps5',
                'control xbox', 'dualsense', 'dualshock',
                'rog ally', 'steam deck',
            ])

        def es_impresora():
            return any(p in n for p in [
                'impresora ', 'multifuncional ', 'plotter ',
                'smart tank', 'ink tank', 'deskjet', 'laserjet',
                'pixma', 'ecotank', 'tinta continua',
                # tinta/consumible de impresora también va aquí
                'kit de tinta', 'cartucho ', 'toner ', 'tinta epson',
                'tinta hp', 'tinta canon',
            ])

        def es_otro():
            return any(p in n for p in [
                'power bank', 'powerbank',
                'cargador ', 'cable usb', 'cable tipo c', 'cable lightning',
                'adaptador ',
                # Relojes / wearables — siempre otros, incluso en combo
                'smartwatch ', 'galaxy fit', 'galaxy watch', 'apple watch',
                'amazfit', 'garmin ', 'mi band', 'honor band',
                'reloj inteligente', 'reloj smart', 'smart watch',
                'funda ', ' case ', 'protector de pantalla',
                'mica ', 'vidrio templado',
                'memoria sd', 'memoria usb', 'disco duro externo',
                'mouse ', 'teclado ',
                'router ', 'extensor wifi',
                'camara de seguridad', 'drone ',
                'proyector ',
            ])

        # ══════════════════════════════════════════════════════════════════
        # PASO 2: MAPEAR QUÉ CATEGORÍAS ESTÁN PRESENTES
        # ══════════════════════════════════════════════════════════════════
        presentes = {
            'computadores': es_computador(),
            'celulares':    es_celular(),
            'tablets':      es_tablet(),
            'pantallas':    es_pantalla(),
            'audio':        es_audio(),
            'consolas':     es_consola(),
            'impresoras':   es_impresora(),
            'otros':        es_otro(),
        }

        cats_presentes = [c for c, v in presentes.items() if v]

        # ══════════════════════════════════════════════════════════════════
        # PASO 3: PRODUCTO SIMPLE (una sola categoría detectada)
        # ══════════════════════════════════════════════════════════════════
        if len(cats_presentes) == 1:
            return cats_presentes[0]

        # ══════════════════════════════════════════════════════════════════
        # PASO 4: COMBOS Y DESEMPATES (dos o más categorías detectadas)
        # ══════════════════════════════════════════════════════════════════
        p = presentes  # alias corto

        # — Consola siempre gana si está presente —
        if p['consolas']:
            return 'consolas'

        # — Impresora gana sobre computadores (Epson F170 Sublimación) —
        if p['impresoras']:
            return 'impresoras'

        # — Combos con celular —
        if p['celulares']:
            # Celular + {reloj, cargador, audífonos, tablet} → celulares
            if any(p[c] for c in ['otros', 'audio', 'tablets']):
                return 'celulares'
            return 'celulares'

        # — Combos con tablet —
        if p['tablets']:
            # Tablet + audífonos → tablets
            if p['audio']:
                return 'tablets'
            return 'tablets'

        # — Combos audio + otros (reloj + audífonos) → audio —
        if p['audio'] and p['otros']:
            # Si el "otro" es un reloj/wearable solo, va a audio
            # (Reloj Smart Watch + Audífonos I8 Ultra → audio)
            tiene_reloj = any(x in n for x in [
                'watch', 'reloj', 'smartwatch', 'band '
            ])
            tiene_audio = any(x in n for x in [
                'audifonos', 'auriculares', 'buds', 'airpods', 'parlante'
            ])
            if tiene_reloj and tiene_audio:
                return 'audio'
            # Si el "otro" es cargador/accesorio → otros
            return 'otros'

        # — Computadores vs pantallas: AIO puede tener 'monitor' en nombre —
        if p['computadores'] and p['pantallas']:
            return 'computadores'

        # — Pantallas ganan sobre otros —
        if p['pantallas']:
            return 'pantallas'

        # — Audio solo —
        if p['audio']:
            return 'audio'

        # — Computadores solo —
        if p['computadores']:
            return 'computadores'

        # ══════════════════════════════════════════════════════════════════
        # PASO 5: NINGUNA CATEGORÍA DETECTADA → otros
        # ══════════════════════════════════════════════════════════════════
        if not cats_presentes:
            return 'otros'

        return cats_presentes[0]

    async def errback_close_page(self, failure):
        page = failure.request.meta.get("playwright_page")
        if page: await page.close()

    def closed(self, reason):
        os.kill(os.getpid(), signal.SIGINT)