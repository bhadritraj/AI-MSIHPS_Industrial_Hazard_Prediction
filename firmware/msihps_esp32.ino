/*
  AI-MSIHPS ESP32 Firmware
  ─────────────────────────
  Sensors: MQ2, MQ135, DHT22, MPU6050, Ultrasonic, 
           Vibration, Flame, Sound, RFID (MFRC522)
  Output:  MQTT → Flask Backend
           OLED Display
           Buzzer + LED indicators

  Libraries needed (install via Arduino Library Manager):
  - PubSubClient (MQTT)
  - ArduinoJson
  - DHT sensor library (Adafruit)
  - Adafruit_SSD1306 (OLED)
  - MPU6050_light
  - MFRC522 (RFID)
  - WiFi (built-in ESP32)
*/

#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <DHT.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <MPU6050_light.h>
#include <SPI.h>
#include <MFRC522.h>

// ─── Configuration ─────────────────────────────────────────────────────────────

const char* WIFI_SSID     = "YOUR_WIFI_SSID";       // ← Change this
const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";    // ← Change this
const char* MQTT_BROKER   = "192.168.1.100";         // ← Your server IP
const int   MQTT_PORT     = 1883;
const char* ZONE_ID       = "zone_01";               // ← Set for each device
const int   READING_INTERVAL_MS = 5000;              // 5 seconds

// MQTT Topics
String SENSOR_TOPIC  = "msihps/sensors/" + String(ZONE_ID);
String COMMAND_TOPIC = "msihps/commands/" + String(ZONE_ID);
String RFID_TOPIC    = "msihps/rfid/" + String(ZONE_ID);

// ─── Pin Definitions ────────────────────────────────────────────────────────────

// Gas Sensors (Analog)
#define MQ2_PIN         34      // ADC1 - Methane, LPG, Smoke
#define MQ135_PIN       35      // ADC1 - Toxic gas

// DHT22 Temperature + Humidity
#define DHT_PIN         4
#define DHT_TYPE        DHT22

// Ultrasonic (Liquid level)
#define TRIG_PIN        5
#define ECHO_PIN        18

// Digital sensors
#define FLAME_PIN       19      // Digital: HIGH = flame detected
#define VIBRATION_PIN   21      // Digital pulse sensor
#define SOUND_PIN       22      // Digital: HIGH = sound threshold exceeded

// Output devices
#define BUZZER_PIN      25
#define LED_RED_PIN     26
#define LED_GREEN_PIN   27
#define LED_YELLOW_PIN  14

// RFID (SPI)
#define RFID_SS_PIN     15
#define RFID_RST_PIN    2

// I2C (OLED + MPU6050 share same bus)
#define I2C_SDA         21
#define I2C_SCL         22

// ─── Object Initialization ──────────────────────────────────────────────────────

DHT dht(DHT_PIN, DHT_TYPE);
Adafruit_SSD1306 display(128, 64, &Wire, -1);
MPU6050 mpu(Wire);
MFRC522 rfid(RFID_SS_PIN, RFID_RST_PIN);
WiFiClient espClient;
PubSubClient mqttClient(espClient);

// ─── Global State ───────────────────────────────────────────────────────────────

float lastRiskScore    = 0.0;
String lastStatus      = "SAFE";
bool alarmActive       = false;
unsigned long lastRead = 0;
unsigned long vibCount = 0;
unsigned long lastVibCheck = 0;

// ─── Setup ──────────────────────────────────────────────────────────────────────

