# 🛒 Multi-Store Tech Scraper - Colombia Edition

![Python](https://img.shields.io/badge/Python-3.x-blue?logo=python&logoColor=white)
![Scrapy](https://img.shields.io/badge/Scrapy-2.8+-green?logo=scrapy)
![Playwright](https://img.shields.io/badge/Playwright-Automated-orange?logo=playwright)
![MongoDB](https://img.shields.io/badge/MongoDB-Atlas-brightgreen?logo=mongodb)
![Status](https://img.shields.io/badge/Repo-Privado-red)

Un ecosistema avanzado de web scraping diseñado para la extracción masiva y automatizada de productos tecnológicos de las principales tiendas en Colombia. Este proyecto es una solución robusta para el monitoreo de precios y análisis de mercado en tiempo real.

## 📋 Tabla de Contenidos

- [Descripción](#descripción)
- [Tiendas Soportadas](#-tiendas-soportadas)
- [Características Técnicas](#-características-técnicas)
- [Requisitos](#requisitos)
- [Instalación](#instalación)
- [Uso y Ejecución](#-uso-y-ejecución)
- [Estructura del Proyecto](#estructura-del-proyecto)
- [Equipo de Desarrollo](#-equipo-de-desarrollo)

---

## 📝 Descripción

Este proyecto implementa un sistema multi-tienda capaz de navegar sitios web modernos con renderizado dinámico. Gracias a la integración de **Scrapy** y **Playwright**, los spiders pueden interactuar con interfaces complejas (React, Next.js, etc.) para extraer datos precisos de:
- 💻 Computadores y Portátiles
- 📱 Celulares y Tablets
- 🎮 Componentes Gaming y Periféricos

### Casos de Uso:
- 📊 **Análisis competitivo**: Comparativa entre las 6 tiendas tecnológicas más grandes del país.
- 📈 **Histórico de precios**: Rastreo de variaciones y detección de ofertas reales.
- 💹 **Business Intelligence**: Recolección de datos para toma de decisiones comerciales.

---

## 🏢 Tiendas Soportadas

El sistema cuenta con 6 spiders especializados y optimizados:

| Tienda | Spider Name | Enfoque |
| :--- | :--- | :--- |
| **Alkosto** | `alkosto` | Líder en consumo masivo tech |
| **Éxito** | `exito` | Gran retail nacional |
| **Falabella** | `falabella` | Multinacional de retail |
| **Tauret Computadores** | `tauretcomputadores` | Especialistas en Gaming/High-end |
| **CompuLago** | `compulago` | Hardware y periféricos |
| **CompuWorking** | `compuworking` | Soluciones corporativas y hardware |

---

## ⭐ Características Técnicas

- **Renderizado Dinámico**: Manejo de JavaScript mediante `scrapy-playwright`.
- **Evasión de Bloqueos**: Rotación de cabeceras y gestión de tiempos de espera inteligentes.
- **Pipelines de Limpieza**: Normalización automática de precios (quitar símbolos, puntos y convertir a tipo numérico).
- **Persistencia en la Nube**: Conexión directa con clústeres de **MongoDB Atlas**.

---

## 🔧 Instalación y Configuración

1. **Clonar el repositorio**:
   ```bash
   git clone https://github.com/JoseeJimenez/scrapy_pa.git
   cd scrapy_pa
   ```

2. **Preparar el entorno**:
   ```bash
   python -m venv venv
   # Activar: venv\Scripts\activate (Win) o source venv/bin/activate (Unix)
   pip install -r requirements.txt
   playwright install chromium
   ```

3. **Variables de Entorno**:
   Configura tu archivo `.env` con la URI de tu base de datos:
   ```env
   MONGO_URI=tu_conexion_mongodb_atlas
   ```

---

## 🚀 Uso y Ejecución

Para ejecutar cualquiera de los 6 spiders disponibles:

```bash
# Ejemplo para ejecutar Tauret
scrapy crawl tauretcomputadores

# Ejemplo para ejecutar Falabella con salida a archivo
scrapy crawl falabella -o datos.json
```

---

## 📂 Estructura del Proyecto

```text
alkosto_project/
├── spiders/                 # Los 6 Spiders (Alkosto, Éxito, Falabella, etc.)
├── items.py                 # Modelo de datos unificado
├── pipelines.py             # Procesamiento y guardado en Mongo
├── settings.py              # Configuración de Playwright y Scrapy
└── utils/                   # Herramientas de apoyo
```

---

## 👥 Equipo de Desarrollo

Este proyecto fue desarrollado con dedicación por:

*   **Lucho Jimenez**
*   **Diego Serpa**
*   **Cesar Jimenez**
*   **Bibi Ledesma**

### 🎓 Mención Especial
Un agradecimiento total a nuestro profesor **Chavarriga**, quien nos guio en el proceso y nos dio las bases para montar este proyecto bien cartelúo.

---
<div align="center">
  <b>© 2026 - Proyecto Privado de Web Scraping</b>
</div>
