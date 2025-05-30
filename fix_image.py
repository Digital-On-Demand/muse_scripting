import numpy as np
from PIL import Image
import sys
import os

# static variables
DO_NOTHING = True
WHITE_THRESHOLD = 245  # can be tweaked (0-255)

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

            #make rgba just in case
            if fixed.mode != 'RGBA':
                fixed = fixed.convert('RGBA')

            #get image as np array
            data = np.array(fixed)

            #rgba channels
            r, g, b, a = data[:,:,0], data[:,:,1], data[:,:,2], data[:,:,3]

            #mask to check for white pixels
            white_mask = (r > WHITE_THRESHOLD) & (g > WHITE_THRESHOLD) & (b > WHITE_THRESHOLD)

            #make white pixels transparent
            data[white_mask, 3] = 0

            #invert colors
            data[..., :3] = 255 - data[..., :3]

            #recombine and save (overwrite) image
            fixed = Image.fromarray(data, mode='RGBA')
        fixed.save(fixed_file_path)

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