void setup() {
    Serial.begin(115200);
    Serial.println("[MSIHPS] Booting...");

    // Pin modes
    pinMode(FLAME_PIN,      INPUT);
    pinMode(VIBRATION_PIN,  INPUT);
    pinMode(SOUND_PIN,      INPUT);
    pinMode(BUZZER_PIN,     OUTPUT);
    pinMode(LED_RED_PIN,    OUTPUT);
    pinMode(LED_GREEN_PIN,  OUTPUT);
    pinMode(LED_YELLOW_PIN, OUTPUT);

    // Attach vibration interrupt
    attachInterrupt(digitalPinToInterrupt(VIBRATION_PIN), countVibration, RISING);

    // DHT22
    dht.begin();

    // I2C devices
    Wire.begin(I2C_SDA, I2C_SCL);

    // OLED
    if (!display.begin(SSD1306_SWITCHCAPVCC, 0x3C)) {
        Serial.println("[OLED] Init failed");
    } else {
        showBootScreen();
    }

    // MPU6050
    byte status = mpu.begin();
    if (status != 0) {
        Serial.println("[MPU6050] Connection failed!");
    } else {
        mpu.calcOffsets();   // Auto-calibrate (keep device still for 3 seconds)
        Serial.println("[MPU6050] Calibrated");
    }

    // RFID
    SPI.begin();
    rfid.PCD_Init();
    Serial.println("[RFID] Ready");

    // WiFi
    connectWiFi();

    // MQTT
    mqttClient.setServer(MQTT_BROKER, MQTT_PORT);
    mqttClient.setCallback(onMQTTMessage);
    connectMQTT();

    // Startup blink
    blinkLED(LED_GREEN_PIN, 3);
    Serial.println("[MSIHPS] Ready!");
}

// ─── Main Loop ──────────────────────────────────────────────────────────────────

void loop() {
    // Maintain connections
    if (!mqttClient.connected()) connectMQTT();
    mqttClient.loop();

    unsigned long now = millis();

    // Read and publish sensors every READING_INTERVAL_MS
    if (now - lastRead >= READING_INTERVAL_MS) {
        lastRead = now;
        readAndPublishSensors();
    }

    // Check for RFID scan
    checkRFID();

    // Check vibration frequency (count pulses per second)
    if (now - lastVibCheck >= 1000) {
        lastVibCheck = now;
        // vibCount is updated by interrupt
        vibCount = 0;  // Reset for next second
    }

    delay(10);
}

// ─── Sensor Reading & Publishing ────────────────────────────────────────────────

void readAndPublishSensors() {
    // Gas sensors (MQ2, MQ135)
    int mq2_raw   = analogRead(MQ2_PIN);
    int mq135_raw = analogRead(MQ135_PIN);
    float mq2_ppm   = convertToPPM(mq2_raw, 9.83, -0.699);    // MQ2 calibration curve
    float mq135_ppm = convertToPPM(mq135_raw, 116.6, -2.769); // MQ135 calibration curve

    // Temperature + Humidity
    float temperature = dht.readTemperature();
    float humidity    = dht.readHumidity();
    if (isnan(temperature)) temperature = 25.0;
    if (isnan(humidity))    humidity = 50.0;

    // Ultrasonic liquid level
    float liquid_level = readUltrasonic();

    // MPU6050 tilt
    mpu.update();
    float tilt = sqrt(
        mpu.getAngleX() * mpu.getAngleX() +
        mpu.getAngleY() * mpu.getAngleY()
    );  // Combined tilt angle

    // Boolean sensors
    bool flame    = digitalRead(FLAME_PIN) == LOW;   // Active LOW
    bool sound    = digitalRead(SOUND_PIN) == HIGH;

    // Vibration (from interrupt counter)
    float vibration = (float)vibCount;   // Hz

    // Build JSON payload
    StaticJsonDocument<512> doc;
    doc["zone_id"]      = ZONE_ID;
    doc["mq2"]          = round(mq2_ppm * 10) / 10.0;
    doc["mq135"]        = round(mq135_ppm * 10) / 10.0;
    doc["temperature"]  = round(temperature * 10) / 10.0;
    doc["humidity"]     = round(humidity * 10) / 10.0;
    doc["vibration"]    = round(vibration * 10) / 10.0;
    doc["tilt"]         = round(tilt * 10) / 10.0;
    doc["liquid_level"] = round(liquid_level * 10) / 10.0;
    doc["flame"]        = flame;
    doc["sound"]        = sound ? 90.0 : 55.0;    // Approximate dB
    doc["timestamp"]    = millis();

    char payload[512];
    serializeJson(doc, payload);

    // Publish to MQTT
    bool published = mqttClient.publish(SENSOR_TOPIC.c_str(), payload);
    if (!published) {
        Serial.println("[MQTT] Publish failed! Retrying connection...");
        connectMQTT();
    }

    // Update OLED
    updateDisplay(mq2_ppm, mq135_ppm, temperature, humidity, lastRiskScore, lastStatus);

    // Debug print
    Serial.printf("[Sensors] MQ2:%.1f MQ135:%.1f T:%.1f H:%.1f Tilt:%.1f Flame:%d Risk:%.0f\n",
        mq2_ppm, mq135_ppm, temperature, humidity, tilt, flame, lastRiskScore);
}

