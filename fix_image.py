import numpy as np
from PIL import Image
import sys
import os

# static variables
DO_NOTHING = False  # set to True to skip image processing
WHITE_THRESHOLD = 250  # can be tweaked (0-255)
BLACK_THRESHOLD = 4  # can be tweaked (0-255)

def fix_image(input_path, recipe_name, fixed_file_path):
    with Image.open(input_path) as img:
        if DO_NOTHING:
            fixed = img
        else:
            # flip image along x axis if rocksBottom, otherwise rotate 90 degrees CCW
            if "rocksbottom" in recipe_name.lower():
                print("Flipping image along x axis")
                fixed = img.transpose(Image.FLIP_LEFT_RIGHT)
            else:
                print("Rotating image 90 degrees CCW")
                fixed = img.rotate(90, expand=True)

            # Ensure RGBA
            if fixed.mode != 'RGBA':
                fixed = fixed.convert('RGBA')

            # To NumPy for pixel math
            data = np.array(fixed)
            r, g, b, a = data[:,:,0], data[:,:,1], data[:,:,2], data[:,:,3]

            # Make white pixels transparent
            white_mask = (r > WHITE_THRESHOLD) & (g > WHITE_THRESHOLD) & (b > WHITE_THRESHOLD)
            data[white_mask, 3] = 0

            # Create masks for selective inversion
            black_mask = (r < BLACK_THRESHOLD) & (g < BLACK_THRESHOLD) & (b < BLACK_THRESHOLD)
            invert_mask = ~(white_mask | black_mask)

            # Invert only relevant pixels
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