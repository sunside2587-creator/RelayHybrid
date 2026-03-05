from flask import Flask, render_template, request, jsonify
import paho.mqtt.client as mqtt
import json
from datetime import datetime

app = Flask(__name__)

# Inisialisasi data awal agar template tidak kosong saat pertama kali dibuka
data_sensor = {"suhu1": 0, "hum1": 0, "suhu2": 0, "hum2": 0}
history = {"labels": [], "suhu1": [], "suhu2": []}

# Konfigurasi Auto Relay
auto_config = {
    "auto_enabled": False,
    "temp_threshold": 30.0,
    "time_start": "08:00",
    "time_end": "17:00",
    "relay_auto_1": False,
    "relay_auto_2": True,
    "relay_auto_3": True 
}

last_auto_state = False

# ================= MQTT CALLBACK =================
def on_connect(client, userdata, flags, rc, properties=None):
    print(f"MQTT Connected with code: {rc}")
    client.subscribe("iot/sandi/dht")

def on_message(client, userdata, msg):
    global data_sensor, history
    try:
        payload = json.loads(msg.payload.decode())
        data_sensor = payload
        
        # Update Riwayat Grafik
        now = datetime.now()
        now_str = now.strftime("%H:%M:%S")
        history["labels"].append(now_str)
        history["suhu1"].append(payload.get("suhu1", 0))
        history["suhu2"].append(payload.get("suhu2", 0))
        
        if len(history["labels"]) > 20:
            for key in history: history[key].pop(0)

        # ====== AUTO CONTROL LOGIC ======
        global last_auto_state
        if auto_config["auto_enabled"]:
            current_time = now.strftime("%H:%M")
            suhu = float(payload.get("suhu1", 0))
            
            time_match = auto_config["time_start"] <= current_time <= auto_config["time_end"]
            temp_match = suhu >= auto_config["temp_threshold"]
            
            should_be_on = time_match and temp_match
            
            if should_be_on != last_auto_state:
                state_str = "ON" if should_be_on else "OFF"
                if auto_config["relay_auto_1"]: client.publish("hybrid/cmd/manual", f"{state_str}1")
                if auto_config["relay_auto_2"]: client.publish("hybrid/cmd/manual", f"{state_str}2")
                if auto_config["relay_auto_3"]: client.publish("hybrid/cmd/manual", f"{state_str}3")
                last_auto_state = should_be_on

    except Exception as e:
        print(f"Error: {e}")

# ================= MQTT SETUP (VERSI 2.0) =================
client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
client.on_connect = on_connect
client.on_message = on_message

client.connect("broker.emqx.io", 1883, 60)
client.loop_start()

# ================= ROUTES =================
@app.route('/')
def index():
    # PERBAIKAN: Mengirimkan data_sensor ke template index.html
    return render_template('index.html', data=data_sensor)

@app.route('/api/data')
def get_data():
    return jsonify({"current": data_sensor, "history": history})

@app.route('/api/auto_config', methods=['GET', 'POST'])
def handle_auto_config():
    global auto_config
    if request.method == 'POST':
        data = request.json
        auto_config.update({
            "auto_enabled": data.get("auto_enabled", auto_config["auto_enabled"]),
            "temp_threshold": float(data.get("temp_threshold", auto_config["temp_threshold"])),
            "time_start": data.get("time_start", auto_config["time_start"]),
            "time_end": data.get("time_end", auto_config["time_end"]),
            "relay_auto_1": data.get("relay_auto_1", auto_config["relay_auto_1"]),
            "relay_auto_2": data.get("relay_auto_2", auto_config["relay_auto_2"]),
            "relay_auto_3": data.get("relay_auto_3", auto_config["relay_auto_3"])
        })
        return jsonify({"status": "success", "config": auto_config})
    return jsonify(auto_config)

@app.route('/relay', methods=['POST'])
def relay():
    state = request.form.get('state')
    client.publish("hybrid/cmd/manual", state)
    return jsonify({"status": "sent", "cmd": state})

if __name__ == '__main__':
    # Pastikan port sesuai dengan yang Anda akses di browser
    app.run(debug=True, port=5500)