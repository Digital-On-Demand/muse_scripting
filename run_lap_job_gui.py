import tkinter as tk
from tkinter import messagebox
import os
import time
import requests
from PIL import Image, ImageTk
import csv
from lib import parse_filename

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
    
def poll_status_and_log_duration(barcode):
    url = server + "/api/jobs/api-query-job-status"
    data = {"pass_code": pass_code, "device_access_code": DEVICE_ACCESS_CODE}
    sleep_interval = 5
    elapsed = 0

    try:
        while True:
            time.sleep(sleep_interval)
            elapsed += sleep_interval
            response = requests.post(url, data=data)

            if response.status_code != 200:
                print(f"Polling error {response.status_code}: {response.text}")
                break

            status = response.json().get("user_job_status", "").lower()
            if status != "running":
                break

        csv_path = os.path.join(LASER_FOLDER_PATH, "job_times.csv")
        write_header = not os.path.exists(csv_path)

        with open(csv_path, mode='a', newline='') as file:
            writer = csv.writer(file)
            if write_header:
                writer.writerow(["barcode", "elapsed_time_seconds"])
            writer.writerow([barcode, elapsed])

    except Exception as e:
        print(f"Polling exception: {e}")

def start_job(event=None):
    barcode, recipe_name, quantity = parse_filename(file_name)
    if barcode is None:
        print(f"Invalid filename format: {file_name}")

    output_folder = os.path.join(LASER_FOLDER_PATH, "Output")
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

    success = run_lap_job(server, pass_code, DEVICE_ACCESS_CODE, lap_file_path)

    for job_num in range(quantity):
        status_label.config(text=f"Running job {job_num+1} of {quantity} for {barcode}")
        window.update()
        success = run_lap_job(server, pass_code, DEVICE_ACCESS_CODE, lap_file_path)
        if success:
            poll_status_and_log_duration(barcode)
        else:
            status_label.config(text=f"Failed job {job_num+1} for {barcode}")
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