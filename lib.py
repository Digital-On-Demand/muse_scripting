import numpy as np
from PIL import Image
from skimage.filters.rank import entropy
from skimage.morphology import disk
from skimage.util import img_as_ubyte
import cv2

# static variables
DO_NOTHING = False  #disables all image manip
WHITE_THRESHOLD = 250  # can be tweaked (0-255)
BLACK_THRESHOLD = 4  # can be tweaked (0-255)
OPACITY_THRESHOLD = 0  # can be tweaked (0-255)
ENTROPY_THRESHOLD = 16  # can be tweaked (0-255)
DISK_RADIUS = 4  # radius for disk used in entropy calculation, can be tweaked

def fix_image(input_path, recipe_name, fixed_file_path):
    with Image.open(input_path) as img:
        if DO_NOTHING:
            fixed = img
        else:
            #some recipe-specific transformations, otherwise rotate 90 degrees CCW
            if "rocksbottom" in recipe_name.lower():
                print("Flipping image along x axis")
                fixed = img.transpose(Image.FLIP_LEFT_RIGHT)
            elif "chug" in recipe_name.lower() or "shot" in recipe_name.lower():
                print("Rotating image 270 degrees CCW")
                fixed = img.rotate(270, expand=True)
            else:
                print("Rotating image 90 degrees CCW")
                fixed = img.rotate(90, expand=True)

            #ensure 4 channel mode
            if fixed.mode != 'RGBA':
                fixed = fixed.convert('RGBA')

            #image to image array
            data = np.array(fixed)
            r, g, b, a = data[:,:,0], data[:,:,1], data[:,:,2], data[:,:,3]

            if "steel" in recipe_name.lower():
                #set all non-transparent pixels to black
                opaque_mask = a > OPACITY_THRESHOLD
                data[opaque_mask, 0] = 0
                data[opaque_mask, 1] = 0
                data[opaque_mask, 2] = 0
                data[opaque_mask, 3] = 255

                #set transparent pixels to white (for display purposes)
                data[~opaque_mask, 0:3] = 255
                data[~opaque_mask, 3] = 0
                
            elif "glass" in recipe_name.lower():
                # Convert image to grayscale
                gray = cv2.cvtColor(np.dstack((r, g, b)).astype(np.uint8), cv2.COLOR_RGB2GRAY)

                # Normalize grayscale to uint8 if not already
                gray_ubyte = img_as_ubyte(gray / 255.0)

                # Compute entropy using a small disk neighborhood (adjust radius to tune sensitivity)
                entropy_img = entropy(gray_ubyte, disk(DISK_RADIUS))

                # Threshold to create photo mask
                photo_mask = (entropy_img > 3.5) & (a > OPACITY_THRESHOLD)  # tweak threshold if needed

                # Invert photo regions
                data[..., 0][photo_mask] = 255 - r[photo_mask]
                data[..., 1][photo_mask] = 255 - g[photo_mask]
                data[..., 2][photo_mask] = 255 - b[photo_mask]
                data[..., 3][photo_mask] = 255

                # Set non-photo opaque regions to solid black
                non_photo = (~photo_mask) & (a > OPACITY_THRESHOLD)
                data[..., 0][non_photo] = 0
                data[..., 1][non_photo] = 0
                data[..., 2][non_photo] = 0
                data[..., 3][non_photo] = 255

                # Optional: fully transparent = white for preview
                transparent = a <= OPACITY_THRESHOLD
                data[..., 0][transparent] = 255
                data[..., 1][transparent] = 255
                data[..., 2][transparent] = 255
                data[..., 3][transparent] = 0

            #save image
            fixed = Image.fromarray(data, mode='RGBA')
        fixed.save(fixed_file_path)

def parse_filename(filename):
    parts = filename.split("-")
    if len(parts) >= 3:
        barcode = parts[0]
        recipe_name = parts[1]
        try:
            quantity = int(parts[2].split(".")[0])
        except ValueError:
            return (None, None, None)
        return (barcode, recipe_name, quantity)
    else:
        return (None, None, None)