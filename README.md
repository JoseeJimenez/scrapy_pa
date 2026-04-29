# 🛒 Multi-Store Tech Scraper - Alkosto Edition

![Python](https://img.shields.io/badge/Python-3.x-blue?logo=python&logoColor=white)
![Scrapy](https://img.shields.io/badge/Scrapy-2.8+-green?logo=scrapy)
![MongoDB](https://img.shields.io/badge/MongoDB-Atlas-brightgreen?logo=mongodb)
![License](https://img.shields.io/badge/License-MIT-yellow)

Un web scraper avanzado y automatizado diseñado para extraer información detallada de productos tecnológicos desde **Alkosto**, incluyen computadores, celulares y tablets.

## 📋 Tabla de Contenidos

- [Descripción](#descripción)
- [Características](#características)
- [Requisitos](#requisitos)
- [Instalación](#instalación)
- [Configuración](#configuración)
- [Uso](#uso)
- [Estructura del Proyecto](#estructura-del-proyecto)
- [Tecnologías](#tecnologías)
- [Contribuciones](#contribuciones)

---

## 📝 Descripción

Este proyecto implementa un web scraper profesional que automatiza la extracción de datos de productos tecnológicos de **Alkosto**. Utiliza las últimas tecnologías en scraping y es capaz de gestionar contenido dinámico generado por JavaScript.

### Casos de Uso:
- 📊 Análisis competitivo de precios
- 📈 Seguimiento de inventario
- 💹 Comparativa de productos tecnológicos
- 🔍 Investigación de mercado

---

## ⭐ Características

### 🚀 Navegación Dinámica
- Interacción automática con botones de "Cargar más"
- Renderizado completo de JavaScript mediante **Playwright**
- Gestión inteligente de elementos dinámicos

### 📦 Bucle Multi-Categoría
- Extracción automatizada de múltiples secciones en una sola ejecución
- Soporte para:
  - 💻 Computadores
  - 📱 Celulares
  - 📲 Tablets

### 🔧 Procesamiento de Datos
- ✅ Normalización de precios a formato numérico
- ✅ Categorización automática basada en palabras clave
- ✅ Extracción inteligente de marcas con lógica de fallback
- ✅ Limpieza y validación de datos

### 💾 Persistencia
- Integración directa con **MongoDB Atlas**
- Almacenamiento escalable en la nube
- Sincronización automática de datos

### ⚙️ Compatibilidad
- Configuración optimizada de Asyncio para Windows
- Compatible con sistemas Unix/Linux
- Gestión automática de errores y reintentos

---

## 📋 Requisitos

- **Python**: 3.7 o superior
- **Sistema Operativo**: Windows, macOS, Linux
- **Base de Datos**: MongoDB Atlas (cuenta requerida)
- **Conexión a Internet**: Estable

---

## 🔧 Instalación

### 1. Clonar el repositorio

```bash
git clone https://github.com/JoseeJimenez/scrapy_pa.git
cd scrapy_pa
```

### 2. Crear un entorno virtual

```bash
# En Windows
python -m venv venv
venv\Scripts\activate

# En macOS/Linux
python3 -m venv venv
source venv/bin/activate
```

### 3. Instalar dependencias

```bash
pip install -r requirements.txt
```

### 4. Instalar navegadores de Playwright

```bash
playwright install
```

---

## ⚙️ Configuración

### 1. Variables de Entorno

Crea un archivo `.env` en la raíz del proyecto:

```env
# MongoDB Atlas
MONGO_URI=mongodb+srv://<usuario>:<contraseña>@<cluster>.mongodb.net/<base_de_datos>?retryWrites=true&w=majority

# Configuración opcional
PROXY_URL=<opcional>
REQUEST_TIMEOUT=30
MAX_RETRIES=3
```

### 2. Instalación de Navegadores

```bash
playwright install chromium
```

---

## 🚀 Uso

### Ejecutar el Scraper

```bash
# Ejecutar todos los spiders
scrapy crawl alkosto

# Ejecutar un spider específico (computadores)
scrapy crawl alkosto -a category=computadores

# Con niveles de log
scrapy crawl alkosto -L DEBUG
```

### Comandos Útiles

```bash
# Listar todos los spiders disponibles
scrapy list

# Ver información del proyecto
scrapy info

# Crear un nuevo spider
scrapy genspider nuevo_spider ejemplo.com
```

---

## 📂 Estructura del Proyecto

```
scrapy_pa/
├── README.md                      # Este archivo
├── requirements.txt               # Dependencias del proyecto
├── .gitignore                    # Archivos ignorados por Git
└── alkosto_project/              # Proyecto principal de Scrapy
    ├── scrapy.cfg               # Configuración de Scrapy
    ├── alkosto_project/
    │   ├── __init__.py
    │   ├── items.py             # Definición de items/esquemas
    │   ├── pipelines.py         # Procesamiento de datos
    │   ├── settings.py          # Configuración global
    │   ├── middlewares.py       # Middlewares personalizados
    │   ├── spiders/             # Spiders (scrapers)
    │   │   ├── __init__.py
    │   │   └── alkosto.py       # Spider principal
    │   └── utils/               # Utilidades
    │       └── helpers.py
    └── tests/                   # Pruebas unitarias
```

---

## 🛠️ Tecnologías Utilizadas

| Tecnología | Versión | Propósito |
|-----------|---------|----------|
| **Python** | 3.x | Lenguaje principal |
| **Scrapy** | ≥2.8 | Framework de scraping |
| **Playwright** | ≥1.40.0 | Automatización de navegador |
| **scrapy-playwright** | 0.0.46-0.1.0 | Integración Scrapy-Playwright |
| **PyMongo** | ≥4.0 | Controlador MongoDB |
| **python-dotenv** | ≥1.0.0 | Gestión de variables de entorno |
| **itemadapter** | ≥0.8 | Adaptador de items |

---

## 📊 Ejemplos de Datos Extraídos

### Estructura de Producto

```python
{
    "nombre": "Computador Portátil Dell XPS 13",
    "precio": 2899.99,
    "marca": "Dell",
    "categoría": "computadores",
    "enlace": "https://www.alkosto.com/...",
    "disponibilidad": "En stock",
    "especificaciones": {
        "procesador": "Intel i7",
        "ram": "16GB",
        "almacenamiento": "512GB SSD"
    },
    "fecha_extracción": "2026-04-29T10:30:00Z"
}
```

---

## ⚠️ Consideraciones Importantes

### Ética y Legalidad
- ⚠️ Respeta el archivo `robots.txt` del sitio
- ⚠️ Revisa los términos de servicio de Alkosto
- ⚠️ No sobrecargues los servidores (implementa delays)
- ⚠️ Usa responsablemente

### Mejores Prácticas
- Implementa delays entre solicitudes
- Usa rotación de user-agents
- Maneja excepciones apropiadamente
- Monitorea el consumo de recursos

---

## 🐛 Solución de Problemas

### Problema: Error de conexión a MongoDB
```bash
# Verifica tu cadena de conexión en .env
# Asegúrate de que tu IP esté en la whitelist de MongoDB Atlas
```

### Problema: Playwright no carga
```bash
# Reinstala los navegadores
playwright install --with-deps chromium
```

### Problema: Timeout en solicitudes
```bash
# Aumenta el timeout en settings.py
DOWNLOAD_TIMEOUT = 60
```

---

## 📝 Logging y Monitoreo

El scraper genera logs detallados:

```
2026-04-29 10:30:00 [scrapy.core.engine] INFO: Spider opened
2026-04-29 10:30:02 [alkosto] INFO: Extrayendo productos de categoría: computadores
2026-04-29 10:35:45 [alkosto] INFO: Total de productos extraídos: 1250
```

---

## 🤝 Contribuciones

Las contribuciones son bienvenidas. Por favor:

1. **Fork** el repositorio
2. Crea una **rama** para tu feature (`git checkout -b feature/AmazingFeature`)
3. **Commit** tus cambios (`git commit -m 'Add AmazingFeature'`)
4. **Push** a la rama (`git push origin feature/AmazingFeature`)
5. Abre un **Pull Request**

### Reportar Bugs
Si encuentras algún bug, por favor abre un **issue** con:
- Descripción clara del problema
- Pasos para reproducirlo
- Tu entorno (SO, versión de Python, etc.)

---

## 📄 Licencia

Este proyecto está bajo la licencia **MIT**. Ver el archivo `LICENSE` para más detalles.

---

## 📧 Contacto

**Autor**: [JoseeJimenez](https://github.com/JoseeJimenez)

Para preguntas o sugerencias, abre un **issue** en este repositorio.

---

## 🙏 Agradecimientos

- [Scrapy](https://scrapy.org/) - Framework de scraping
- [Playwright](https://playwright.dev/) - Automatización de navegadores
- [MongoDB](https://www.mongodb.com/) - Base de datos
- La comunidad de código abierto

---

<div align="center">

**⭐ Si este proyecto te fue útil, considera darle una estrella ⭐**

</div>