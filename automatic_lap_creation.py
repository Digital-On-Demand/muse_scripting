import requests
import json
import os
import time
from PIL import Image, ImageDraw
from fix_image import fix_image

# global variables
IS_BETA = True
laser_folder_path = "Z:\\Shared\\Muse"
device_access_code = "Tribute,Snowy,22"
sleep_time = 5 # seconds to wait between file scans, change in prod

if IS_BETA:
    server = "https://beta.fslaser.com"
    pass_code = "Whacking:Wrinkle:52"
else:
    server = "https://re4.fslaser.com"
    pass_code = "Protract;Aneurism;50"

def get_standard_lap(server, pass_code, device_access_code, input_file_path, json_file_path, output_file_path):
    try:
        #set URL
        url = f"{server}/api/jobs/standard-png-lap"

        # image manipulation
        transformation_matrix = [1, 0, 0, 1, 0, 0]
        with Image.open(input_file_path) as img:
            #with open(json_file_path, "r") as json_file:
                #settings = json.load(json_file)
                #rotary_settings = settings.get("rotary", {})
                #rotary_position_near_chuck = math.ceil(rotary_settings.get("rotaryPositionNearChuck_mm", [0, 0])[0])
                #rotary_position_far_chuck = math.ceil(rotary_settings.get("rotaryPositionFarChuck_mm", [0, 0])[0])
                #print(f"Rotary positions:\nNear: {rotary_position_near_chuck}, Far: {rotary_position_far_chuck}")
            #print_area_width = abs(rotary_position_near_chuck) + abs(rotary_position_far_chuck)
            #print(f"Print area width: {print_area_width}")

            # get image size
            width, height = img.size
            # Convert width from pixels to millimeters
            dpi = 300
            inches_per_mm = 1 / 25.4
            width_mm = width / dpi / inches_per_mm
            height_mm = height / dpi / inches_per_mm

            print(f"Attempting to center image on y-axis")
            transformation_matrix[4] = width_mm / -2

            print(f"Scaling image")
            transformation_matrix[0] = .3125
            transformation_matrix[3] = .3125

        # prepare data for request
        with open(input_file_path, "rb") as input_file, open(json_file_path, "rb") as json_file:
            data = {
                "pass_code": pass_code,
                "device_access_code": device_access_code,
                "transform_params": json.dumps(transformation_matrix)
            }
            files = {
                "png_file": input_file,
                "json_file": json_file,
            }

            # make request
            print(f"Processing file: {input_file_path}")
            response = requests.post(url, data=data, files=files)
            
            # write response to new file if successful, otherwise do some error handling
            if response.status_code == 200:
                print("Server responded successfully")
                with open(output_file_path, "wb") as f:
                    f.write(response.content)
                print(f"Successfully created LAP file at: {os.path.abspath(output_file_path)}")
                return True
            else:
                print(f"Error: Server responded with status code {response.status_code}")
                print("Raw response text:", response.text)
                return False
    except Exception as e:
        print(f"An error occurred: {e}")
        return False

if __name__ == "__main__":
    # iterate through files in input folder (comment the while True for testing)
    while True:
        for filename in os.listdir(f"{laser_folder_path}\\Input"):
            if filename.endswith(".png"):
                # dynamically get barcode, recipe name, and quantity from filename
                parts = filename.split("-")
                if len(parts) >= 3:
                    barcode = parts[0]
                    recipe_name = parts[1]
                    quantity = parts[2].split(".")[0]
                else:
                    print(f"Filename format invalid: {filename}")
                    continue

                # dynamically get material type
                config_json = f"settings-{recipe_name}"

                # dynamically set file paths
                input_file_path = os.path.join(f"{laser_folder_path}\\Input", filename)
                json_file_path = os.path.join(laser_folder_path, f"{config_json}.json")
                output_folder_path = os.path.join(laser_folder_path, "Output")
                fixed_folder_path = os.path.join(laser_folder_path, "Fixed")

                #fix the image
                fixed_file_path = os.path.join(fixed_folder_path, filename)
                fix_image(input_file_path, recipe_name, fixed_file_path)

                # do the thing
                output_file_path = os.path.join(output_folder_path, f"{barcode}-{recipe_name}-{quantity}.lap")
                success = get_standard_lap(
                    server, pass_code, device_access_code,
                    fixed_file_path, json_file_path, output_file_path
                )
                
                # if success, delete the input file (comment block for testing)
                #if success:
                #    try:
                #        os.remove(input_file_path)  # UNHIDE ME
                #        print(f"Deleted old file: {input_file_path}")
                #   except Exception as e:
                #        print(f"Failed to delete file: {e}")

                # sleep a little
                time.sleep(sleep_time)