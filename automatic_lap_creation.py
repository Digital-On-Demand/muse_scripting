import os
import time
import traceback
import warnings
from PIL import Image
from lib import process_folder, LASER_FOLDER_PATH, DEVICE_ACCESS_CODE, DEFAULT_SERVER, DEFAULT_PASS_CODE

# Static variables
warnings.filterwarnings("ignore", category=UserWarning, module="torchvision")
Image.MAX_IMAGE_PIXELS = None
warnings.filterwarnings("ignore", message=".*decompression.*", category=UserWarning)
SLEEP_TIME = 0  # seconds to wait between files inside a scan
SCAN_INTERVAL_SECONDS = 10 * 60  # wait between folder scans
TESTING_MODE = False  # when True, input files stay in Input/CC_Input after processing

if __name__ == "__main__":
    input_folder_path = os.path.join(LASER_FOLDER_PATH, "Input")
    cc_input_folder_path = os.path.join(LASER_FOLDER_PATH, "CC_Input")
    input_processed_path = os.path.join(LASER_FOLDER_PATH, "Input_Processed")
    cc_input_processed_path = os.path.join(LASER_FOLDER_PATH, "CC_Input_Processed")
    output_folder_path = os.path.join(LASER_FOLDER_PATH, "Artwork")
    fixed_folder_path = os.path.join(LASER_FOLDER_PATH, "Fixed")
    failed_folder_path = os.path.join(LASER_FOLDER_PATH, "Failed")

    processed_dest = False if TESTING_MODE else None
    failed_dest = None if TESTING_MODE else failed_folder_path
    if TESTING_MODE:
        print("TESTING_MODE: input files will not be moved to *_Processed or Failed")

    while True:
        try:
            os.makedirs(input_folder_path, exist_ok=True)
            os.makedirs(cc_input_folder_path, exist_ok=True)
            os.makedirs(input_processed_path, exist_ok=True)
            os.makedirs(cc_input_processed_path, exist_ok=True)
            os.makedirs(output_folder_path, exist_ok=True)
            os.makedirs(fixed_folder_path, exist_ok=True)
            os.makedirs(failed_folder_path, exist_ok=True)

            process_folder(
                input_folder_path, output_folder_path, fixed_folder_path,
                server=DEFAULT_SERVER,
                pass_code=DEFAULT_PASS_CODE,
                device_access_code=DEVICE_ACCESS_CODE,
                sleep_time=SLEEP_TIME,
                processed_folder_path=processed_dest,
                failed_folder_path=failed_dest,
            )

            process_folder(
                cc_input_folder_path, output_folder_path, fixed_folder_path,
                server=DEFAULT_SERVER,
                pass_code=DEFAULT_PASS_CODE,
                device_access_code=DEVICE_ACCESS_CODE,
                sleep_time=SLEEP_TIME,
                use_cc_input_logic=True,
                processed_folder_path=processed_dest,
                failed_folder_path=failed_dest,
            )
        except KeyboardInterrupt:
            break
        except Exception:
            traceback.print_exc()

        try:
            time.sleep(SCAN_INTERVAL_SECONDS)
        except KeyboardInterrupt:
            break
