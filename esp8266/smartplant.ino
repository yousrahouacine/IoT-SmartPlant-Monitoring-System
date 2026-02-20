#include <ESP8266WiFi.h>
#include <PubSubClient.h>
#include <DHT.h>
#include <SPI.h>
#include <MFRC522.h>

/* ===== WIFI ===== */
const char* ssid = "Your WiFi";    
const char* password = "WiFi password";    

/* ===== MQTT ===== */
const char* mqtt_server = "broker.hivemq.com";
const int mqtt_port = 1883;
const char* DATA_TOPIC = "smartplant/yousra/data";
const char* CMD_TOPIC = "smartplant/yousra/cmd";
const char* USER_TOPIC = "smartplant/yousra/user";

/* ===== RFID ===== */
#define SS_PIN D8
#define RST_PIN D3
MFRC522 mfrc522(SS_PIN, RST_PIN);

/* ===== PINS ===== */
#define LED_PIN D2
#define DHTPIN D4
#define DHTTYPE DHT11
#define LDR_PIN D1

DHT dht(DHTPIN, DHTTYPE);

/* ===== THRESHOLDS ===== */
#define SOIL_THRESHOLD 30

/* ===== FR8 ===== */
#define USER_CMD_DURATION 20000
bool userOverride = false;
bool userLedState = LOW;
unsigned long userCmdTime = 0;

/* ===== TIMING ===== */
unsigned long lastPublish = 0;
const unsigned long PUBLISH_INTERVAL = 3000;

/* ===== MQTT ===== */
WiFiClient espClient;
PubSubClient client(espClient);

/* ===== WIFI ===== */
void setup_wifi() {
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(300);
  }
}

/* ===== MQTT CALLBACK ===== */
void callback(char* topic, byte* payload, unsigned int length) {

  String message = "";
  for (unsigned int i = 0; i < length; i++) {
    message += (char)payload[i];
  }

  if (String(topic) == CMD_TOPIC) {
    userOverride = true;
    userCmdTime = millis();

    if (message == "ON") {
     for (int i = 0; i < 10; i++) {
      digitalWrite(LED_PIN, HIGH);
      delay(300);
      digitalWrite(LED_PIN, LOW);
      delay(300);
     }
     userOverride = false; // Not blocked in manuel mode!
  }

    else if (message == "OFF") {
      userLedState = LOW;
    }
  }
}

/* ===== RECONNECT ===== */
void reconnect() {
  while (!client.connected()) {
    String cid = "SmartPlant_" + String(ESP.getChipId());
    if (client.connect(cid.c_str())) {
      client.subscribe(CMD_TOPIC);
    } else {
      delay(1000);
    }
  }
}

void setup() {
  Serial.begin(9600);
  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, LOW);

  pinMode(LDR_PIN, INPUT);

  dht.begin();
  setup_wifi();

  SPI.begin();
  mfrc522.PCD_Init();

  client.setServer(mqtt_server, mqtt_port);
  client.setCallback(callback);
}

void loop() {

  if (!client.connected()) reconnect();
  client.loop();

  if (userOverride && millis() - userCmdTime > USER_CMD_DURATION) {
    userOverride = false;
  }

  if (mfrc522.PICC_IsNewCardPresent() && mfrc522.PICC_ReadCardSerial()) {
    String uid = "";
    for (byte i = 0; i < mfrc522.uid.size; i++) {
      uid += String(mfrc522.uid.uidByte[i], HEX);
    }
    client.publish(USER_TOPIC, uid.c_str());
    mfrc522.PICC_HaltA();
    delay(1000);
  }

  if (millis() - lastPublish < PUBLISH_INTERVAL) return;
  lastPublish = millis();

  float h = dht.readHumidity();
  float t = dht.readTemperature();
  int light = digitalRead(LDR_PIN);

  //Soil calibration
  int rawSoil = analogRead(A0);

  //Realistic range
  int soil = map(rawSoil, 1023, 550, 0, 100);
  soil = constrain(soil, 0, 100);

  Serial.println(soil);

  

  String status = "OK";
  String action = "None";
  bool alert = false;

  bool needWater = soil < SOIL_THRESHOLD;
  bool needLight = (light == LOW);

  if (needWater && needLight) {
    status = "Needs water and light";
    action = "Water plant and move to sunlight";
    alert = true;
  }
  else if (needWater) {
    status = "Needs water";
    action = "Water plant";
    alert = true;
  }

  else if (needLight) {
    status = "Needs light";
    action = "Move to sunlight";
    alert = true;
  }

  bool autoLed = alert ? HIGH : LOW;

  digitalWrite(LED_PIN, userOverride ? userLedState : autoLed);

  String payload = "{";
  payload += "\"temperature\":" + String(t) + ",";
  payload += "\"humidity\":" + String(h) + ",";
  payload += "\"light\":" + String(light) + ",";
  payload += "\"soil\":" + String(soil) + ",";
  payload += "\"status\":\"" + status + "\",";
  payload += "\"action\":\"" + action + "\"";
  payload += "}";

  client.publish(DATA_TOPIC, payload.c_str());
}