// ─── RFID Worker Access ──────────────────────────────────────────────────────────

void checkRFID() {
    if (!rfid.PICC_IsNewCardPresent() || !rfid.PICC_ReadCardSerial()) {
        return;
    }

    // Read UID
    String uid = "";
    for (byte i = 0; i < rfid.uid.size; i++) {
        uid += String(rfid.uid.uidByte[i] < 0x10 ? "0" : "");
        uid += String(rfid.uid.uidByte[i], HEX);
    }
    uid.toUpperCase();
    Serial.println("[RFID] Card detected: " + uid);

    // Publish RFID event to backend
    StaticJsonDocument<256> doc;
    doc["rfid_uid"] = uid;
    doc["zone_id"]  = ZONE_ID;
    doc["action"]   = "entry";

    char payload[256];
    serializeJson(doc, payload);
    mqttClient.publish(("msihps/rfid/" + String(ZONE_ID)).c_str(), payload);

    // Wait for response (handled via COMMAND_TOPIC callback)
    delay(500);
    rfid.PICC_HaltA();
    rfid.PCD_StopCrypto1();
}

// ─── MQTT Command Handler ────────────────────────────────────────────────────────

void onMQTTMessage(char* topic, byte* payload, unsigned int length) {
    String msg = "";
    for (int i = 0; i < length; i++) msg += (char)payload[i];

    StaticJsonDocument<256> doc;
    DeserializationError err = deserializeJson(doc, msg);
    if (err) return;

    String command = doc["command"].as<String>();
    bool buzzerOn  = doc["buzzer"].as<bool>();
    String led     = doc["led"].as<String>();

    Serial.println("[CMD] " + command + " | Buzzer:" + buzzerOn + " | LED:" + led);

    // Update last status from server
    lastRiskScore = doc["risk_score"].as<float>();
    lastStatus    = doc["status"].as<String>();

    // Control outputs
    if (buzzerOn) {
        activateAlarm();
    } else {
        deactivateAlarm();
    }

    if (led == "RED") {
        setLED("RED");
    } else if (led == "YELLOW") {
        setLED("YELLOW");
    } else {
        setLED("GREEN");
    }

    // If RFID access response
    if (command == "ACCESS_GRANTED") {
        blinkLED(LED_GREEN_PIN, 2);
        showAccessScreen("ACCESS GRANTED", doc["worker"].as<String>(), true);
    } else if (command == "ACCESS_DENIED") {
        blinkLED(LED_RED_PIN, 3);
        showAccessScreen("ACCESS DENIED", doc["reason"].as<String>(), false);
    } else if (command == "EVACUATE") {
        activateAlarm();
        showEvacuationScreen();
    }
}

// ─── Sensor Helpers ──────────────────────────────────────────────────────────────

float convertToPPM(int raw_adc, float a, float b) {
    // MQ sensor: PPM = a * (Vcc * (1023-raw) / raw * R_load)^b
    // Simplified linear approximation for embedded use
    float voltage = raw_adc * (3.3 / 4095.0);   // ESP32 ADC is 12-bit
    if (voltage < 0.1) return 0;
    float ratio = voltage / 3.3;
    return a * pow(ratio, b);
}

float readUltrasonic() {
    digitalWrite(TRIG_PIN, LOW);
    delayMicroseconds(2);
    digitalWrite(TRIG_PIN, HIGH);
    delayMicroseconds(10);
    digitalWrite(TRIG_PIN, LOW);
    long duration = pulseIn(ECHO_PIN, HIGH, 30000);
    float distance = duration * 0.034 / 2.0;    // cm
    return (distance > 0 && distance < 400) ? distance : 0;
}

void IRAM_ATTR countVibration() {
    vibCount++;
}

// ─── Display Functions ───────────────────────────────────────────────────────────

void showBootScreen() {
    display.clearDisplay();
    display.setTextSize(1);
    display.setTextColor(SSD1306_WHITE);
    display.setCursor(10, 10);
    display.println("AI-MSIHPS v1.0");
    display.setCursor(10, 25);
    display.println("Industrial Safety");
    display.setCursor(10, 40);
    display.println("Initializing...");
    display.display();
    delay(2000);
}

