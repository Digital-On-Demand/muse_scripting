import numpy as np
from PIL import Image
import json
import os
import shutil
import requests
import time
import re
from datetime import datetime

from multi_decoration import build_overrides_for_multi_decoration

# Static variables
# Resolve recipe specs file relative to this module for portability
RECIPE_SPECS_FILE = os.path.join(os.path.dirname(__file__), "recipe_specs.json")
DO_NOTHING = False  # Disables all image manipulation (for testing)

_BARCODE_DECORATION_SUFFIX_RE = re.compile(r"^(?P<base>\d+)\.(?P<idx>[12])$")


def _strip_multi_decoration_suffix(barcode: str) -> str:
    if not barcode:
        return barcode
    m = _BARCODE_DECORATION_SUFFIX_RE.match(str(barcode))
    return m.group("base") if m else str(barcode)

def _load_recipe_specs():
    try:
        with open(RECIPE_SPECS_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {}


# Cache recipe specs at module import to avoid repeated disk I/O
RECIPE_SPECS = _load_recipe_specs()

# Configuration constants (can be overridden by callers)
LASER_FOLDER_PATH = "Y:\\Shared\\Muse"
SETTINGS_FOLDER_PATH = "C:\\Musery\\settings"
DEVICE_ACCESS_CODE = "2CCF67398804"
IS_BETA = False

if IS_BETA:
    DEFAULT_SERVER = "https://beta.fslaser.com"
    DEFAULT_PASS_CODE = "Decoy!Retiree!25"
else:
    DEFAULT_SERVER = "https://re4.fslaser.com"
    DEFAULT_PASS_CODE = "Ignore;Crablike;37"


def normalize_recipe_name(recipe_name):
    """
    Normalize a recipe name using the aliases mapping.
    Uses EXACT recipe name match (case-insensitive) to find alias.
    Returns the canonical recipe name if an alias exists, otherwise returns the original name.
    """
    if not recipe_name:
        return None
    
    aliases = RECIPE_SPECS.get("aliases", {})
    
    # Check for exact match in aliases (case-insensitive)
    recipe_lower = recipe_name.lower()
    for alias, canonical in aliases.items():
        if alias.lower() == recipe_lower:
            return canonical
    
    # No alias found, return original recipe name
    return recipe_name


def find_config_json(recipe_name, settings_path=None):
    """
    Find the configuration JSON file for a given recipe name.
    Uses normalized recipe name from aliases to find matching settings file.
    """
    if settings_path is None:
        settings_path = SETTINGS_FOLDER_PATH
    
    # Normalize recipe name using aliases
    normalized_name = normalize_recipe_name(recipe_name)
    if not normalized_name:
        return None
    
    # Clean up the normalized name for file matching
    search_name = normalized_name.lower()
    
    if not os.path.exists(settings_path):
        return None
    
    for filename in os.listdir(settings_path):
        if filename.startswith("settings-") and filename.endswith(".json"):
            if search_name in filename.lower():
                return os.path.join(settings_path, filename)
    
    return None


def get_standard_lap(server, pass_code, device_access_code, input_file_path, json_file_path, output_file_path, transformation_matrix, log_filename=None):
    """
    Create a standard PNG LAP file by sending image and config to the server.
    Uses the provided transformation matrix (calculated during image fixing).
    Returns True if successful, False otherwise.
    """
    log_name = log_filename or input_file_path
    try:
        # Set URL
        url = f"{server}/api/jobs/standard-png-lap"

        # Prepare data for request
        with open(input_file_path, "rb") as png_file, open(json_file_path, "rb") as json_file:
            data = {
                "pass_code": pass_code,
                "device_id": device_access_code,
                "transform_params": json.dumps(transformation_matrix),
            }
            files = {
                "png_file": png_file,
                "json_file": json_file,
            }

            _log_job(log_name, "request sent to server")
            response = requests.post(url, data=data, files=files, timeout=60)
            _log_job(log_name, "server sent response")

            if response.status_code == 200:
                with open(output_file_path, "wb") as f:
                    f.write(response.content)
                return True
            return False
    except Exception:
        return False


def _move_input_file(src_path, dest_folder, label, overwrite=False):
    """Move an input file into dest_folder."""
    if not dest_folder or not src_path or not os.path.exists(src_path):
        return
    try:
        os.makedirs(dest_folder, exist_ok=True)
        dest_path = os.path.join(dest_folder, os.path.basename(src_path))
        if os.path.exists(dest_path):
            if overwrite:
                os.remove(dest_path)
            else:
                stem, ext = os.path.splitext(os.path.basename(src_path))
                dest_path = os.path.join(dest_folder, f"{stem}-{int(time.time())}{ext}")
        shutil.move(src_path, dest_path)
    except Exception:
        return


def processed_folder_for_input(folder_path):
    """Map Input / CC_Input to their *_Processed siblings under the same parent."""
    base = os.path.basename(os.path.normpath(folder_path))
    parent = os.path.dirname(os.path.normpath(folder_path))
    mapping = {
        "Input": "Input_Processed",
        "CC_Input": "CC_Input_Processed",
    }
    processed_name = mapping.get(base)
    if not processed_name:
        return None
    return os.path.join(parent, processed_name)


def _log_job(filename, status):
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    name = os.path.splitext(os.path.basename(filename))[0]
    print(f"[{stamp}] - {name} - {status}", flush=True)


def process_folder(folder_path, output_folder_path, fixed_folder_path, 
                   server=None, pass_code=None, 
                   device_access_code=None, sleep_time=1, use_cc_input_logic=False,
                   processed_folder_path=None, failed_folder_path=None):
    """
    Process files from a specific input folder.
    Applies image fixes and creates LAP files for each PNG found.
    Successes go to processed_folder_path; failures go to failed_folder_path.
    """
    if server is None:
        server = DEFAULT_SERVER
    if pass_code is None:
        pass_code = DEFAULT_PASS_CODE
    if device_access_code is None:
        device_access_code = DEVICE_ACCESS_CODE

    if processed_folder_path is None:
        processed_folder_path = processed_folder_for_input(folder_path)
    
    png_filenames = [fn for fn in os.listdir(folder_path) if fn.lower().endswith(".png")]
    multi_overrides = build_overrides_for_multi_decoration(folder_path, png_filenames)

    for filename in png_filenames:
        input_file_path = os.path.join(folder_path, filename)
        try:
            # Parse filename
            barcode, recipe_name, quantity = parse_filename(filename)
            if barcode is None:
                _move_input_file(input_file_path, failed_folder_path, "Failed", overwrite=True)
                _log_job(filename, "Failed, moved to Failed")
                continue

            # Apply multi-decoration override when present (rocks glasses .1/.2 pairs)
            override = multi_overrides.get(filename)
            if override:
                effective_barcode = override.barcode
                effective_recipe = override.recipe_name
                fixed_filename = override.fixed_filename
            else:
                effective_barcode = _strip_multi_decoration_suffix(barcode)
                effective_recipe = recipe_name
                # Ensure Fixed output also drops the .1/.2 barcode suffix if present
                if effective_barcode != barcode:
                    quantity_suffix = f"-{quantity}" if quantity is not None else ""
                    fixed_filename = f"{effective_barcode}-{effective_recipe}{quantity_suffix}.png"
                else:
                    fixed_filename = filename

            # Find config JSON
            config_json = find_config_json(effective_recipe)
            if not config_json:
                _move_input_file(input_file_path, failed_folder_path, "Failed", overwrite=True)
                _log_job(filename, "Failed, moved to Failed")
                continue

            json_file_path = config_json

            # Fix the image and get transformation matrix
            fixed_file_path = os.path.join(fixed_folder_path, fixed_filename)
            transformation_matrix = fix_image(
                input_file_path,
                effective_recipe,
                fixed_file_path,
                use_cc_input_logic=use_cc_input_logic,
            )
            _log_job(filename, "image fixed and moved to Fixed")
            file_to_send = fixed_file_path

            # Create LAP file
            quantity_suffix = f"-{quantity}" if quantity is not None else ""
            output_file_path = os.path.join(
                output_folder_path,
                f"{effective_barcode}-{effective_recipe}{quantity_suffix}.lap",
            )
            success = get_standard_lap(
                server, pass_code, device_access_code,
                file_to_send, json_file_path, output_file_path, transformation_matrix,
                log_filename=filename,
            )

            if success:
                _move_input_file(input_file_path, processed_folder_path, "Processed")
                _log_job(filename, "moved to Processed")
            else:
                _move_input_file(input_file_path, failed_folder_path, "Failed", overwrite=True)
                _log_job(filename, "Failed, moved to Failed")

            if sleep_time:
                time.sleep(sleep_time)
        except Exception:
            _move_input_file(input_file_path, failed_folder_path, "Failed", overwrite=True)
            _log_job(filename, "Failed, moved to Failed")


def get_recipe_spec_entry(recipe_name):
    """Return the full spec dict for a recipe, or None."""
    if not recipe_name:
        return None
    normalized_name = normalize_recipe_name(recipe_name)
    if not normalized_name:
        return None
    normalized_lower = normalized_name.lower()
    for key, value in RECIPE_SPECS.items():
        if key == "aliases":
            continue
        if key.lower() == normalized_lower:
            return value
    return None


def get_spec_from_recipe_name(recipe_name, spec):
    """
    Get a specific spec value from recipe specs using normalized recipe name.
    Uses EXACT match on the normalized recipe name to find the spec entry.
    """
    entry = get_recipe_spec_entry(recipe_name)
    if entry is None:
        return None
    return entry.get(spec)


def get_rotation_degrees(recipe_name):
    """
    Rotation in degrees: negative = counter-clockwise, positive = clockwise, 0 = none.
    Falls back to deprecated rotary / opensTowardsChuck when rotation is omitted.
    """
    entry = get_recipe_spec_entry(recipe_name)
    if not entry:
        return 0
    if "rotation" in entry:
        return int(entry["rotation"])
    if not entry.get("rotary"):
        return 0
    if entry.get("opensTowardsChuck"):
        return 90
    return -90


def get_mirror_y(recipe_name):
    """
    Mirror left-right (flip horizontally) when True.
    Falls back to deprecated mirrored / rotary when mirrorY is omitted.
    """
    entry = get_recipe_spec_entry(recipe_name)
    if not entry:
        return False
    if "mirrorY" in entry:
        return bool(entry["mirrorY"])
    if entry.get("rotary"):
        return False
    return not entry.get("mirrored")


def get_trim_ends(recipe_name):
    """
    Trim transparent padding from left and right edges after sizing.
    Falls back to deprecated rotary when trimEnds is omitted.
    """
    entry = get_recipe_spec_entry(recipe_name)
    if not entry:
        return False
    if "trimEnds" in entry:
        return bool(entry["trimEnds"])
    return bool(entry.get("rotary"))

# ============================================================================
# Image Processing Functions - Modular Steps
# ============================================================================

def _trim_to_content(img):
    """
    Crop image to the bounding box of non-transparent pixels (trim padding only).
    Does not encroach on real data; only removes empty edges.
    Returns the cropped image unchanged if fully transparent.
    """
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    alpha = img.split()[3]
    bbox = alpha.getbbox()
    if bbox is None:
        return img
    return img.crop(bbox)


def _trim_left_transparent(img):
    """
    Remove fully transparent columns from the LEFT side only.
    Keeps top/bottom/right whitespace intact so artboard layout is preserved,
    but eliminates leading empty pixels before real content.
    """
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    alpha = img.split()[3]
    data = np.array(alpha)  # H x W
    h, w = data.shape

    left = 0
    while left < w and np.all(data[:, left] == 0):
        left += 1

    # Nothing to trim or everything is transparent
    if left == 0 or left >= w:
        return img

    return img.crop((left, 0, w, h))


def _trim_right_transparent(img):
    """
    Remove fully transparent columns from the RIGHT side only.
    This keeps the content origin stable while preventing trailing
    empty pixels from extending the artboard width.
    """
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    alpha = img.split()[3]
    data = np.array(alpha)  # H x W
    h, w = data.shape

    right = w - 1
    while right >= 0 and np.all(data[:, right] == 0):
        right -= 1

    # Nothing to trim or everything is transparent
    if right == w - 1 or right < 0:
        return img

    return img.crop((0, 0, right + 1, h))


def _trim_solid_background(img, tolerance=10, max_foreground_fraction=0.005):
    """
    Heuristic trim for Muse/Input images that have a large solid background
    (e.g., all black) and line art in the middle.
    - Detects the dominant background color from the corners.
    - Trims rows/columns where almost all pixels match that background color.
    - Intended to remove obvious "whitespace" bands before any scaling/cropping.
    """
    if img.mode not in ("RGB", "RGBA"):
        img = img.convert("RGBA")
    elif img.mode == "RGB":
        img = img.convert("RGBA")

    data = np.array(img)  # H x W x 4
    h, w, _ = data.shape

    if h < 10 or w < 10:
        return img

    # Sample a small patch from each corner to estimate background color
    patch = 10
    corners = np.concatenate(
        [
            data[0:patch, 0:patch],
            data[0:patch, -patch:],
            data[-patch:, 0:patch],
            data[-patch:, -patch:],
        ],
        axis=0,
    )
    bg_color = corners[:, :, :3].reshape(-1, 3).mean(axis=0)

    rgb = data[:, :, :3].astype(np.float32)
    diff = np.linalg.norm(rgb - bg_color[None, None, :], axis=2)

    # A pixel is considered "foreground" if it is far from the background color
    foreground_mask = diff > tolerance

    # Trim top
    top = 0
    for y in range(h):
        frac_fg = foreground_mask[y].mean()
        if frac_fg > max_foreground_fraction:
            break
        top = y + 1

    # Trim bottom
    bottom = h
    for y in range(h - 1, -1, -1):
        frac_fg = foreground_mask[y].mean()
        if frac_fg > max_foreground_fraction:
            break
        bottom = y

    # Trim left
    left = 0
    for x in range(w):
        frac_fg = foreground_mask[:, x].mean()
        if frac_fg > max_foreground_fraction:
            break
        left = x + 1

    # Trim right
    right = w
    for x in range(w - 1, -1, -1):
        frac_fg = foreground_mask[:, x].mean()
        if frac_fg > max_foreground_fraction:
            break
        right = x

    # Ensure we don't trim everything away
    if right - left <= 0 or bottom - top <= 0:
        return img

    # If trimming removed only a negligible margin, skip to avoid surprises
    min_change = 5
    if top <= min_change and (h - bottom) <= min_change and left <= min_change and (w - right) <= min_change:
        return img

    return img.crop((left, top, right, bottom))

def sizing_and_padding(img, recipe_name):
    """
    Legacy wrapper for CC-style sizing & padding.
    Currently routes to CC Input behavior to preserve backward compatibility.
    """
    return sizing_and_padding_cc(img, recipe_name)


def sizing_and_padding_cc(img, recipe_name):
    """
    CC Input Sizing & Padding
    - Used for `Muse/CC_Input` assets.
    - Crop all existing padding, scale to artboard, then reapply padding based on
      paddingStart/paddingEnd from recipe specs.
    """
    artboard_width = get_spec_from_recipe_name(recipe_name, "artboardWidth")
    artboard_height = get_spec_from_recipe_name(recipe_name, "artboardHeight")

    if not artboard_width or not artboard_height or artboard_width <= 0 or artboard_height <= 0:
        return img

    padding_start = get_spec_from_recipe_name(recipe_name, "paddingStart")
    padding_end = get_spec_from_recipe_name(recipe_name, "paddingEnd")

    if img.mode != "RGBA":
        img = img.convert("RGBA")

    # Step 1: Trim to content only (no encroachment on real data)
    img = _trim_to_content(img)
    if img.width <= 0 or img.height <= 0:
        return img

    # Step 2: Content area and scale (padding does not affect scale)
    if padding_start is not None and padding_end is not None:
        available_height = artboard_height * (padding_end - padding_start)
        range_start_y = artboard_height * padding_start
        content_width = artboard_width
        content_height = available_height
    else:
        range_start_y = 0
        content_width = artboard_width
        content_height = artboard_height

    scale = min(content_width / img.width, content_height / img.height)
    new_width = int(round(img.width * scale))
    new_height = int(round(img.height * scale))
    img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

    # Step 3: Artboard canvas and padding (padding applied after scaling)
    padded_img = Image.new("RGBA", (artboard_width, artboard_height), (255, 255, 255, 0))
    x_offset = (artboard_width - new_width) // 2
    y_offset = int(range_start_y + (content_height - new_height) // 2)
    padded_img.paste(img, (x_offset, y_offset), img)
    return padded_img


def sizing_and_padding_input(img, recipe_name):
    """
    Muse/Input Sizing & Padding
    - Used for `Muse/Input` assets.
    - Assumes the image is already correctly padded by a technical user.
    - Only adds or removes transparent whitespace to reach the target artboard
      size; does NOT trim content or use paddingStart/paddingEnd.
    """
    artboard_width = get_spec_from_recipe_name(recipe_name, "artboardWidth")
    artboard_height = get_spec_from_recipe_name(recipe_name, "artboardHeight")

    if not artboard_width or not artboard_height or artboard_width <= 0 or artboard_height <= 0:
        return img

    if img.mode != "RGBA":
        img = img.convert("RGBA")

    # Fast path: exactly correct size
    if img.width == artboard_width and img.height == artboard_height:
        return img

    # Step 1: Try to remove obvious solid-background whitespace (top/bottom/left/right)
    trimmed = _trim_solid_background(img)
    img = trimmed

    iw, ih = img.width, img.height
    if iw <= 0 or ih <= 0:
        return img

    # Step 2: Uniformly scale (up or down) to fit within artboard while
    # preserving aspect ratio.
    scale = min(artboard_width / iw, artboard_height / ih)
    if abs(scale - 1.0) > 0.01:
        new_w = int(round(iw * scale))
        new_h = int(round(ih * scale))
        img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
        iw, ih = img.width, img.height

    # Step 3: Center on artboard canvas, padding with transparency if needed.
    canvas = Image.new("RGBA", (artboard_width, artboard_height), (255, 255, 255, 0))
    x_offset = (artboard_width - iw) // 2
    y_offset = (artboard_height - ih) // 2
    canvas.paste(img, (x_offset, y_offset), img)
    return canvas


def sizing_and_padding_cc(img, recipe_name):
    """
    CC Input Sizing & Padding (Muse/CC_Input) - NEW LOGIC
    - Incoming art is typically huge with no padding.
    - Step 1: Scale image as close as possible to the artboard while
      preserving aspect ratio (no cropping).
    - Step 2: Place on an artboard-sized canvas.
    - Step 3: If paddingStart/paddingEnd are defined, further shrink the
      content vertically so its height fits the specified vertical band
      while keeping the overall artboard resolution.
    - Step 4: Remove transparent whitespace from the LEFT edge only
      (technical IW instead of WIW).
    """
    artboard_width = get_spec_from_recipe_name(recipe_name, "artboardWidth")
    artboard_height = get_spec_from_recipe_name(recipe_name, "artboardHeight")

    if not artboard_width or not artboard_height or artboard_width <= 0 or artboard_height <= 0:
        return img

    padding_start = get_spec_from_recipe_name(recipe_name, "paddingStart")
    padding_end = get_spec_from_recipe_name(recipe_name, "paddingEnd")

    if img.mode != "RGBA":
        img = img.convert("RGBA")

    # Step 1: initial scale to fit artboard as closely as possible
    iw, ih = img.width, img.height
    if iw <= 0 or ih <= 0:
        return img

    base_scale = min(artboard_width / iw, artboard_height / ih)
    new_w = int(round(iw * base_scale))
    new_h = int(round(ih * base_scale))
    img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)

    # Optional: further vertical shrink into padding band
    if padding_start is not None and padding_end is not None:
        band_height = artboard_height * (padding_end - padding_start)
        if band_height > 0 and new_h > band_height:
            band_scale = band_height / new_h
            new_w = int(round(new_w * band_scale))
            new_h = int(round(new_h * band_scale))
            img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
        range_start_y = int(round(artboard_height * padding_start))
        content_height = band_height
    else:
        range_start_y = 0
        content_height = artboard_height

    # Step 2/3: place scaled content onto artboard canvas
    padded_img = Image.new("RGBA", (artboard_width, artboard_height), (255, 255, 255, 0))
    x_offset = (artboard_width - new_w) // 2
    y_offset = int(range_start_y + (content_height - new_h) // 2)
    padded_img.paste(img, (x_offset, y_offset), img)

    # Step 4: remove left and right transparent whitespace when trimEnds is set
    if get_trim_ends(recipe_name):
        padded_img = _trim_left_transparent(padded_img)
        padded_img = _trim_right_transparent(padded_img)
    return padded_img


def sizing_and_padding_input(img, recipe_name):
    """
    Muse/Input Sizing & Padding - NEW LOGIC
    - Incoming customer art may be at arbitrary dimensions.
    - Rule: add or remove whitespace to match the recipe artboard; if
      whitespace cannot be removed without touching real pixels, scale
      the image down to fit.
    - Uses alpha-based content trimming only (no heuristic solid-color
      guesses) and never crops real data.
    """
    artboard_width = get_spec_from_recipe_name(recipe_name, "artboardWidth")
    artboard_height = get_spec_from_recipe_name(recipe_name, "artboardHeight")

    if not artboard_width or not artboard_height or artboard_width <= 0 or artboard_height <= 0:
        return img

    if img.mode != "RGBA":
        img = img.convert("RGBA")

    # Step 1: Remove true whitespace (transparent) around content
    trimmed = _trim_to_content(img)
    img = trimmed

    iw, ih = img.width, img.height
    if iw <= 0 or ih <= 0:
        return img

    # Step 2: Decide if we need to scale.
    # If content already fits inside the artboard, keep it at native size
    # and only add whitespace. If it would overflow, scale DOWN to fit
    # while preserving aspect ratio.
    if iw <= artboard_width and ih <= artboard_height:
        scale = 1.0
    else:
        scale = min(artboard_width / iw, artboard_height / ih)

    if abs(scale - 1.0) > 0.01:
        new_w = int(round(iw * scale))
        new_h = int(round(ih * scale))
        img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
        iw, ih = img.width, img.height

    # Step 3: Center on artboard canvas, padding with transparency.
    canvas = Image.new("RGBA", (artboard_width, artboard_height), (255, 255, 255, 0))
    x_offset = (artboard_width - iw) // 2
    y_offset = (artboard_height - ih) // 2
    canvas.paste(img, (x_offset, y_offset), img)

    # Step 4: remove left and right transparent whitespace when trimEnds is set
    if get_trim_ends(recipe_name):
        canvas = _trim_left_transparent(canvas)
        canvas = _trim_right_transparent(canvas)
    return canvas


def apply_image_color_processing(img, recipe_name, contrast_reduction=50):
    """
    Function 2: Image Color Processing
    Invert the colors of the image and reduce contrast by a specified margin.
    This makes things more grey while still maintaining noticeable differences.
    
    Args:
        img: PIL Image in RGBA mode
        recipe_name: Recipe name for material-specific processing
        contrast_reduction: Amount to reduce contrast (0-255), default 50
    """
    # Ensure 4 channel mode
    if img.mode != 'RGBA':
        img = img.convert('RGBA')
    
    # Convert to numpy array
    data = np.array(img)
    r, g, b, a = data[:,:,0], data[:,:,1], data[:,:,2], data[:,:,3]
    
    # Reduce contrast (move values toward middle gray)
    # Formula: new_value = old_value + (128 - old_value) * (contrast_reduction/255)
    contrast_factor = contrast_reduction / 255.0
    r = np.clip(r + (128 - r) * contrast_factor, 0, 255).astype(np.uint8)
    g = np.clip(g + (128 - g) * contrast_factor, 0, 255).astype(np.uint8)
    b = np.clip(b + (128 - b) * contrast_factor, 0, 255).astype(np.uint8)
    
    # Invert RGB channels (preserve alpha)
    data[:,:,0] = 255 - r
    data[:,:,1] = 255 - g
    data[:,:,2] = 255 - b
    # Alpha channel remains unchanged
    
    return Image.fromarray(data, mode='RGBA')


def apply_image_metadata_manipulation(img, recipe_name):
    """
    Function 3: Image Metadata Manipulation
    Apply mirrorY (left-right flip) and rotation from recipe specs.
    rotation: degrees, negative = counter-clockwise, positive = clockwise.
    """
    if get_mirror_y(recipe_name):
        img = img.transpose(Image.FLIP_LEFT_RIGHT)

    rotation = get_rotation_degrees(recipe_name)
    if rotation:
        # PIL rotates counter-clockwise for positive angles
        img = img.rotate(-rotation, expand=True)
    return img


def get_transformation_matrix(img, recipe_name):
    """
    Function 4: Get Transformation Matrix
    Calculate the transformation matrix for positioning and scaling the image.
    Returns a 6-element list representing the transformation matrix.
    """
    transformation_matrix = [1, 0, 0, 1, 0, 0]
    
    # Get image size
    width, height = img.size
    
    # Convert px to mm (assuming 300 DPI)
    dpi = 300
    inches_per_mm = 1 / 25.4
    width_mm = width / dpi / inches_per_mm
    height_mm = height / dpi / inches_per_mm
    
    transformation_matrix[4] = width_mm / -2
    
    # Apply Y translation if specified
    y_translation = get_spec_from_recipe_name(recipe_name, "yTranslation")
    if y_translation:
        transformation_matrix[5] = y_translation
    
    # Apply X translation if specified (overrides centering)
    x_translation = get_spec_from_recipe_name(recipe_name, "xTranslation")
    if x_translation:
        transformation_matrix[4] = x_translation
    
    # Apply scaling (0.3125 = 96/300, converting from 300 DPI to 96 DPI)
    transformation_matrix[0] = 0.3125
    transformation_matrix[3] = 0.3125
    
    return transformation_matrix

def fix_image(input_path, recipe_name, fixed_file_path, use_cc_input_logic=False):
    """
    Main image fixing function that applies all processing steps sequentially.
    Returns the transformation matrix for use in LAP creation.
    """
    with Image.open(input_path) as img:
        if DO_NOTHING:
            fixed = img
            transformation_matrix = get_transformation_matrix(fixed, recipe_name)
        else:
            # Step 1: Sizing & Padding
            if use_cc_input_logic:
                # Muse/CC_Input behavior: crop all padding, then reapply recipe-based padding
                img = sizing_and_padding_cc(img, recipe_name)
            else:
                # Muse/Input behavior: only add/remove whitespace to hit artboard size
                img = sizing_and_padding_input(img, recipe_name)
            
            # Step 2: Image Color Processing
            img = apply_image_color_processing(img, recipe_name)
            
            # Step 3: Image Metadata Manipulation (rotation/flipping)
            img = apply_image_metadata_manipulation(img, recipe_name)
            
            fixed = img
            
            # Step 4: Get Transformation Matrix
            transformation_matrix = get_transformation_matrix(fixed, recipe_name)
        
        fixed.save(fixed_file_path)
        return transformation_matrix

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