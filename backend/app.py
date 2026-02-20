from flask import Flask, render_template, jsonify
import csv
import os

app = Flask(__name__)

def read_history():
    data = []
    base_dir = os.path.dirname(os.path.dirname(__file__))
    file_path = os.path.join(base_dir, "history.csv")

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                data.append(row)
    except Exception as e:
        print("Error reading CSV:", e)

    return data[::-1]


@app.route("/")
def dashboard():
    history = read_history()
    latest = history[0] if history else None
    return render_template("dashboard.html", latest=latest)


@app.route("/history")
def history_page():
    history = read_history()
    return render_template("history.html", history=history)


@app.route("/analytics")
@app.route("/analytics")
def analytics():
    history = read_history()

    if not history:
        return render_template(
            "analytics.html",
            history=history,
            avg_temp=0,
            avg_soil=0,
            avg_light=0,
            alert_percentage=0
        )

    temps = [float(row["temperature"]) for row in history if row["temperature"]]
    soils = [float(row["soil"]) for row in history if row["soil"]]
    lights = [float(row["light"]) for row in history if row["light"]]

    avg_temp = round(sum(temps) / len(temps), 2) if temps else 0
    avg_soil = round(sum(soils) / len(soils), 2) if soils else 0
    avg_light = round(sum(lights) / len(lights), 2) if lights else 0

    alert_count = len([row for row in history if row["status"] != "OK"])
    alert_percentage = round((alert_count / len(history)) * 100, 2)

    return render_template(
        "analytics.html",
        history=history,
        avg_temp=avg_temp,
        avg_soil=avg_soil,
        avg_light=avg_light,
        alert_percentage=alert_percentage
    )



# AJAX API!
@app.route("/api/latest")
def api_latest():
    history = read_history()
    latest = history[0] if history else None
    return jsonify(latest)


if __name__ == "__main__":
    app.run(debug=True)
