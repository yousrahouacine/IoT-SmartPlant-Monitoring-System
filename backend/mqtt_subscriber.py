print("SCRIPT STARTED")

import paho.mqtt.client as mqtt
import json
import requests
import threading
import time
import csv
import os
from datetime import datetime

# ===== WEATHER CONFIG =====
WEATHER_API_KEY = "Your API Key"   
CITY = "Cagliari"

# ===== MQTT CONFIG =====
BROKER = "broker.hivemq.com"
PORT = 1883
TOPIC = "smartplant/yousra/data"
CMD_TOPIC = "smartplant/yousra/cmd"
USER_TOPIC = "smartplant/yousra/user"

# ===== TELEGRAM CONFIG =====
TOKEN = "***"   
CHAT_ID = "***"   

# ===== FILES =====
CSV_FILE = "history.csv"
USER_FILE = "users.csv"

# ===== GLOBAL STATES =====
last_status = None
last_data = None
last_alert_time = 0
last_save_time = 0

ALERT_INTERVAL = 120
SAVE_INTERVAL = 120

MAX_ROWS = 15
REMOVE_ROWS = 5


# ===== WEATHER FUNCTION =====
def will_rain_soon():
    try:
        url = f"https://api.openweathermap.org/data/2.5/forecast?q={CITY}&appid={WEATHER_API_KEY}&units=metric"
        response = requests.get(url)
        data = response.json()

        for forecast in data["list"][:2]:
            weather = forecast["weather"][0]["main"]
            if weather.lower() == "rain":
                return True
        return False
    except:
        return False


# ===== TELEGRAM SEND =====
def send_telegram(msg):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    data = {"chat_id": CHAT_ID, "text": msg}
    requests.post(url, data=data)


# ===== REGISTER USER =====
def register_user(uid):
    exists = False

    if os.path.exists(USER_FILE):
        with open(USER_FILE, "r", encoding="utf-8") as f:
            rows = list(csv.reader(f))
            for r in rows[1:]:
                if r[0] == uid:
                    exists = True
                    break

    if not exists:
        with open(USER_FILE, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            if f.tell() == 0:
                writer.writerow(["uid", "timestamp", "device"])
            writer.writerow([
                uid,
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "SmartPlant_1"
            ])

        send_telegram(f"!🕵️‍♂️ New user registered\nUID: {uid}")


# ===== LED COMMAND =====
def send_led_command(cmd):
    client.publish(CMD_TOPIC, cmd)


# ===== SAVE HISTORY =====
def save_to_history(data):
    rows = []

    if os.path.exists(CSV_FILE):
        with open(CSV_FILE, "r", encoding="utf-8") as f:
            rows = list(csv.reader(f))

    content = rows[1:] if rows else []

    if len(content) >= MAX_ROWS:
        content = content[REMOVE_ROWS:]

    content.append([
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        data["temperature"],
        data["humidity"],
        data["light"],
        data["soil"],
        data["status"],
        data["action"]
    ])

    with open(CSV_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "timestamp",
            "temperature",
            "humidity",
            "light",
            "soil",
            "status",
            "action"
        ])
        writer.writerows(content)


# ===== TELEGRAM COMMAND LISTENER =====
def check_telegram_commands():
    global last_data
    offset = None

    while True:
        url = f"https://api.telegram.org/bot{TOKEN}/getUpdates"
        if offset:
            url += f"?offset={offset}"

        r = requests.get(url).json()

        if r.get("ok"):
            for update in r["result"]:
                offset = update["update_id"] + 1

                if "message" in update and "text" in update["message"]:
                    text = update["message"]["text"]

                    if text == "/status" and last_data:
                        msg = f"""🌱 Smart Plant Status
Status: {last_data['status']}
Action: {last_data['action']}
Temp: {last_data['temperature']} °C
Humidity: {last_data['humidity']} %
Soil: {last_data['soil']} %
"""
                        send_telegram(msg)

                    elif text == "/led_on":
                        send_led_command("ON")
                        send_telegram(" LED ON")

                    elif text == "/led_off":
                        send_led_command("OFF")
                        send_telegram(" LED OFF")

        time.sleep(2)


# ===== MQTT CALLBACKS =====
def on_connect(client, userdata, flags, rc):
    print("Connected with result code", rc)
    client.subscribe(TOPIC)
    client.subscribe(USER_TOPIC)


def on_message(client, userdata, msg):
    global last_data, last_status, last_alert_time, last_save_time

    # RFID SMART CHECK 
    if msg.topic == USER_TOPIC:
        uid = msg.payload.decode()
        print("USER SCANNED:", uid)
        register_user(uid)

        if last_data:
            if last_data["status"] == "OK":
                send_telegram(" Plant checked\n🌿 Everything is fine.")
            else:
                send_telegram(f""" Plant checked
 Status: {last_data['status']}
Action: {last_data['action']}
""")
        return

    try:
        payload = msg.payload.decode()
        payload = payload.replace("nan", "null")
        data = json.loads(payload)
    except json.JSONDecodeError:
        print(" Message JSON invalide ignoré")
        return

    last_data = data
    current_time = time.time()

    if current_time - last_save_time >= SAVE_INTERVAL:
        save_to_history(data)
        last_save_time = current_time

    print("---- Smart Plant ----")
    print("Temp:", data["temperature"], "°C")
    print("Humidity:", data["humidity"], "%")
    print("Light:", data["light"])
    print("Soil:", data["soil"], "%")
    print("Status:", data["status"])
    print("Action:", data["action"])
    print("---------------------\n")

    # ===== WEATHER AWARE DECISION =====
    rain_expected = will_rain_soon()

    if (
        data["status"] == "Needs water"
        and rain_expected
        and (current_time - last_alert_time) > ALERT_INTERVAL
    ):
        last_alert_time = current_time
        send_telegram("🌧 Rain expected soon — watering postponed.")

    elif (
        data["status"] != "OK"
        and (current_time - last_alert_time) > ALERT_INTERVAL
    ):
        last_alert_time = current_time

        message = f"""🌱 Smart Plant Alert
Status: {data['status']}
Action: {data['action']}
Temp: {data['temperature']} °C
Humidity: {data['humidity']} %
Soil: {data['soil']} %
"""
        send_telegram(message)


# ===== START THREAD =====
threading.Thread(target=check_telegram_commands, daemon=True).start()

# ===== MQTT START =====
client = mqtt.Client(protocol=mqtt.MQTTv311)
client.on_connect = on_connect
client.on_message = on_message
client.connect(BROKER, PORT, 60)

print("ENTERING MQTT LOOP")
client.loop_forever()
