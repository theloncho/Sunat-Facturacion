# 🧾 Sistema de Facturación Electrónica SUNAT-ready (Perú)

![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)
![Django](https://img.shields.io/badge/Django-4.2+-092E20.svg)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-336791.svg)
![Docker](https://img.shields.io/badge/Docker-Ready-2496ED.svg)

Sistema web robusto para la emisión de comprobantes de pago electrónicos (Facturas, Boletas y Notas de Crédito) cumpliendo con la normativa de la **SUNAT** (Superintendencia Nacional de Aduanas y de Administración Tributaria del Perú) y el estándar **UBL 2.1**.

## 🌟 Características Principales

* **✅ Emisión Electrónica:** Generación de Facturas (F001), Boletas (B001) y Notas de Crédito (FC01/BC01).
* **🧾 Estándar UBL 2.1:** Generación estricta de archivos XML estructurados según validaciones XSD de SUNAT.
* **✍️ Firma Digital (XMLDSig):** Integración nativa para firma de comprobantes usando certificados digitales `.pfx`.
* **🔌 Integración SOAP:** Comunicación directa con el servicio web de SUNAT (`billService`) vía Zeep.
* **🛡️ Modo Simulador (Mock):** Permite pruebas académicas o de desarrollo sin depender del servidor Beta de SUNAT (90% aceptación simulada).
* **📊 Reportes Tributarios:** Libro de ventas en tiempo real con exportación a Excel profesional (`openpyxl`).
* **🐳 Dockerizado:** Orquestación completa con `docker-compose` (App + PostgreSQL + pgAdmin).

## 🏗️ Arquitectura y Tecnologías

El proyecto sigue una arquitectura MVT (Model-View-Template) escalable y separada en aplicaciones (`apps/`).

| Capa | Tecnología |
|---|---|
| **Backend Framework** | Django 4.2 |
| **Base de Datos** | PostgreSQL 15 |
| **Frontend** | HTML5, CSS3, Bootstrap 5, Alpine.js |
| **API REST** | Django REST Framework (DRF) |
| **Autenticación** | JWT (SimpleJWT) y Session Auth |
| **Procesamiento XML/SOAP**| `lxml`, `zeep`, `signxml` |
| **Generación PDF / Excel** | `reportlab`, `openpyxl` |
| **Despliegue** | Docker, Docker Compose |

## ⚙️ Variables de Entorno (`.env`)

El sistema es altamente configurable a través de variables de entorno. Asegúrate de tener tu archivo `.env` configurado:

```env
# Configuración Django
SECRET_KEY=tu_secreto_aqui
DEBUG=True

# Configuración Base de Datos
DATABASE_NAME=facturaSunat
DATABASE_USER=postgres
DATABASE_PASSWORD=postgres123
DATABASE_HOST=db  # Usa 'localhost' si ejecutas sin Docker
DATABASE_PORT=5432

# Credenciales SUNAT (Ambiente Beta / Producción)
SUNAT_RUC=20000000001
SUNAT_USER=MODDATOS
SUNAT_PASSWORD=MODDATOS

# Configuración de Certificado Digital
SUNAT_CERT_PATH=certificates/certificate.pfx
SUNAT_CERT_PASSWORD=12345678

# Modo del Sistema
# True: Intenta conectar al servidor real de SUNAT Beta
# False: Usa el Mock de Simulación (Aceptación automática para pruebas)
SUNAT_BETA_MODE=False 
```

## 🚀 Instalación y Ejecución

### Opción A: Con Docker (Recomendado)

Esta es la forma más rápida y evita problemas de compatibilidad de dependencias.

```bash
# 1. Clonar el repositorio
git clone https://github.com/theloncho/Sunat-Facturacion.git
cd Sunat-Facturacion

# 2. Levantar los contenedores (App, PostgreSQL, pgAdmin)
docker-compose up --build

# 3. En otra terminal, aplicar migraciones e inyectar datos de prueba
docker-compose exec web python manage.py migrate
docker-compose exec web python manage.py loaddata fixtures/initial_data.json
docker-compose exec web python manage.py createsuperuser

# 4. Acceder a los servicios
# Aplicación Web: http://localhost:8001
# pgAdmin (BD):   http://localhost:5050 (admin@admin.com / admin123)
```

### Opción B: Entorno Local Tradicional

```bash
# 1. Crear entorno virtual e instalar dependencias
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt

# 2. Asegúrate de tener PostgreSQL corriendo localmente
# Actualiza DATABASE_HOST=localhost en tu .env

# 3. Migrar y cargar datos
python manage.py migrate
python manage.py loaddata fixtures/initial_data.json

# 4. Ejecutar servidor
python manage.py runserver 8000
```

## 📚 Modelo Matemático Tributario

El motor tributario de la aplicación (`apps.comprobantes.services`) realiza los cálculos bajo la normativa peruana de la siguiente manera:

```text
Base Imponible (Afecto) = Σ (Cantidad × Precio Unitario × (1 - Descuento/100))
IGV (18%)               = Base Imponible × 0.18
Operaciones Inafectas   = Σ (Productos marcados como inafectos)
Total a Pagar           = Base Imponible + IGV + Operaciones Inafectas
```

## 🌐 Endpoints API REST

El proyecto expone una API completa para integraciones de terceros. (Documentación completa disponible en `/api/docs/` vía Swagger).

| Método | Endpoint | Descripción |
|---|---|---|
| `POST` | `/api/facturas/` | Genera y emite Factura (RUC obligatorio) |
| `POST` | `/api/boletas/` | Genera y emite Boleta (DNI/RUC/CE) |
| `POST` | `/api/notas-credito/` | Emite NC referenciando un comprobante original |
| `GET` | `/api/comprobantes/{id}/pdf/` | Retorna el archivo PDF (A4/Ticket) |
| `POST` | `/api/comprobantes/{id}/reenviar/` | Reintenta envío de comprobantes rechazados |
| `GET` | `/api/reportes/ventas/` | Exporta el libro de ventas |

## 🧪 Pruebas Automatizadas (Testing)

El sistema cuenta con pruebas automatizadas para garantizar la precisión de los cálculos tributarios y la generación XML.

```bash
# Ejecutar todas las pruebas (dentro de Docker)
docker-compose exec web pytest

# Generar reporte de cobertura HTML
docker-compose exec web pytest --cov=apps --cov-report=html
```

## 🎓 Contexto Académico

Este proyecto fue desarrollado como **Evidencia de Producto (EP)** para el curso **Taller de Lenguajes de Programación** (Ciclo IX) de la **Universidad Señor de Sipán** (Chiclayo, Perú - 2026). 

Demuestra la capacidad de analizar, modelar y construir un sistema complejo con requerimientos estrictos dictados por una entidad gubernamental (SUNAT), aplicando buenas prácticas de Ingeniería de Software (Arquitectura MVT, Dockerización, Integración de APIs SOAP, y Diseño de Base de Datos Relacional).

---
*Desarrollado con mucho para la automatización financiera en el Perú.*