import preprocessing
import pandas as pd
import uvicorn
import cv2
import shutil
import requests
from fastapi import FastAPI, Request, File, UploadFile
from ultralytics import YOLO
from pathlib import Path
from datetime import datetime

# App initialization
app = FastAPI()

# Route configuration with pathlib
BASE_DIR = Path(__file__).parent
MODEL_PATH = (BASE_DIR / "../trained_models/local/best_m.pt").resolve()
CAPTURED_DIR = (BASE_DIR / "../captured_images").resolve()
CAPTURED_DIR.mkdir(parents=True, exist_ok=True)
CSV_FILE = Path(__file__).parent / "../medidas_contador.csv"

# Load Model
model = YOLO(MODEL_PATH)

# Django API Configuration
DJANGO_API_URL = "http://127.0.0.1:8000/api/public/reading/"
DEFAULT_METER_ID = "MTR001"  # ID del contador por defecto (cambiar según sea necesario)

# Image processing and Inference
def process_image_yolo(img_path:Path):
    processed_image = preprocessing.process_image(img_path)
    results = model(processed_image, conf=0.4, project=str(CAPTURED_DIR / "YOLO"),save=True)
    detected = []
    for r in results:
        boxes = r.boxes
        for box in boxes:
            cls = int(box.cls[0])
            conf = float(box.conf[0])
            x1, y1, x2, y2 = box.xyxy[0].tolist()

            print(f"--> Detectado: {cls} | Posicion_x: {x1} | Confianza: {conf:.2f} ")
            detected.append({"numero":cls, "x_pos":x1, "confianza":conf})
    
    if not detected:
        return "Error: No se detectaron numeros"
    
    detected_ordered = sorted(detected, key=lambda k: k["x_pos"])
    final_reading = "".join(str(d["numero"]) for d in detected_ordered)
    return final_reading

# Update CSV
def save_reading(reading):
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    df = pd.DataFrame([["1", timestamp, reading, len(reading)]], columns=["ID","Fecha", "Lectura", "# Digitos"])
    header = not CSV_FILE.exists()
    df.to_csv(CSV_FILE, mode='a', header=header, index=False)

# Send reading to Django API
def send_to_django(reading, meter_id=DEFAULT_METER_ID):
    """
    Envía la lectura al sistema Django (water_monitoring) para almacenarla en PostgreSQL.
    
    Args:
        reading: Lectura del contador (string con dígitos)
        meter_id: ID del contador en el sistema Django
    
    Returns:
        dict: Respuesta del servidor Django o error
    """
    try:
        # Convertir lectura a float (asumiendo que es un valor acumulado)
        accumulated_value = float(reading)
        
        # Preparar payload para el API de Django
        payload = {
            "meter_id": meter_id,
            "accumulated_value": accumulated_value,
            "timestamp": datetime.now().isoformat()
        }
        
        # Enviar POST request al endpoint público de Django
        response = requests.post(DJANGO_API_URL, json=payload, timeout=5)
        
        if response.status_code == 201:
            print(f"✅ Lectura enviada exitosamente a Django: {response.json()}")
            return {"success": True, "data": response.json()}
        else:
            print(f"⚠️ Error al enviar a Django ({response.status_code}): {response.text}")
            return {"success": False, "error": response.text, "status_code": response.status_code}
            
    except requests.exceptions.ConnectionError:
        print(f"❌ No se pudo conectar con Django API en {DJANGO_API_URL}")
        return {"success": False, "error": "Connection error - Django server not available"}
    except ValueError as e:
        print(f"❌ Error de formato en lectura '{reading}': {e}")
        return {"success": False, "error": f"Invalid reading format: {reading}"}
    except Exception as e:
        print(f"❌ Error inesperado al enviar a Django: {e}")
        return {"success": False, "error": str(e)}

#ESP32 workflow
@app.post("/upload")
async def upload_from_esp32(request: Request):
    data = await request.body()

    if not data or len(data)==0:
        return {"error":"No data received"}
    print(f"Recibidos {len(data)} bytes")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = CAPTURED_DIR / f"img_{timestamp}_esp32.jpg"
    filename.write_bytes(data)
    print(f"[ESP32] Imagen guardada en: {filename.name}")

    # Model inference
    try:
        reading = process_image_yolo(filename)
        print(f"Lectura detectada: {reading}")
        
        # Guardar en CSV local (respaldo)
        save_reading(reading)
        
        # Enviar a Django solo si la lectura es válida (no contiene "Error")
        if "Error" not in reading and reading.isdigit():
            django_response = send_to_django(reading, meter_id=DEFAULT_METER_ID)
        else:
            django_response = {"success": False, "error": "Invalid reading - not sent to database"}
            print(f"⚠️ Lectura inválida, no se envió a Django: {reading}")
        
        return {
            "status": "ok", 
            "lectura": reading, 
            "origen": "ESP32",
            "django_sync": django_response
        }
    except Exception as e:
        print(f"Error: {e}")
        return {"status": "error", "lectura": "Error", "origen": "ESP32", "error": str(e)}

@app.post("/test-web")
async def upload_from_web(file:UploadFile=File(...)):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = CAPTURED_DIR / f"img_{timestamp}_web.jpg"

    with open(filename ,"wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    print(f"[WEB] Imagen guardada en: {filename.name}")

    # Model inference
    try:
        reading = process_image_yolo(filename)
        print(f"Lectura detectada: {reading}")
        
        # Guardar en CSV local (respaldo)
        save_reading(reading)
        
        # Enviar a Django solo si la lectura es válida (no contiene "Error")
        if "Error" not in reading and reading.isdigit():
            django_response = send_to_django(reading, meter_id=DEFAULT_METER_ID)
        else:
            django_response = {"success": False, "error": "Invalid reading - not sent to database"}
            print(f"⚠️ Lectura inválida, no se envió a Django: {reading}")
        
        return {
            "status": "ok", 
            "lectura": reading, 
            "origen": "WEB TEST",
            "django_sync": django_response
        }
    except Exception as e:
        print(f"Error: {e}")
        return {"status": "error", "lectura": "Error", "origen": "WEB TEST", "error": str(e)}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)