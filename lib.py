import numpy as np
from PIL import Image
from skimage.filters.rank import entropy
from skimage.morphology import disk
from skimage.util import img_as_ubyte
import cv2
import json
import os

# static variables
# Resolve recipe specs file relative to this module for portability
RECIPE_SPECS_FILE = os.path.join(os.path.dirname(__file__), "recipe_specs.json")
DO_NOTHING = False  #disables all image manip
WHITE_THRESHOLD = 250  # can be tweaked (0-255) - previous optimal was 250
BLACK_THRESHOLD = 4  # can be tweaked (0-255) - previous optimal was 4
OPACITY_THRESHOLD = 0  # can be tweaked (0-255) - previous optimal was 0
ENTROPY_THRESHOLD = 2  # can be tweaked (0-255) - previous optimal was 2
DISK_RADIUS = 4  # radius for disk used in entropy calculation - previous optimal was 4

def warp_trapezoid_trig(img, angle_deg):
    #print(f"Warping frustum with angle {angle_deg} degrees")
    import math
    from PIL import Image
    import numpy as np

    theta = math.radians(angle_deg)
    H = img.height
    W = img.width  # top width = artboard width

    result_np = np.zeros((H, W, 4), dtype=np.uint8)
    img_np = np.array(img.convert("RGBA"))

    for y in range(H):
        current_width = int(W - 2 * y * math.tan(theta))
        if current_width <= 0:
            continue
        row = img_np[y:y+1, :, :]
        resized_row = Image.fromarray(row, 'RGBA').resize((current_width, 1), resample=Image.BICUBIC)
        x_offset = (W - current_width) // 2
        result_np[y:y+1, x_offset:x_offset+current_width, :] = np.array(resized_row)

    return Image.fromarray(result_np, 'RGBA')

def _load_recipe_specs():
    try:
        with open(RECIPE_SPECS_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {}


# Cache recipe specs at module import to avoid repeated disk I/O
RECIPE_SPECS = _load_recipe_specs()


def get_spec_from_recipe_name(recipe_name, spec):
    if not recipe_name:
        return None
    for key, value in RECIPE_SPECS.items():
        if key.lower() in recipe_name.lower():
            return value.get(spec)
    return None

def fix_image(input_path, recipe_name, fixed_file_path):
    with Image.open(input_path) as img:
        if DO_NOTHING:
            fixed = img
        else:
            ###if get_spec_from_recipe_name(recipe_name, "taperAngle") != 0:
             ###   img = warp_trapezoid_trig(img, get_spec_from_recipe_name(recipe_name, "taperAngle"))
           ###     print("Tapered glass | Warping frustum")

            if not get_spec_from_recipe_name(recipe_name, "rotary"):
                print("Non-rotary | Flipping image horizontally")
                img = img.transpose(Image.FLIP_LEFT_RIGHT)
            else:
                if get_spec_from_recipe_name(recipe_name, "opensTowardsChuck"):
                    print("Opens towards chuck | Rotating image 270 degrees")
                    img = img.rotate(270, expand=True)
                if not get_spec_from_recipe_name(recipe_name, "opensTowardsChuck"):
                    print("Opens away from chuck | Rotating image 90 degrees")
                    img = img.rotate(90, expand=True)


            fixed = img

            #ensure 4 channel mode
            if fixed.mode != 'RGBA':
                fixed = fixed.convert('RGBA')

            #image to image array
            data = np.array(fixed)
            r, g, b, a = data[:,:,0], data[:,:,1], data[:,:,2], data[:,:,3]


            if get_spec_from_recipe_name(recipe_name, "material") == "steel":
                print("Steel job | Doing stuff")
                #set all non-transparent pixels to black
                opaque_mask = a > OPACITY_THRESHOLD
                data[opaque_mask, 0] = 0
                data[opaque_mask, 1] = 0
                data[opaque_mask, 2] = 0
                data[opaque_mask, 3] = 255

                #set transparent pixels to white (for display purposes)
                data[~opaque_mask, 0:3] = 255
                data[~opaque_mask, 3] = 0
                
                
            elif get_spec_from_recipe_name(recipe_name, "material") == "glass":
                print("Glass job | Doing stuff")
                # Convert image to grayscale
                gray = cv2.cvtColor(np.dstack((r, g, b)).astype(np.uint8), cv2.COLOR_RGB2GRAY)

                # Normalize grayscale to uint8 if not already
                gray_ubyte = img_as_ubyte(gray / 255.0)

                # Compute entropy using a small disk neighborhood (adjust radius to tune sensitivity)
                entropy_img = entropy(gray_ubyte, disk(DISK_RADIUS))

                # Threshold to create photo mask
                photo_mask = (entropy_img > ENTROPY_THRESHOLD) & (a > OPACITY_THRESHOLD)

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
    """Parse names like 'BARCODE-recipe-name-10.png' or 'BARCODE-recipe-name-10.lap'.

    - Returns (barcode, recipe_name, quantity)
    - If only a barcode is provided, returns (barcode, None, None)
    - If quantity is missing, returns quantity as None
    """
    name = os.path.basename(filename)
    if name.lower().endswith((".png", ".lap")):
        name = name.rsplit(".", 1)[0]
    parts = name.split("-")
    if not parts:
        return (None, None, None)

    barcode = parts[0]
    if len(parts) == 1:
        return (barcode, None, None)

    # Try to interpret the last segment as quantity
    try:
        quantity = int(parts[-1])
        recipe_name = "-".join(parts[1:-1]) if len(parts) > 2 else ""
    except ValueError:
        recipe_name = "-".join(parts[1:])
        quantity = None

    return (barcode, recipe_name if recipe_name != "" else None, quantity)