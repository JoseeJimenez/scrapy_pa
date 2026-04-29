import scrapy
from scrapy_playwright.page import PageMethod
from alkosto_project.items import AlkostoProjectItem
import sys
import asyncio
import re

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

class ComputerworkingSpider(scrapy.Spider):
    name = 'compuworking'
    allowed_domains = ['computerworking.com.co']
    
    # Categorías con sus IDs
    categorias = {
        'https://www.computerworking.com.co/categorias/222/true': 'portatiles',
        'https://www.computerworking.com.co/categorias/310/true': 'computadores',
        'https://www.computerworking.com.co/categorias/169/true': 'accesorios_pc',
        'https://www.computerworking.com.co/categorias/124/true': 'mouse_teclado',
        'https://www.computerworking.com.co/categorias/230/true': 'celulares_tablets',
        'https://www.computerworking.com.co/categorias/390/true': 'televisores',
        'https://www.computerworking.com.co/categorias/241/true': 'audio',
        'https://www.computerworking.com.co/categorias/243/true': 'consolas',
    }
    
    def start_requests(self):
        """Inicia las peticiones para cada categoría"""
        for url_base, categoria_nombre in self.categorias.items():
            self.logger.info(f"[{categoria_nombre}] Iniciando extracción desde: {url_base}")
            
            yield scrapy.Request(
                url_base,
                meta={
                    "playwright": True,
                    "playwright_include_page": True,
                    "playwright_page_methods": [
                        # Esperar a que el contenedor principal cargue
                        PageMethod("wait_for_selector", "div.col-md-9 div.row", timeout=15000),
                        # Esperar a que los productos estén visibles
                        PageMethod("wait_for_selector", "div.col-sm-3 div.productBox", timeout=15000),
                        # Scroll para asegurar que todo esté cargado
                        PageMethod("evaluate", """
                            async () => {
                                // Scroll al final de la página
                                window.scrollTo(0, document.body.scrollHeight);
                                await new Promise(r => setTimeout(r, 2000));
                                // Scroll al inicio
                                window.scrollTo(0, 0);
                                await new Promise(r => setTimeout(r, 1000));
                            }
                        """),
                        # Esperar uno más
                        PageMethod("wait_for_timeout", 3000),
                    ],
                    "categoria_url": categoria_nombre,
                    "url_base": url_base,
                    "pagina": 1,
                },
                callback=self.parse_category
            )
    
    def parse_category(self, response):
        """Extrae productos de la página actual"""
        categoria_url = response.meta.get('categoria_url')
        url_base = response.meta.get('url_base')
        pagina = response.meta.get('pagina', 1)
        
        # Extraer TODOS los productos en la página actual
        # Selector: div.col-sm-3 > div.productBox
        productos = response.css('div.col-sm-3 div.productBox')
        
        self.logger.info(f"[{categoria_url}] Página {pagina}: Se encontraron {len(productos)} elementos productBox")
        
        if len(productos) == 0:
            self.logger.warning(f"[{categoria_url}] ⚠️ NO SE ENCONTRARON PRODUCTOS. HTML disponible:")
            # Mostrar el HTML para debugging
            html_sample = response.css('div.col-md-9').get()
            if html_sample:
                self.logger.info(f"HTML Sample: {html_sample[:500]}")
        
        productos_extraidos = 0
        
        for idx, producto in enumerate(productos):
            try:
                # NOMBRE: div.productCaption h5::text
                nombre = producto.css('div.productCaption h5::text').get()
                if not nombre:
                    nombre = producto.css('div.productCaption h5 span::text').get()
                
                nombre = nombre.strip() if nombre else None
                
                if not nombre:
                    self.logger.debug(f"[{categoria_url}] Producto #{idx+1} sin nombre, saltando")
                    continue
                
                # ENLACE: div.productCaption a::attr(href)
                enlace = producto.css('div.productCaption a::attr(href)').get()
                if not enlace:
                    enlace = producto.css('div.productImage a::attr(href)').get()
                enlace = response.urljoin(enlace) if enlace else None
                
                # IMAGEN: div.productImage img::attr(src)
                imagen = producto.css('div.productImage img::attr(src)').get()
                imagen = response.urljoin(imagen) if imagen else None
                
                # PRECIO: div.productCaption h3::text
                precio_raw = producto.css('div.productCaption h3::text').get()
                if not precio_raw:
                    precio_raw = producto.css('h3::text').get()
                
                # Crear item
                item = AlkostoProjectItem()
                item['nombre'] = nombre
                item['precio'] = self.formatear_precio(precio_raw)
                item['enlace'] = enlace
                item['marca'] = self.extraer_marca(nombre)
                item['imagen'] = imagen
                
                # Categorización inteligente
                categoria_final = self.categorizar(nombre, enlace, categoria_url)
                item['categoria'] = categoria_final
                item['tienda'] = 'Computerworking'
                
                self.logger.info(f"✓ [{categoria_final}] {nombre} - {item['precio']}")
                productos_extraidos += 1
                
                yield item
            
            except Exception as e:
                self.logger.error(f"[{categoria_url}] Error procesando producto #{idx}: {str(e)}")
                continue
        
        self.logger.info(f"[{categoria_url}] Página {pagina}: ✓ {productos_extraidos}/{len(productos)} productos extraídos y guardados")
        
        # PAGINACIÓN
        siguiente_enlaces = response.css('div.pagination a.paginate::attr(href)').getall()
        
        self.logger.info(f"[{categoria_url}] Enlaces de paginación encontrados: {len(siguiente_enlaces)}")
        
        if siguiente_enlaces and pagina < 50:  # Aumenté a 50 páginas máximo
            siguiente_url = siguiente_enlaces[0] if siguiente_enlaces else None
            
            if siguiente_url:
                self.logger.info(f"[{categoria_url}] → Página {pagina + 1}: {siguiente_url}")
                yield scrapy.Request(
                    siguiente_url,
                    meta={
                        "playwright": True,
                        "playwright_include_page": True,
                        "playwright_page_methods": [
                            PageMethod("wait_for_selector", "div.col-md-9 div.row", timeout=15000),
                            PageMethod("wait_for_selector", "div.col-sm-3 div.productBox", timeout=15000),
                            PageMethod("evaluate", """
                                async () => {
                                    window.scrollTo(0, document.body.scrollHeight);
                                    await new Promise(r => setTimeout(r, 2000));
                                    window.scrollTo(0, 0);
                                    await new Promise(r => setTimeout(r, 1000));
                                }
                            """),
                            PageMethod("wait_for_timeout", 3000),
                        ],
                        "categoria_url": categoria_url,
                        "url_base": url_base,
                        "pagina": pagina + 1,
                    },
                    callback=self.parse_category
                )
            else:
                self.logger.info(f"[{categoria_url}] ✓ Fin de la paginación (página {pagina}) - No hay siguiente enlace")
        else:
            if pagina >= 50:
                self.logger.info(f"[{categoria_url}] ⚠️ Límite de 50 páginas alcanzado")
            else:
                self.logger.info(f"[{categoria_url}] ✓ Fin de la paginación (página {pagina})")
    
    def formatear_precio(self, texto):
        """Limpia y formatea el precio"""
        if not texto:
            return "0 COP"
        
        texto = texto.replace('$', '').strip()
        texto = texto.replace(' ', '')
        
        puntos_count = texto.count('.')
        comas_count = texto.count(',')
        
        if puntos_count > 0 and comas_count > 0:
            if texto.rindex('.') > texto.rindex(','):
                texto = texto.replace('.', '').replace(',', '')
            else:
                texto = texto.replace(',', '').replace('.', '')
        elif comas_count > 0:
            texto = texto.replace(',', '')
        elif puntos_count > 0:
            texto = texto.replace('.', '')
        
        solo_numeros = ''.join(filter(str.isdigit, texto))
        
        try:
            precio_int = int(solo_numeros) if solo_numeros else 0
            precio_formateado = f"{precio_int:,}".replace(',', '.')
            return f"{precio_formateado} COP"
        except ValueError:
            return "0 COP"
    
    def extraer_marca(self, nombre):
        """Extrae la marca del nombre del producto"""
        marcas_comunes = [
            'HP', 'LENOVO', 'ASUS', 'APPLE', 'ACER', 'DELL', 'SAMSUNG', 'LG',
            'XIAOMI', 'MOTOROLA', 'HUAWEI', 'REALME', 'OPPO', 'EPSON', 'CANON',
            'KALLEY', 'VIVO', 'INTEL', 'AMD', 'RYZEN', 'CORE', 'GENIUS', 'LOGITECH',
            'COUGAR', 'EASY', 'FORZA', 'JAITECH', 'KAISE', 'MACSYSTEM', 'MACON',
            'NICOMAR', 'POWEST', 'UNITEC', 'VARIOS', 'WACOM', 'WATTANA', 'DRACO',
            'DIGITAL', 'POWER GROUP', 'JALTECH', 'NUC', 'GAMER', 'TORRE', 'MINI PC',
            'HYUNDAI', 'HISENSE', 'SONY', 'PANASONIC', 'SHARP', 'TCL', 'PHILIPS',
            'SENNHEISER', 'BOSE', 'BEATS', 'JBL', 'SKULLCANDY',
            'PLANTRONICS', 'CORSAIR', 'RAZER', 'STEELSERIES', 'TURTLE BEACH'
        ]
        
        nombre_upper = nombre.upper()
        marca = next((m for m in marcas_comunes if m in nombre_upper), None)
        
        return marca if marca else "GENÉRICA"
    
    def categorizar(self, nombre, enlace, categoria_url):
        """Categorización inteligente"""
        texto = (str(nombre) + ' ' + str(enlace or '')).lower()
        
        # Prioridad 1: Móviles y Tablets
        if 'celulares' in categoria_url or 'tablets' in categoria_url:
            if any(k in texto for k in ['tablet', 'tableta', 'ipad']):
                return 'tablets'
            elif any(k in texto for k in ['celular', 'smartphone', 'iphone', 'telefono', 'teléfono', 'moto', 'galaxy', 'xiaomi', 'realme', 'vivo', 'oppo']):
                return 'celulares'
            else:
                return 'celulares'
        
        # Prioridad 2: Televisores
        elif 'televisores' in categoria_url:
            return 'pantallas'
        
        # Prioridad 3: Audio
        elif 'audio' in categoria_url:
            return 'audio'
        
        # Prioridad 4: Consolas
        elif 'consolas' in categoria_url or 'gamer' in categoria_url:
            return 'consolas'
        
        # Prioridad 5: Computadores y Portátiles
        elif 'computadores' in categoria_url or 'portatiles' in categoria_url:
            if any(k in texto for k in ['portátil', 'laptop', 'notebook']):
                return 'portatiles'
            else:
                return 'computadores'
        
        # Prioridad 6: Accesorios
        elif 'accesorios' in categoria_url or 'mouse' in categoria_url:
            if any(k in texto for k in ['mouse', 'teclado']):
                return 'mouse_teclado'
            else:
                return 'accesorios_pc'
        
        # Fallback
        return 'otros'
