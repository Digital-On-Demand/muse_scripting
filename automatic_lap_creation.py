import requests
import json
import os
import time
import warnings
from PIL import Image
from lib import fix_image, parse_filename, get_spec_from_recipe_name

# static variables
warnings.filterwarnings("ignore", category=UserWarning, module="torchvision")
IS_BETA = True
LASER_FOLDER_PATH = "Z:\\Shared\\Muse"
DEVICE_ACCESS_CODE = "Tribute,Snowy,22"
SLEEP_TIME = 5 # seconds to wait between file scans, change in prod

if IS_BETA:
    server = "https://beta.fslaser.com"
    pass_code = "Whacking:Wrinkle:52"
else:
    server = "https://re4.fslaser.com"
    pass_code = "Protract;Aneurism;50"

def find_config_json(recipe_name):
    adjusted_recipe_name = recipe_name.lower().replace("glass", "").replace("Glass", "").replace("laser", "").replace("Laser", "")
    adjusted_recipe_name = ''.join(filter(lambda x: not x.isdigit(), adjusted_recipe_name))
    for filename in os.listdir(os.path.join(LASER_FOLDER_PATH, 'Settings')):
        if filename.startswith("settings-") and filename.endswith(".json"):
            if adjusted_recipe_name in filename.lower():
                #print("i found "+adjusted_recipe_name+" in "+filename.lower())
                return os.path.join(os.path.join(LASER_FOLDER_PATH, 'Settings'), filename)
            #print("i couldnt find "+adjusted_recipe_name+" in "+filename.lower())
            
def get_standard_lap(server, pass_code, DEVICE_ACCESS_CODE, input_file_path, json_file_path, output_file_path, recipe_name):
    try:
        #set URL
        url = f"{server}/api/jobs/standard-png-lap"

        # image manipulation
        transformation_matrix = [1, 0, 0, 1, 0, 0]
        with Image.open(input_file_path) as img:
            # get image size
            width, height = img.size
            # px to mm
            dpi = 300
            inches_per_mm = 1 / 25.4
            width_mm = width / dpi / inches_per_mm
            height_mm = height / dpi / inches_per_mm

            print(f"Attempting to center image on y-axis")
            transformation_matrix[4] = width_mm / -2

            if get_spec_from_recipe_name(recipe_name, "yTranslation"):
                print(f"Translating image {get_spec_from_recipe_name(recipe_name, 'yTranslation')}mm")
                transformation_matrix[5] = get_spec_from_recipe_name(recipe_name, "yTranslation")

            if get_spec_from_recipe_name(recipe_name, "xTranslation"):
                print(f"Translating image {get_spec_from_recipe_name(recipe_name, 'xTranslation')}mm")
                transformation_matrix[4] = get_spec_from_recipe_name(recipe_name, "xTranslation")

            print(f"Scaling image")
            transformation_matrix[0] = .3125
            transformation_matrix[3] = .3125

        # prepare data for request
        with open(input_file_path, "rb") as input_file, open(json_file_path, "rb") as json_file:
            data = {
                "pass_code": pass_code,
                "device_access_code": DEVICE_ACCESS_CODE,
                "transform_params": json.dumps(transformation_matrix)
            }
            files = {
                "png_file": input_file,
                "json_file": json_file,
            }

            # make request
            print(f"Processing file: {input_file_path}")
            response = requests.post(url, data=data, files=files, timeout=60)
            
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
    #while True:
        input_folder_path = os.path.join(LASER_FOLDER_PATH, "Input")
        output_folder_path = os.path.join(LASER_FOLDER_PATH, "Output")
        fixed_folder_path = os.path.join(LASER_FOLDER_PATH, "Fixed")

        # ensure required folders exist
        os.makedirs(input_folder_path, exist_ok=True)
        os.makedirs(output_folder_path, exist_ok=True)
        os.makedirs(fixed_folder_path, exist_ok=True)

        for filename in os.listdir(input_folder_path):
            if filename.endswith(".png"):
                #parse filename
                barcode, recipe_name, quantity = parse_filename(filename)
                if barcode is None:
                    print(f"Invalid filename format: {filename}")
                    continue

                # dynamically get material type
                config_json = find_config_json(recipe_name)
                if not config_json:
                    print(f"No configuration JSON found for recipe: {recipe_name}")
                    continue

                # dynamically set file paths
                input_file_path = os.path.join(input_folder_path, filename)
                json_file_path = config_json

                #fix the image
                fixed_file_path = os.path.join(fixed_folder_path, filename)
                fix_image(input_file_path, recipe_name, fixed_file_path)

                # do the thing
                quantity_suffix = f"-{quantity}" if quantity is not None else ""
                output_file_path = os.path.join(output_folder_path, f"{barcode}-{recipe_name}{quantity_suffix}.lap")
                success = get_standard_lap(
                    server, pass_code, DEVICE_ACCESS_CODE,
                    fixed_file_path, json_file_path, output_file_path, recipe_name
                )

                # sleep a little
                print(f"Sleeping for {SLEEP_TIME} seconds before next file scan...")
                time.sleep(SLEEP_TIME)