import tkinter as tk
from tkinter import messagebox
import os
import time
from datetime import datetime
import requests
from PIL import Image, ImageTk
import csv
from lib import parse_filename

# static variables
IS_BETA = False
LASER_FOLDER_PATH = "Y:/Shared/Muse"
device_id = "2CCF67398804" #obtained from device screen
SLEEP_TIME = 4 #time to sleep before starting job

if IS_BETA:
    server = "https://beta.fslaser.com"
    pass_code = "Decoy!Retiree!25" #obtained from account info on website
else:
    server = "https://re4.fslaser.com"
    pass_code = "Ignore;Crablike;37"

def run_lap_job(server, pass_code, device_id, lap_file_path):
    try:
        url = server + "/api/jobs/api-run-lap-job"
        data = {"pass_code": pass_code, "device_id": device_id, "soft_limit_check": True}
        with open(lap_file_path, "rb") as f:
            files = {"lap_file": f}
            response = requests.post(url, data=data, files=files, timeout=30)

        if response.status_code == 200:
            result = response.json()
            status_label.config(text=f"Job started on Muse.\nResponse: {result}")
            return True
        else:
            try:
                error_text = response.json()
            except Exception:
                error_text = response.text
            status_label.config(text=f"Error {response.status_code}: {error_text}")
            return False
    except Exception as e:
        status_label.config(text=f"Exception: {e}")
        return False
    
def poll_status_and_log_duration(barcode):
    url = server + "/api/jobs/api-query-job-status"
    data = {"pass_code": pass_code, "device_id": device_id}
    sleep_interval = 5
    elapsed = 0

    try:
        while True:
            time.sleep(sleep_interval)
            elapsed += sleep_interval
            response = requests.post(url, data=data, timeout=30)
            statusMessage = response.json().get("user_job_status", "")
            if statusMessage == 'idle':
                break

        csv_path = r"C:\log.csv"
        write_header = not os.path.exists(csv_path)

        with open(csv_path, mode='a', newline='') as file:
            writer = csv.writer(file)
            if write_header:
                writer.writerow(["barcode", "elapsed_time_seconds", "date"])
            writer.writerow([barcode, elapsed, datetime.now().isoformat(timespec="seconds")])

    except Exception as e:
        print(f"Polling exception: {e}")

def start_job(event=None):
    user_input = barcode_entry.get().strip()
    barcode, recipe_name, quantity = parse_filename(user_input)
    if barcode is None:
        status_label.config(text=f"Invalid input: {user_input}")

    output_folder = os.path.join(LASER_FOLDER_PATH, "Artwork")
    lap_file_path = None

    fixed_folder = os.path.join(LASER_FOLDER_PATH, "Fixed")
    preview_path = None
    for file_name in os.listdir(fixed_folder):
        if file_name.endswith(".png") and barcode in file_name:
            preview_path = os.path.join(fixed_folder, file_name)
            break

    if preview_path:
        img = Image.open(preview_path)
        img.thumbnail((200, 200))
        img_tk = ImageTk.PhotoImage(img)
        image_label.config(image=img_tk)
        image_label.image = img_tk
    else:
        image_label.config(image="", text="No preview found")


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

    # If quantity is None, default to 1
    if quantity is None:
        quantity = 1

    for job_num in range(quantity):
        status_label.config(text=f"Running job {job_num+1} of {quantity} for {barcode}")
        window.update()
        success = run_lap_job(server, pass_code, device_id, lap_file_path)
        if success:
            poll_status_and_log_duration(os.path.basename(lap_file_path))
        else:
            break

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

image_label = tk.Label(window)
image_label.pack(pady=5)

window.mainloop()