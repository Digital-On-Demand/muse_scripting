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

def apply_rotation_and_flipping(img, recipe_name):
    """Apply rotation and flipping transformations based on recipe specs"""
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
    return img

def fix_image(input_path, recipe_name, fixed_file_path):
    with Image.open(input_path) as img:
        if DO_NOTHING:
            fixed = img
        else:
            #resize image
            artboard_width = get_spec_from_recipe_name(recipe_name, "artboardWidth")
            artboard_height = get_spec_from_recipe_name(recipe_name, "artboardHeight")
            
            if artboard_width and artboard_height and artboard_width > 0 and artboard_height > 0:
                print(f"Scaling image to artboard size: {artboard_width}x{artboard_height}")
                img = img.resize((artboard_width, artboard_height), Image.Resampling.LANCZOS)
            elif artboard_width and artboard_width > 0:
                print(f"Scaling image width to artboard width: {artboard_width}")
                aspect_ratio = img.height / img.width
                new_height = int(artboard_width * aspect_ratio)
                img = img.resize((artboard_width, new_height), Image.Resampling.LANCZOS)
            elif artboard_height and artboard_height > 0:
                print(f"Scaling image height to artboard height: {artboard_height}")
                aspect_ratio = img.width / img.height
                new_width = int(artboard_height * aspect_ratio)
                img = img.resize((new_width, artboard_height), Image.Resampling.LANCZOS)
            ###if get_spec_from_recipe_name(recipe_name, "taperAngle") != 0:
             ###   img = warp_trapezoid_trig(img, get_spec_from_recipe_name(recipe_name, "taperAngle"))
           ###     print("Tapered glass | Warping frustum")

            # Apply rotation and flipping
            img = apply_rotation_and_flipping(img, recipe_name)


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

