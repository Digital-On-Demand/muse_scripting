import tkinter as tk
from tkinter import messagebox
import os
import time
import requests

# static variables
IS_BETA = True
LASER_FOLDER_PATH = "Z:/Shared/Muse"
DEVICE_ACCESS_CODE = "Tribute,Snowy,22"
SLEEP_TIME = 4 #time to sleep before starting job

if IS_BETA:
    server = "https://beta.fslaser.com"
    pass_code = "Whacking:Wrinkle:52"
else:
    server = "https://re4.fslaser.com"
    pass_code = "Protract;Aneurism;50"

def run_lap_job(server, pass_code, device_access_code, lap_file_path):
    try:
        url = server + "/api/jobs/api-run-lap-job"
        data = {"pass_code": pass_code, "device_access_code": device_access_code}
        with open(lap_file_path, "rb") as f:
            files = {"lap_file": f}
            response = requests.post(url, data=data, files=files)

        if response.status_code == 200:
            result = response.json()
            status_label.config(text=f"Job started on Muse.\nResponse: {result}")
            return True
        else:
            error_text = response.json()
            status_label.config(text=f"Error {response.status_code}: {error_text}")
            return False
    except Exception as e:
        status_label.config(text=f"Exception: {e}")
        return False

def start_job(event=None):
    barcode = barcode_entry.get().strip()
    if not barcode:
        status_label.config(text="Enter a real barcode")
        return

    output_folder = os.path.join(LASER_FOLDER_PATH, "Output")
    lap_file_path = None

    for file_name in os.listdir(output_folder):
        if file_name.startswith(barcode):
            lap_file_path = os.path.join(output_folder, file_name)
            break

    if not lap_file_path:
        status_label.config(text=f"no file found for {barcode}")
        return

    for i in range(SLEEP_TIME, 0, -1):
        status_label.config(text=f"Starting job in {i} second(s)...")
        window.update()
        time.sleep(1)

    success = run_lap_job(server, pass_code, DEVICE_ACCESS_CODE, lap_file_path)

    if success:
        status_label.config(text=f"Job started for {barcode}")
    else:
        status_label.config(text=f"Failed to start job for {barcode}")

    barcode_entry.delete(0, tk.END)

# GUI setup
window = tk.Tk()
window.title("Muse LAP Job Runner")
window.geometry("400x200")

tk.Label(window, text="Enter Barcode:").pack(pady=10)
barcode_entry = tk.Entry(window, width=30)
barcode_entry.pack()
barcode_entry.bind("<Return>", start_job)

run_button = tk.Button(window, text="Run Job", command=start_job)
run_button.pack(pady=15)

status_label = tk.Label(window, text="")
status_label.pack()

window.mainloop()