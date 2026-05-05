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
        'CONCURRENT_REQUESTS':            2,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 2,
        'DOWNLOAD_DELAY':                 1,
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

    _CATEGORIAS_PERMITIDAS = {
        'computadores': {'computadores', 'pantallas', 'otros'},
        'tablets':      {'tablets',      'otros'},
        'celulares':    {'celulares',    'otros'},
        'impresoras':   {'impresoras',   'otros'},
        'pantallas':    {'pantallas',    'otros'},
        'consolas':     {'consolas',     'otros'},
        'audio':        {'audio',        'otros'},
    }

    _EXCLUIR = [
        'disco menstrual', 'copa menstrual', 'tampon', 'toalla higienica',
        'camiseta', 'camisa ', 'pantalon', 'zapato', 'tenis ',
        'reloj ', 'pulsera ', 'collar ', 'anillo ',
        'licuadora', 'batidora', 'cafetera', 'microondas',
        'aspiradora', 'plancha cabello', 'secador cabello',
        'muneca', 'peluche', 'lego ',
        'cuaderno', 'boligrafo', 'tijeras',
    ]

    # NOTA: Se eliminó 'cable ', 'adaptador' y 'convertidor' genéricos
    # porque interceptaban productos válidos (celulares, audio, consolas)
    _CABLES = [
        'cable hdmi', 'cable usb', 'cable vga', 'cable dp',
        'extension usb', 'extensor usb',
        'splitter', 'hub usb', 'bracket',
        'cable de carga control',   # cable de consola, no celular
        'cable audio y video wii',
        'cable de poder ps',
    ]

    _IMPRESORAS = [
        'impresora', 'multifuncional', 'multifuncion', 'plotter',
        'escaner', 'printer', 'fotocopiadora', 'copiadora',
        # Tintas y consumibles — van a impresoras, no a otros
        'tinta ', 'tintas ', 'cartucho', 'cartuchos',
        'toner', 'tóner',
        'botella tinta', 'botella de tinta',
        'kit tinta', 'kit tintas', 'kit de tinta',
        'sistema de tinta', 'sistema tinta',
        'cabezal', 'cabezal impresion', 'cabezal de impresion',
        'recarga tinta', 'rellenar cartucho',
        'ribbon ', 'tinta ribbon',
        # Extras
        'ecotank',
        'scanncut', 'scancut',
        'caja de mantenimiento',
        'papel adhesivo dk',
        'cinta plastico',
        'cinta d1',
        'letratag', 'rotuladora',
        'botella t544', 'botella btd',
        'unidad de imagen compatible',
        'tambor creacion de imagenes',
        'destructora', 'picadora de papel',
        'scanner ads',
        'caja mantenimiento pxmb',
    ]

    _TABLETS = [
        'tablet', 'tableta', 'ipad',
        'galaxy tab', ' tab s', ' tab a', ' tab p',
        'mediapad', 'lenovo tab', 'fire tablet',
        'kindle', 'paperwhite', 'kindle scribe',
        'kobo ',
        # Extras
        'megapad',
        'tab tb',
        'pizarra lcd',
        'digitalizador de firma',
        'pantalla lcd tactil capacitiva hdmi raspberry',
        'pantalla display raspberry',
    ]

    _CELULARES = [
        'celular', 'smartphone', 'iphone',
        'galaxy s', 'galaxy a', 'galaxy z', 'galaxy m', 'galaxy f',
        'redmi ', ' poco ', 'moto g', 'moto e', ' pixel ',
        'find x', 'reno ',
        # Extras
        's25 ultra',
        'a36 5g',
        'note 50',
        'note 60',
        'v50 512',
        'y19 s ',
        'blade l220',
        'smart 20 4g',
        'nubia v80',
        'cel5g magic',
        'a26 8ram',
        'play9a',
        'm3000 profesional',
        'magic8l',
    ]

    _CONSOLAS = [
        'playstation', 'ps5 ', 'ps4 ', 'ps3 ', '5 slim', '4 slim', '4 pro',
        'xbox series', 'xbox one', 'xbox 360',
        'nintendo switch', 'switch lite', 'switch oled', 'switch 2',
        'steam deck', 'game boy',
        'meta quest', 'oculus quest', 'quest 3', 'quest 2', 'vr headset',
        # Videojuegos físicos/digitales
        'videojuego', 'video juego',
        'mario kart', 'mario odyssey', 'mario party', 'mario bros',
        'mario galaxy', 'mario wonder', 'mario tennis',
        'zelda ', 'breath of the wild', 'tears of the kingdom',
        'pokemon ', 'pokémon ',
        'kirby ', 'metroid', 'splatoon', 'smash ',
        'fifa ', 'ea sports fc', 'nba 2k', 'mlb ',
        'call of duty', 'god of war', 'spider-man',
        'assassin', 'far cry', 'cyberpunk', 'elden ring',
        'street fighter', 'tekken ', 'mortal kombat',
        'minecraft ', 'sonic ', 'halo ', 'forza ',
        'hogwarts', 'resident evil', 'diablo ', 'overwatch',
        'amiibo',
        # Extras — consolas sin keyword claro
        'series s ', 'series x ',
        'consola series',
        'consola juegos',
        'switch™', ' switch 2',
        # Accesorios de consola
        'control compatible con play',
        'control inalambrico dualsense',
        'control pro para consola',
        'control joystick inalambrico nlntendo',
        'control joystick inalambrico nintendo',
        'control robot white', 'control carbon black',
        'control series shock', 'control series s x',
        'control one series',
        'control storm breaker',
        'control inalambrico series sx',
        'control backbone',
        'control licenciado xbox',
        'control hand grip',
        'control joystick super nova',
        'control inalambrico cyclone',
        'control inalambrico easysmx',
        'controlador x2 pro',
        'clutch gladiate',
        'kontrol freek',
        'joycon',
        'dualsense edge',
        'analogico para control',
        '2x analogo electromagnetico hall',
        'soporte base pared 2 controles',
        'silicona protectora',
        'funda en acrilico protector para mando xbox',
        'carcasa protector funda flexible para nintendo wii',
        'vidrio templado para consola',
        'estuche rigido relieve',
        'estuche negro + acrilico',
        'estuche de viaje rigido',
        'estuche para consola',
        'maleta estuche de viaje para switch',
        'soporte plegable para decodificador',
        'flex mod 101',
        'adaptador de corriente cargador compatible con switch',
        'adaptador nintendo switch type-c',
        'handgrip soporte para joycon',
        'cable hdmi 2.1 8k',
        'bateria recargable + cable usb-c',
        'adaptador inalambrico xbox',
        'x2 cinta cable flex microfono v1 para sony ps5',
        'accesorio switch',
        'camera switch',
        # Juegos extras
        'grand theft auto',
        'donkey kong bananza', 'donkey kong country',
        'tony hawk',
        'one piece odyssey',
        'dragon ball fighterz',
        'ori the collection',
        'gris - switch', 'neva - switch',
        'marvel ultimate alliance',
        'xenoblade',
        'triangle strategy',
        'fire emblem',
        'shin megami tensei',
        'streets of rage',
        'tactics ogre',
        'prinny presents',
        'story of seasons',
        'phantom brave',
        'stray - ',
        'chrono cross',
        'atelier yumia',
        'final fantasy ix',
        'the caligula effect',
        'horizon forbidden west',
        'yasha legends',
        'daemon x machina',
        'dead space',
        'trials of mana',
        'ys x nordics',
        'farmagia',
        'rune factory',
        'sword of the necromancer',
        'blazblue',
        'black myth wukong',
        'the diofield chronicle',
        'visions of mana',
        'death stranding',
        'legacy of kain',
        'suikoden',
        'dragon quest iii',
        'the king of fighters',
        'the rumble fish',
        'evil west',
        'tales of graces',
        'tales of symphonia',
        'asterix & obelix',
        'fantasian neo dimension',
        'read only memories',
        'five nights at freddy',
        'gears 5',
        'my hero one',
        'eiyuden chronicle',
        'star ocean',
        'hades - switch',
        'luigi',
        'animal crossing',
        'super mario 3d world',
        'marvel vs capcom',
        'capcom fighting collection',
        'pokemon legends z',
        'super mario 3d all',
        'fc 25 play',
        'spirit of the north',
        'lost judgment',
        'elrentaros',
        'estuche game traveler',
        'set 22 en 1 hand grip',
        'carga y juega compatible con series',
        'kit carga y juega 360',
        'volante palanca y pedal gamer',
        'palanca de cambios shifter gaming',
        'volante xbsx racing',
        'asiento de carreras',
        'pasta termica arctic',
    ]

    _COMPUTADORES_DIRECTOS = [
        'laptop', 'notebook', 'macbook', 'chromebook', 'ultrabook',
        'todo en uno', 'todo-en-uno', 'all in one',
        'pc gamer', 'pc escritorio', 'pc de escritorio',
        'desktop pc', 'mini pc', 'desktop gaming',
        'computador', 'computadora',
        'torre gamer', 'torre pc', 'cpu gamer',
        'gabinete torre',
        # Líneas HP
        'victus', 'pavilion', 'envy ', 'spectre', 'omen ',
        'probook', 'elitebook', 'zbook',
        # Líneas Lenovo
        'ideapad', 'thinkpad', 'legion ', 'yoga ',
        # Líneas ASUS
        'vivobook', 'zenbook', 'rog ', 'tuf gaming',
        # Líneas Dell
        'inspiron', 'xps ', 'latitude', 'vostro',
        # Líneas Acer
        'swift ', 'aspire ', 'nitro ', 'predator',
        'extensa ', 'travelmate',
        # Líneas Toshiba/Dynabook
        'dynabook', 'portege', 'satellite',
        # Otros
        'surface ',
        'galaxy book',
        'matebook',
        ' loq ',
    ]

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
        'rtx 3050', 'rtx 3060', 'rtx 3070', 'rtx 3080',
        'rtx 4050', 'rtx 4060', 'rtx 4070', 'rtx 4080',
        'gtx 1650', 'gtx 1660',
        ' fhd ', 'fhd "', ' led 15', ' led 14', ' led 13',
        'led 15,6', 'led 14,', 'led 13,',
    ]

    _PANTALLAS = [
        'smart tv', 'television', 'televisor',
        'tv qled', 'tv oled', 'tv led', 'tv 4k', 'tv 8k',
        ' monitor ', 'monitor gamer', 'monitor curvo', 'monitor led',
        'monitor ips', 'monitor 4k', 'gaming monitor',
        'pantalla pc',
        # Modelos de TV sin keyword explícito
        'bravia ', 'crystal uhd', ' qled', ' oled',
        'un32t', 'un43t', 'un50t', 'un55t', 'un65t',
        'tcl|',
        # Extras
        'marco tactil',
        'touch screen',
        'pantalla hd portatil recargable',
        'extensor de pantalla triple',
        'pantalla 24 pulgadas inteligente',
        'wandr - centro de entretenimiento',
        'pantalla para proyector',
        'tv 65\"',
        'ua8050',
        'soporte para tv pared',
        'pantalla lcd tactil',
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
        # Modelos JBL sin keyword genérico
        'partybox', 'go4 ', 'go4squad',
        'charge 6', 'charge 5', 'charge 4',
        'flip 6', 'flip 7', 'flip 5',
        'xtreme ', 'boombox', 'pulse 5', 'clip 5', 'clip 4',
        'jbl bar', 'jbl cinema',
        # Audífonos por modelo
        'airpods', 'air pods',
        'galaxy buds', 'galaxy buds4', 'freebuds',
        'soundpeats', 'jabra ',
        'jbl tune', 'jbl live', 'jbl free', 'jbl reflect',
        'jbl endurance',
        'sony wh', 'sony wf', 'sony linkbuds',
        'beats studio', 'beats fit', 'beats flex', 'beats powerbeats',
        'anker soundcore',
        # Extras
        'torre de sonido',
        'cabina activa',
        'cabina de sonido',
        'cabina torre de sonido',
        'cabina sonivox',
        'microfono', 'micrófono',
        'microfonos', 'micrófonos',
        'lark m2',
        'by-v20', 'by-v1',
        'mic mini dual',
        'mic 3 negro', 'mic 3 (2tx',
        'quantum stream studio',
        'sm57 instrumental',
        'pm-500 usb',
        'nt1 5ta gen',
        'pga58',
        'sv200', 'sv100', ',sv100',
        'cmteck',
        'sistema inalambrico con 2 microfonos',
        'sistema inalambrico doble microfono',
        'amplificador de voz portatil',
        'amplificador megafono',
        'grabadora de audio', 'grabadora de voz',
        'icd-ux570', 'dr-05x',
        'h4essential',
        'mezclador tarjeta de sonido',
        'mezclador de audio',
        'tarjeta de sonido externa',
        'wave beam 2',
        'audifonos t110',
        'audifono t110',
        'diadema studio pro',
        'soundgear frames',
        'sub1 modulo de bajos',
        'audio pack superficie',
        'l1 pro ',
        's1 pro',
        'funda play - through para s1',
        'transmisor de instrumentos inalambrico',
        'transmisor inalambrico de microfono',
        'one box xboom',
        'torre de sonido party rocker',
        'authentics 300',
        'receptor bluetooth para auto',
        'soporte x 2 para parlantes',
        'walkie talkie',
        'radio am-fm',
        'radio fm digital',
        'radio pastilla',
        'radio digital portatil',
        'radio vintage bluetooth',
        'radio analogico',
        'planta solar portatil 3 bombillas radio',
        'radios de comunicacion',
        'cable de audio plug 3.5',
        'cable adaptador convertidor plug 3.5',
        'adaptador audio 30 pines bluetooth',
        'adaptador audio digital a analogico',
        'bluetooth audio receptor 30 pines',
        'microfono inalambrico lavalier',
        'microfono lark',
        'kit de microfonos inalambricos creators',
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
    # Reclasificación
    # =========================================================================
    def _reclasificar(self, nombre, categoria_origen):
        n = self._norm(nombre)

        if self._hit(n, self._EXCLUIR):
            resultado = 'excluir'
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
            resultado = 'computadores'
        elif self._hit(n, self._CONTEXTO_HW):
            resultado = 'computadores'
        elif self._hit(n, self._PANTALLAS):
            resultado = 'pantallas'
        elif self._hit(n, self._AUDIO):
            resultado = 'audio'
        elif self._hit(n, self._PERIFERICOS):
            resultado = 'perifericos'
        else:
            self.logger.debug(f'[Falabella] SIN CATEGORIA: "{nombre[:60]}"')
            resultado = 'otros'

        # Validación por URL: solo se salta si es 'excluir'.
        if resultado != 'excluir':
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

        # Descartamos solo productos explícitamente excluidos
        if categoria_final == 'excluir':
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