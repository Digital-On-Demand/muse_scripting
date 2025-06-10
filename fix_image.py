import numpy as np
from PIL import Image
import sys
import os
from scipy.ndimage import binary_dilation, label

# static variables
DO_NOTHING = False  # set to True to skip image processing
WHITE_THRESHOLD = 253  # can be tweaked (0-255)
BLACK_THRESHOLD = 2  # can be tweaked (0-255)
TRANSPARENT_THRESHOLD = 250  # can be tweaked (0-255)

def edge_contiguous_mask(mask):
    from skimage.segmentation import clear_border
    return clear_border(mask)

def compress_contrast(arr, factor=0.25):
    return np.clip((arr - 128) * factor + 128, 0, 255).astype(np.uint8)

def fix_image(input_path, recipe_name, fixed_file_path):
    with Image.open(input_path) as img:
        if DO_NOTHING:
            fixed = img
        else:
            # some image manip based on recipe
            if "rocksbottom" in recipe_name.lower():
                print("Flipping image along x axis")
                fixed = img.transpose(Image.FLIP_LEFT_RIGHT)
            elif "chug" in recipe_name.lower():
                print("Rotating image 180 degrees")
                fixed = img.rotate(180, expand=True)
            else:
                print("Rotating image 90 degrees CCW")
                fixed = img.rotate(90, expand=True)

            # ensure image is in RGBA mode
            if fixed.mode != 'RGBA':
                fixed = fixed.convert('RGBA')

            # convert to numpy array for processing
            data = np.array(fixed)
            r, g, b, a = data[:,:,0], data[:,:,1], data[:,:,2], data[:,:,3]

            # Build masks
            white_like = (r > WHITE_THRESHOLD) & (g > WHITE_THRESHOLD) & (b > WHITE_THRESHOLD)
            black_like = (r < BLACK_THRESHOLD) & (g < BLACK_THRESHOLD) & (b < BLACK_THRESHOLD)
            transparent = a < TRANSPARENT_THRESHOLD

            # Find edge pixels connected to transparency using dilation
            from scipy.ndimage import binary_dilation

            near_transparent = binary_dilation(transparent, iterations=1)
            edge_connected = (white_like | black_like) & near_transparent

            # Invert everything except edge-connected white/black
            invert_mask = ~edge_connected

            data[..., 0][invert_mask] = 255 - r[invert_mask]
            data[..., 1][invert_mask] = 255 - g[invert_mask]
            data[..., 2][invert_mask] = 255 - b[invert_mask]

            fixed = Image.fromarray(data, mode='RGBA')
        fixed.save(fixed_file_path, dpi=(300, 300))

if __name__ == "__main__":
    path = input("Enter the folder path: ")
    for filename in os.listdir(path):
        file_path = os.path.join(path, filename)
        parts = filename.split("-")
        if len(parts) >= 3:
            barcode = parts[0]
            recipe_name = parts[1]
            quantity = parts[2].split(".")[0]
        fix_image(file_path, recipe_name)
    print(f"images in {path} have been fixed.")