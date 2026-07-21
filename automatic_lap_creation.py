import os
import warnings
from PIL import Image
from lib import process_folder, LASER_FOLDER_PATH, DEVICE_ACCESS_CODE, IS_BETA, DEFAULT_SERVER, DEFAULT_PASS_CODE

# Static variables
warnings.filterwarnings("ignore", category=UserWarning, module="torchvision")
Image.MAX_IMAGE_PIXELS = None
warnings.filterwarnings("ignore", message=".*decompression.*", category=UserWarning)
SLEEP_TIME = 0  # seconds to wait between file scans, change in prod
TESTING_MODE = False  # when True, input files stay in Input/CC_Input after processing

if __name__ == "__main__":
    # Iterate through files in input folders (comment the while True for testing)
    # while True:
    input_folder_path = os.path.join(LASER_FOLDER_PATH, "Input")
    cc_input_folder_path = os.path.join(LASER_FOLDER_PATH, "CC_Input")
    input_processed_path = os.path.join(LASER_FOLDER_PATH, "Input_Processed")
    cc_input_processed_path = os.path.join(LASER_FOLDER_PATH, "CC_Input_Processed")
    output_folder_path = os.path.join(LASER_FOLDER_PATH, "Output")
    fixed_folder_path = os.path.join(LASER_FOLDER_PATH, "Fixed")

    # Ensure required folders exist
    os.makedirs(input_folder_path, exist_ok=True)
    os.makedirs(cc_input_folder_path, exist_ok=True)
    os.makedirs(input_processed_path, exist_ok=True)
    os.makedirs(cc_input_processed_path, exist_ok=True)
    os.makedirs(output_folder_path, exist_ok=True)
    os.makedirs(fixed_folder_path, exist_ok=True)

    processed_dest = False if TESTING_MODE else None
    if TESTING_MODE:
        print("TESTING_MODE: input files will not be moved to *_Processed")

    # Process Input folder (technical users, images already padded correctly)
    print("Processing Input folder (Muse/Input)...")
    process_folder(
        input_folder_path, output_folder_path, fixed_folder_path,
        laser_folder_path=LASER_FOLDER_PATH,
        server=DEFAULT_SERVER,
        pass_code=DEFAULT_PASS_CODE,
        device_access_code=DEVICE_ACCESS_CODE,
        sleep_time=SLEEP_TIME,
        processed_folder_path=processed_dest,
    )

    # Process CC_Input folder (non-technical customers, unsized/unpadded images)
    print("Processing CC_Input folder (Muse/CC_Input)...")
    process_folder(
        cc_input_folder_path, output_folder_path, fixed_folder_path,
        laser_folder_path=LASER_FOLDER_PATH,
        server=DEFAULT_SERVER,
        pass_code=DEFAULT_PASS_CODE,
        device_access_code=DEVICE_ACCESS_CODE,
        sleep_time=SLEEP_TIME,
        use_cc_input_logic=True,
        processed_folder_path=processed_dest,
    )