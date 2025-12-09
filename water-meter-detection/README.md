# Sistema de Lectura Automática de Contadores de Agua (IoT + Visión Artificial)

Este proyecto implementa un sistema completo para la digitalización automática de lecturas de contadores de agua mecánicos analógicos. Utiliza un dispositivo IoT (ESP32-CAM) para la captura de imágenes en campo, un sistema de procesamiento basado en Inteligencia Artificial (YOLOv11) para extraer los dígitos, y se integra con un sistema Django (`water_monitoring`) para almacenar las lecturas en una base de datos PostgreSQL.

## 📋 Tabla de Contenidos

1.  [Descripción del Flujo de Trabajo](#-descripción-del-flujo-de-trabajo)
2.  [Estructura del Proyecto](#-estructura-del-proyecto)
3.  [Requisitos de Hardware y Software](#-requisitos)
4.  [Instalación y Configuración](#️-instalación-y-configuración)
5.  [Instrucciones de Uso](#-instrucciones-de-uso)
6.  [Solución de Problemas Comunes](#-solución-de-problemas-comunes)

-----

## 🔄 Descripción del Flujo de Trabajo

El sistema opera en una modalidad de **Procesamiento en Tiempo Real con Persistencia en Base de Datos**. El ciclo de vida completo del dato es:

1.  **Captura (Edge - ESP32-CAM):** 
    - La **ESP32-CAM** se despierta automáticamente
    - Inicializa el sensor OV2640 y ajusta parámetros de exposición y balance de blancos
    - Captura la imagen del contador de agua

2.  **Transmisión WiFi:** 
    - La imagen se envía vía POST a `http://backend:8001/upload`
    - Backend Python (FastAPI) recibe los datos binarios de la imagen

3.  **Preprocesamiento (Backend Python):** 
    - Script `main.py` guarda la imagen en `captured_images/`
    - Aplica `preprocessing.process_image()`: recorte y conversión a escala de grises

4.  **Inferencia IA (YOLOv11):** 
    - El modelo **YOLOv11** (best_m.pt) detecta cajas delimitadoras de dígitos (0-9)
    - Extrae: clase (dígito), posición X, nivel de confianza

5.  **Reconstrucción de Lectura:** 
    - Los dígitos se ordenan de **izquierda a derecha** según coordenada X
    - Se construye la lectura completa (ej: "12345")

6.  **Doble Persistencia:**
    - **CSV Local (respaldo):** `medidas_contador.csv` - archivo de respaldo local
    - **Base de Datos PostgreSQL:** Se envía automáticamente a Django (`water_monitoring`)
      - Endpoint: `POST /api/public/reading/`
      - Payload: `{meter_id, accumulated_value, timestamp}`
      - **Requisito crítico:** El contador con `meter_id` debe existir previamente en Django

7.  **Almacenamiento y Análisis (Django):**
    - Django recibe la lectura y la almacena en PostgreSQL
    - Calcula automáticamente el consumo vs lectura anterior
    - Actualiza dashboard con mapa interactivo y gráficas en tiempo real

### ⚠️ Importante: Prerrequisitos

- El **contador debe estar registrado** en el sistema Django ANTES de enviar lecturas
- El `meter_id` configurado en `main.py` (DEFAULT_METER_ID) debe coincidir con un contador existente
- El servidor Django debe estar corriendo en `http://127.0.0.1:8000/`

-----

## 📂 Estructura del Proyecto

El repositorio funciona como un *Monorepo*, conteniendo tanto el firmware como el software de análisis:

```text
water-meter-detection/
│
├── client_esp32/              # Firmware C++ para el dispositivo IoT
│   ├── src/main.cpp           # Código principal de captura y transmisión WiFi
│   ├── platformio.ini         # Configuración de compilación y hardware
│   └── ...
│
├── backend_python/            # Software de procesamiento e IA + API
│   ├── notebooks/             # Notebook de entrenamiento YOLO (Google Colab)
│   ├── src/
│   │   ├── preprocessing.py   # Funciones de preprocesamiento de imagen
│   │   └── main.py            # Servidor FastAPI + Inferencia YOLO + Integración Django
│   ├── trained_models/        # Modelos YOLO (.pt)
│   │   └── local/best_m.pt    # Modelo YOLO entrenado
│   ├── captured_images/       # Imágenes capturadas y procesadas
│   ├── requirements.txt       # Dependencias de Python
│   └── medidas_contador.csv   # [Salida] Archivo CSV de respaldo local
│
└── README.md                  # Este archivo

```

## 🏗️ Arquitectura del Sistema Completo

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         SISTEMA COMPLETO                                │
└─────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────┐
│ 1. EDGE (Campo) - ESP32-CAM                                              │
├──────────────────────────────────────────────────────────────────────────┤
│  • Captura imagen del contador cada N segundos                          │
│  • Transmite vía WiFi a servidor FastAPI                                │
│  • POST http://servidor:8001/upload (imagen binaria)                    │
└────────────────────────────────┬─────────────────────────────────────────┘
                                 │
                                 ▼
┌──────────────────────────────────────────────────────────────────────────┐
│ 2. BACKEND IA (water-meter-detection) - FastAPI + YOLOv11               │
├──────────────────────────────────────────────────────────────────────────┤
│  Endpoint: POST /upload                                                  │
│  ├─ Guarda imagen en captured_images/                                   │
│  ├─ preprocessing.process_image() → Recorte + escala de grises          │
│  ├─ YOLO(best_m.pt) → Detecta dígitos 0-9                               │
│  ├─ Ordena dígitos por posición X (izq → der)                           │
│  ├─ Construye lectura: "12345"                                           │
│  ├─ save_reading() → Guarda en medidas_contador.csv (RESPALDO)          │
│  └─ send_to_django() → Envía a base de datos                            │
└────────────────────────────────┬─────────────────────────────────────────┘
                                 │
                                 │ POST /api/public/reading/
                                 │ {
                                 │   "meter_id": "MTR001",
                                 │   "accumulated_value": 12345,
                                 │   "timestamp": "2024-12-09T10:30:00Z"
                                 │ }
                                 ▼
┌──────────────────────────────────────────────────────────────────────────┐
│ 3. BACKEND WEB (water_monitoring) - Django + PostgreSQL                 │
├──────────────────────────────────────────────────────────────────────────┤
│  API Endpoint: POST /api/public/reading/                                │
│  ├─ ⚠️ VALIDA: ¿Existe contador con meter_id="MTR001"?                  │
│  │   └─ SI: Continúa | NO: Error 400                                    │
│  ├─ Crea ConsumptionReading en PostgreSQL                               │
│  ├─ Calcula consumo vs lectura anterior                                 │
│  ├─ Almacena con coordenadas PostGIS                                    │
│  └─ Retorna: {"success": true, "reading_id": 456, ...}                  │
└────────────────────────────────┬─────────────────────────────────────────┘
                                 │
                                 ▼
┌──────────────────────────────────────────────────────────────────────────┐
│ 4. FRONTEND (Dashboard Django)                                           │
├──────────────────────────────────────────────────────────────────────────┤
│  • Mapa interactivo (Leaflet + PostGIS)                                 │
│  • Gráficas de consumo (Chart.js)                                       │
│  • Estadísticas en tiempo real                                          │
│  • Panel de administración SPA                                          │
│  URL: http://127.0.0.1:8000/                                            │
└──────────────────────────────────────────────────────────────────────────┘
```

### 🔑 Puntos Críticos de Integración

1. **Requisito de Pre-registro:** El contador DEBE existir en Django antes de enviar lecturas
2. **Sincronización de IDs:** `DEFAULT_METER_ID` en `main.py` = `meter_id` en Django
3. **Doble persistencia:** CSV local (respaldo) + PostgreSQL (producción)
4. **Validación de lecturas:** Solo se envían a Django lecturas numéricas válidas
5. **Manejo de errores:** Si Django no responde, se guarda solo en CSV local

-----
│
└── README.md                  # Documentación del proyecto
```

-----

## 🛠 Requisitos

### Hardware

  * **ESP32-CAM:** Modelo AI-Thinker (con sensor OV2640).
  * **Fuente de Alimentación:** Cargador USB de 5V/2A (Conexión directa a pines 5V/GND recomendada para estabilidad), o bateria.
  * **Conversor FTDI o Base MB:** Solo necesario para cargar el código la primera vez.

### Software

  * **VS Code:** Editor de código principal.
  * **PlatformIO (Extensión VS Code):** Para compilar y subir código a la ESP32.
  * **Python 3.10+:** Para correr el script de análisis.

-----

## ⚙️ Instalación y Configuración

### 0\. **PREREQUISITO: Configurar y Ejecutar el Sistema Django**

**⚠️ IMPORTANTE:** Antes de usar el sistema de detección, debes tener el sistema Django corriendo:

1.  Ve al proyecto `water_monitoring/` y sigue su README para:
    - Instalar dependencias
    - Configurar PostgreSQL + PostGIS
    - Ejecutar migraciones
    - Crear el superusuario

2.  **Crear el contador en Django:**
    ```bash
    cd water_monitoring
    python manage.py runserver
    ```
    - Accede a http://127.0.0.1:8000/admin/
    - Ve a "Meters" → "Add Meter"
    - Crea un contador con `meter_id = "MTR001"` (o el ID que prefieras)
    - Asegúrate de que el contador esté **activo** (is_active = True)

3.  **Configurar el meter_id en este proyecto:**
    - Edita `backend_python/src/main.py`
    - Línea 27: `DEFAULT_METER_ID = "MTR001"` (usa el ID que creaste en Django)

### 1\. Configurar el Firmware (ESP32)

1.  Abre la carpeta `client_esp32` con VS Code.
2.  Asegúrate de tener instalada la extensión **PlatformIO**.
3.  Edita `src/main.cpp` y configura:
    ```cpp
    const char* ssid = "TU_RED_WIFI";
    const char* password = "TU_PASSWORD";
    const char* serverUrl = "http://IP_DEL_SERVIDOR:8001/upload";
    ```
4.  Conecta la ESP32 al PC.
5.  Haz clic en el botón de **Upload (Flecha Derecha ➡️)** en la barra inferior de PlatformIO.
6.  Una vez cargado, desconecta la ESP32 del PC.

### 2\. Configurar el Entorno Python

1.  Abre una terminal en la carpeta `backend_python`.
2.  Crea un entorno virtual (recomendado):
    ```bash
    python -m venv .venv
    ```
3.  Activa el entorno:
      * Windows: `.venv\Scripts\activate`
      * Mac/Linux: `source .venv/bin/activate`
4.  Instala las librerías necesarias:
    ```bash
    pip install -r requirements.txt
    ```

### 3\. Verificar Configuración de URLs

En `backend_python/src/main.py`, verifica que las URLs sean correctas:

```python
# Django API Configuration (línea 26-27)
DJANGO_API_URL = "http://127.0.0.1:8000/api/public/reading/"  # URL del sistema Django
DEFAULT_METER_ID = "MTR001"  # Debe coincidir con un contador existente en Django
```
4.  Instala las librerías necesarias:
    ```bash
    pip install -r requirements.txt
    ```

-----

## 🚀 Instrucciones de Uso

### Paso 0: Iniciar el Sistema Django (REQUERIDO)

**⚠️ El sistema Django debe estar corriendo ANTES de ejecutar el backend de detección:**

```bash
# Terminal 1: Sistema Django
cd water_monitoring
python manage.py runserver
# Debe estar corriendo en http://127.0.0.1:8000/
```

Verifica que esté funcionando visitando: http://127.0.0.1:8000/admin/

### Paso 1: Iniciar el Backend de Detección (Servidor FastAPI)

```bash
# Terminal 2: Backend de detección
cd water-meter-detection/backend_python
python src/main.py
# Servidor FastAPI corriendo en http://0.0.0.0:8001/
```

El servidor estará escuchando en dos endpoints:
- `POST /upload` - Para recibir imágenes desde ESP32
- `POST /test-web` - Para pruebas desde interfaz web

### Paso 2: Captura y Procesamiento Automático

#### **Opción A: Desde ESP32-CAM (Producción)**

1.  Conecta la ESP32 a una fuente de energía (Batería o Cargador USB 5V/2A)
2.  El LED rojo parpadeará al capturar cada foto
3.  La ESP32 enviará automáticamente la imagen al servidor FastAPI
4.  El flujo automático será:
    ```
    ESP32 → FastAPI (/upload) → YOLO → Lectura → Django (PostgreSQL)
    ```

#### **Opción B: Prueba desde Web**

1.  Usa Postman, curl o cualquier cliente HTTP
2.  Envía una imagen a `http://localhost:8001/test-web`:
    ```bash
    curl -X POST -F "file=@imagen_contador.jpg" http://localhost:8001/test-web
    ```

### Paso 3: Verificar Resultados

**En el backend de detección:**
- Consola mostrará: dígitos detectados, posición X, confianza
- Logs de sincronización con Django (✅ éxito o ❌ error)

**En el sistema Django:**
- Dashboard: http://127.0.0.1:8000/
- Verifica el mapa interactivo con la nueva lectura
- Ve a http://127.0.0.1:8000/admin/meters/consumptionreading/ para ver lecturas

**Archivos locales (respaldo):**
- `backend_python/medidas_contador.csv` - Todas las lecturas
- `backend_python/captured_images/` - Imágenes capturadas
- `backend_python/captured_images/YOLO/` - Imágenes con detecciones YOLO

### 🔍 Logs y Monitoreo

**Terminal FastAPI mostrará:**
```
Recibidos 45678 bytes
[ESP32] Imagen guardada en: img_20241209_143025_esp32.jpg
--> Detectado: 1 | Posicion_x: 45.2 | Confianza: 0.95
--> Detectado: 2 | Posicion_x: 78.4 | Confianza: 0.92
--> Detectado: 3 | Posicion_x: 112.1 | Confianza: 0.89
Lectura detectada: 123
✅ Lectura enviada exitosamente a Django: {'reading_id': 456, 'meter_id': 'MTR001', ...}
```

**Si hay errores:**
```
⚠️ Lectura inválida, no se envió a Django: Error: No se detectaron numeros
❌ No se pudo conectar con Django API en http://127.0.0.1:8000/api/public/reading/
❌ Error al enviar a Django (400): {"meter_id": ["Meter with this ID does not exist"]}
```

-----

## ❓ Solución de Problemas Comunes

| Problema | Causa Probable | Solución |
| :--- | :--- | :--- |
| **"Connection error - Django server not available"** | Django no está corriendo | Ejecuta `python manage.py runserver` en `water_monitoring/` |
| **"Meter with this ID does not exist"** | El contador no existe en Django | Crea el contador en Django Admin con el `meter_id` correcto |
| **"Invalid reading format"** | YOLO no detectó números o detectó texto inválido | Verifica iluminación, enfoque de la cámara, y preprocesamiento |
| **Fotos con colores raros (verde/rosa)** | Fallo de alimentación o sensor saturado | Asegurar alimentación robusta de 5V/2A |
| **El modelo no detecta números** | Iluminación pobre o reflejos | Mejorar iluminación o ajustar parámetros en `preprocessing.py` |
| **Lectura detectada pero no se guarda en DB** | Lectura contiene "Error" o no es numérica | Revisar logs de YOLO, mejorar calidad de imagen |
| **Django devuelve error 400** | Formato de payload incorrecto o timestamp inválido | Verifica que `meter_id` existe y `accumulated_value` es numérico |