def fix_image_cc(input_path, recipe_name, fixed_file_path):
    """Fix image for CC_Input folder - simple background removal with rotation/flipping only"""
    with Image.open(input_path) as img:
        if DO_NOTHING:
            fixed = img
        else:
            #resize image with aspect ratio preservation and padding for CC_Input
            artboard_width = get_spec_from_recipe_name(recipe_name, "artboardWidth")
            artboard_height = get_spec_from_recipe_name(recipe_name, "artboardHeight")
            
            if artboard_width and artboard_height and artboard_width > 0 and artboard_height > 0:
                # Get dynamic padding values from recipe specs
                padding_start = get_spec_from_recipe_name(recipe_name, "paddingStart")
                padding_end = get_spec_from_recipe_name(recipe_name, "paddingEnd")
                
                # Check if both padding values are present
                if padding_start is not None and padding_end is not None:
                    print(f"CC_Input: Scaling image to fit in {padding_start*100:.0f}%-{padding_end*100:.0f}% height range: {artboard_width}x{artboard_height}")
                    
                    # Calculate the dynamic height range based on padding specs
                    available_height = artboard_height * (padding_end - padding_start)
                    range_start = artboard_height * padding_start
                    
                    # Calculate scaling factor to fit within the dynamic height range while preserving aspect ratio
                    scale_x = artboard_width / img.width
                    scale_y = available_height / img.height  # Scale to fit in available height range
                    scale = min(scale_x, scale_y)  # Use smaller scale to fit within bounds
                    
                    # Calculate new dimensions
                    new_width = int(img.width * scale)
                    new_height = int(img.height * scale)
                    
                    # Resize image maintaining aspect ratio
                    img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                    
                    # Ensure image is in RGBA mode before pasting
                    if img.mode != 'RGBA':
                        img = img.convert('RGBA')
                    
                    # Create new image with artboard dimensions and transparent background
                    padded_img = Image.new('RGBA', (artboard_width, artboard_height), (255, 255, 255, 0))
                    
                    # Calculate position to center horizontally and vertically in the dynamic range
                    x_offset = (artboard_width - new_width) // 2
                    y_offset = int(range_start + (available_height - new_height) // 2)
                    
                    # Paste the resized image onto the padded canvas with alpha blending
                    padded_img.paste(img, (x_offset, y_offset), img)
                    img = padded_img
                else:
                    # No padding specified - scale to fit full artboard while preserving aspect ratio
                    print(f"CC_Input: Scaling image to fit full artboard with aspect ratio preservation: {artboard_width}x{artboard_height}")
                    
                    # Calculate scaling factor to fit within full artboard while preserving aspect ratio
                    scale_x = artboard_width / img.width
                    scale_y = artboard_height / img.height
                    scale = min(scale_x, scale_y)  # Use smaller scale to fit within bounds
                    
                    # Calculate new dimensions
                    new_width = int(img.width * scale)
                    new_height = int(img.height * scale)
                    
                    # Resize image maintaining aspect ratio
                    img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                    
                    # Ensure image is in RGBA mode before pasting
                    if img.mode != 'RGBA':
                        img = img.convert('RGBA')
                    
                    # Create new image with artboard dimensions and transparent background
                    padded_img = Image.new('RGBA', (artboard_width, artboard_height), (255, 255, 255, 0))
                    
                    # Calculate position to center the resized image
                    x_offset = (artboard_width - new_width) // 2
                    y_offset = (artboard_height - new_height) // 2
                    
                    # Paste the resized image onto the padded canvas with alpha blending
                    padded_img.paste(img, (x_offset, y_offset), img)
                    img = padded_img
                
            elif artboard_width and artboard_width > 0:
                print(f"CC_Input: Scaling image width to artboard width with padding: {artboard_width}")
                aspect_ratio = img.height / img.width
                new_height = int(artboard_width * aspect_ratio)
                img = img.resize((artboard_width, new_height), Image.Resampling.LANCZOS)
            elif artboard_height and artboard_height > 0:
                print(f"CC_Input: Scaling image height to artboard height with padding: {artboard_height}")
                aspect_ratio = img.width / img.height
                new_width = int(artboard_height * aspect_ratio)
                img = img.resize((new_width, artboard_height), Image.Resampling.LANCZOS)

            # Apply rotation and flipping
            img = apply_rotation_and_flipping(img, recipe_name)

            # Background removal for CC_Input
            if img.mode != 'RGBA':
                img = img.convert('RGBA')
            
            # Convert to numpy array for processing
            data = np.array(img)
            r, g, b, a = data[:,:,0], data[:,:,1], data[:,:,2], data[:,:,3]
            
            # Simple background removal using white/light background detection
            # Create a mask for pixels that are likely background (white/light colors)
            # This is a simple approach - you can adjust thresholds as needed
            white_threshold = 240  # Adjust this value (0-255) to tune sensitivity
            background_mask = (r > white_threshold) & (g > white_threshold) & (b > white_threshold) & (a > 0)
            
            # Set background pixels to transparent (only if they're not already transparent)
            data[background_mask, 3] = 0  # Set alpha to 0 for background
            
            # Ensure non-background pixels are fully opaque (only if they're not already transparent)
            non_background = ~background_mask & (a > 0)
            data[non_background, 3] = 255
            
            # Ensure ALL transparent areas are completely clean (no stray pixels)
            transparent_mask = a == 0
            data[transparent_mask, 0] = 255  # R - pure white
            data[transparent_mask, 1] = 255  # G - pure white  
            data[transparent_mask, 2] = 255  # B - pure white
            data[transparent_mask, 3] = 0    # A - fully transparent
            
            # Additional cleanup: ensure any pixels with very low alpha are completely transparent
            very_low_alpha = a < 10  # Less than 10/255 alpha
            data[very_low_alpha, 0] = 255
            data[very_low_alpha, 1] = 255
            data[very_low_alpha, 2] = 255
            data[very_low_alpha, 3] = 0
            
            # Convert back to PIL Image
            fixed = Image.fromarray(data, mode='RGBA')

        fixed.save(fixed_file_path)

def parse_filename(filename):
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