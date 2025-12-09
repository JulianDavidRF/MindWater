#include <Arduino.h>
#include <WiFi.h>
#include "esp_camera.h"
#include <HTTPClient.h>

// ========================================
// 1. Configuracion basica
// ========================================
const char* ssid = "XXXXX";
const char* password = "XXXXX";
String serverName = "http://IPAdress:8000/upload";

// ========================================
// 2. Definicion de pines (Modelo AI-Thinker)
// ========================================
#define PWDN_GPIO_NUM     32
#define RESET_GPIO_NUM    -1
#define XCLK_GPIO_NUM      0
#define SIOD_GPIO_NUM     26
#define SIOC_GPIO_NUM     27
#define Y9_GPIO_NUM       35
#define Y8_GPIO_NUM       34
#define Y7_GPIO_NUM       39
#define Y6_GPIO_NUM       36
#define Y5_GPIO_NUM       21
#define Y4_GPIO_NUM       19
#define Y3_GPIO_NUM       18
#define Y2_GPIO_NUM        5
#define VSYNC_GPIO_NUM    25
#define HREF_GPIO_NUM     23
#define PCLK_GPIO_NUM     22

#define FLASH_NUM 4

void takeAndSendPhoto();

void setup() {
  Serial.begin(115200);
  Serial.println("\n---Iniciando Sensor OV2640---");
  pinMode(FLASH_NUM,OUTPUT);

  // ========================================
  // 3. Configuracion de Sensor OV2640
  // ========================================
  camera_config_t config;
  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer = LEDC_TIMER_0;
  config.pin_d0 = Y2_GPIO_NUM;
  config.pin_d1 = Y3_GPIO_NUM;
  config.pin_d2 = Y4_GPIO_NUM;
  config.pin_d3 = Y5_GPIO_NUM;
  config.pin_d4 = Y6_GPIO_NUM;
  config.pin_d5 = Y7_GPIO_NUM;
  config.pin_d6 = Y8_GPIO_NUM;
  config.pin_d7 = Y9_GPIO_NUM;
  config.pin_xclk = XCLK_GPIO_NUM;
  config.pin_pclk = PCLK_GPIO_NUM;
  config.pin_vsync = VSYNC_GPIO_NUM;
  config.pin_href = HREF_GPIO_NUM;
  config.pin_sccb_sda = SIOD_GPIO_NUM;
  config.pin_sccb_scl = SIOC_GPIO_NUM;
  config.pin_pwdn = PWDN_GPIO_NUM;
  config.pin_reset = RESET_GPIO_NUM;
  
  config.xclk_freq_hz = 20000000;
  config.pixel_format = PIXFORMAT_JPEG;

  if(psramFound()){
    Serial.println("Usando PSRAM");
    config.frame_size = FRAMESIZE_UXGA; 
    config.jpeg_quality = 10;
    config.fb_count = 1;
  } else {
    Serial.println("NO se está usando la PSRAM");
    config.frame_size = FRAMESIZE_SVGA;
    config.jpeg_quality = 12;
    config.fb_count = 1;
  }

  // Iniciar camara
  esp_err_t err = esp_camera_init(&config);
  if (err != ESP_OK) {
    Serial.printf("Error iniciando camara: 0x%x\n", err);
    delay(1000), ESP.restart();
    return;
  }

  // Balance de color
  sensor_t * s = esp_camera_sensor_get();
  if(s != NULL){
    s->set_whitebal(s,1);
    s->set_awb_gain(s,1);
    s->set_wb_mode(s,0);
  }

  // ========================================
  // 4. Conexion WIFI
  // ========================================
  WiFi.begin(ssid, password);
  WiFi.setSleep(false);

  Serial.print("Conectando WiFi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nWiFi Conectado!");
}

void loop() {
  takeAndSendPhoto();

  Serial.println("Enfriando 15s...");
  delay(3600000); //Se define el intervalo de una hora (configurable)
}

void takeAndSendPhoto(){
  if(WiFi.status() != WL_CONNECTED){
    WiFi.reconnect();
    delay(500);
  }
  delay(100);

  Serial.println("Calibrando luz...");
  camera_fb_t * fb = esp_camera_fb_get();
  esp_camera_fb_return(fb);
  delay(200);

  Serial.println("Capturando imágen...");
  fb = esp_camera_fb_get();

  if(!fb){
    Serial.println("Error en la captura");
    digitalWrite(PWDN_GPIO_NUM, HIGH);
    return;
  }

  Serial.printf("Enviando %u bytes...\n", fb->len);
  HTTPClient http;
  http.begin(serverName);
  http.addHeader("Content-Type", "image/jpeg");

  int httpResponseCode = http.POST(fb->buf, fb->len);

  if(httpResponseCode > 0){
    Serial.printf("Envío exitoso: %d\n", httpResponseCode);
  }else{
    Serial.printf("Envío fallido: %s\n", http.errorToString(httpResponseCode).c_str());
  }

  http.end();
  esp_camera_fb_return(fb);

  for(int i=0; i<3; i++){
    digitalWrite(FLASH_NUM,HIGH); delay(100);
    digitalWrite(FLASH_NUM,LOW); delay(100);
  }
}