void updateDisplay(float mq2, float mq135, float temp, float hum, float risk, String status) {
    display.clearDisplay();
    display.setTextSize(1);
    display.setTextColor(SSD1306_WHITE);

    // Header
    display.setCursor(0, 0);
    display.print("ZONE: ");
    display.print(ZONE_ID);

    // Status bar
    display.setCursor(70, 0);
    display.print("| " + status);

    // Separator line
    display.drawLine(0, 10, 127, 10, SSD1306_WHITE);

    // Sensor values
    display.setCursor(0, 13);
    display.printf("MQ2:%5.0f ppm", mq2);
    display.setCursor(0, 22);
    display.printf("MQ135:%4.0f ppm", mq135);
    display.setCursor(0, 31);
    display.printf("Temp:%4.1fC Hum:%2.0f%%", temp, hum);

    // Risk score bar
    display.setCursor(0, 42);
    display.print("RISK: ");
    display.printf("%.0f/100", risk);

    int barWidth = (int)(risk * 100 / 100);   // Scale to 100 pixels
    display.drawRect(0, 53, 100, 8, SSD1306_WHITE);
    display.fillRect(2, 55, barWidth - 4, 4, SSD1306_WHITE);

    display.display();
}

void showAccessScreen(String title, String info, bool granted) {
    display.clearDisplay();
    display.setTextSize(2);
    display.setCursor(5, 5);
    display.println(granted ? "GRANTED" : "DENIED");
    display.setTextSize(1);
    display.setCursor(0, 35);
    display.println(info.substring(0, 21));
    display.display();
    delay(3000);
}

void showEvacuationScreen() {
    for (int i = 0; i < 5; i++) {
        display.clearDisplay();
        display.setTextSize(2);
        display.setCursor(5, 20);
        display.println("EVACUATE!");
        display.display();
        delay(500);
        display.clearDisplay();
        display.display();
        delay(300);
    }
}

// ─── LED & Buzzer Controls ───────────────────────────────────────────────────────

void setLED(String color) {
    digitalWrite(LED_RED_PIN,    LOW);
    digitalWrite(LED_GREEN_PIN,  LOW);
    digitalWrite(LED_YELLOW_PIN, LOW);

    if (color == "RED")    digitalWrite(LED_RED_PIN,    HIGH);
    if (color == "GREEN")  digitalWrite(LED_GREEN_PIN,  HIGH);
    if (color == "YELLOW") digitalWrite(LED_YELLOW_PIN, HIGH);
}

void blinkLED(int pin, int times) {
    for (int i = 0; i < times; i++) {
        digitalWrite(pin, HIGH); delay(200);
        digitalWrite(pin, LOW);  delay(200);
    }
}

void activateAlarm() {
    if (!alarmActive) {
        alarmActive = true;
        setLED("RED");
        tone(BUZZER_PIN, 2000);   // 2kHz tone
    }
}

void deactivateAlarm() {
    if (alarmActive) {
        alarmActive = false;
        setLED("GREEN");
        noTone(BUZZER_PIN);
    }
}

// ─── WiFi & MQTT Connection ──────────────────────────────────────────────────────

void connectWiFi() {
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
    Serial.print("[WiFi] Connecting");
    int attempts = 0;
    while (WiFi.status() != WL_CONNECTED && attempts < 30) {
        delay(500);
        Serial.print(".");
        attempts++;
    }
    if (WiFi.status() == WL_CONNECTED) {
        Serial.println("\n[WiFi] Connected: " + WiFi.localIP().toString());
    } else {
        Serial.println("\n[WiFi] FAILED — check credentials");
    }
}

void connectMQTT() {
    int attempts = 0;
    while (!mqttClient.connected() && attempts < 5) {
        Serial.print("[MQTT] Connecting...");
        String clientId = "MSIHPS_" + String(ZONE_ID) + "_" + String(random(9999));

        if (mqttClient.connect(clientId.c_str())) {
            Serial.println("Connected!");
            mqttClient.subscribe(COMMAND_TOPIC.c_str());
            Serial.println("[MQTT] Subscribed to: " + COMMAND_TOPIC);
        } else {
            Serial.printf("[MQTT] Failed (rc=%d) — retrying...\n", mqttClient.state());
            delay(3000);
            attempts++;
        }
    }
}
