import os
import re
from dataclasses import dataclass
from typing import Dict, Iterable, Optional, Tuple

from PIL import Image


_MULTI_DECORATION_RE = re.compile(r"^(?P<barcode>\d+)\.(?P<idx>[12])-(?P<rest>.+)\.png$", re.IGNORECASE)


@dataclass(frozen=True)
class MultiDecorationOverride:
    """
    Override values for a single input filename, without mutating the source file.
    """
    barcode: str
    recipe_name: str
    fixed_filename: str


def _aspect_ratio(width: int, height: int) -> float:
    if width <= 0 or height <= 0:
        return float("inf")
    a = max(width, height) / min(width, height)
    return a


def _load_image_size(path: str) -> Optional[Tuple[int, int]]:
    try:
        with Image.open(path) as img:
            return img.size
    except Exception:
        return None


def _replace_barcode_and_recipe(filename: str, new_barcode: str, new_recipe: str) -> str:
    """
    Preserves any trailing quantity suffix like '-1' and preserves extension.
    Example:
      1234567-candlePosh8White-1.png -> 7234567-glassRocksBottom-1.png
    """
    name = os.path.basename(filename)
    if not name.lower().endswith(".png"):
        return filename

    stem = name[:-4]
    parts = stem.split("-")
    if len(parts) < 2:
        return f"{new_barcode}-{new_recipe}.png"

    # If last part is an int, treat it as quantity and keep it.
    quantity_suffix = ""
    try:
        int(parts[-1])
        quantity_suffix = f"-{parts[-1]}"
    except ValueError:
        quantity_suffix = ""

    return f"{new_barcode}-{new_recipe}{quantity_suffix}.png"


def _barcode_without_decoration_suffix(barcode_with_suffix: str) -> str:
    # 1234567.1 -> 1234567
    if "." not in barcode_with_suffix:
        return barcode_with_suffix
    left, right = barcode_with_suffix.rsplit(".", 1)
    if right in ("1", "2") and left.isdigit():
        return left
    return barcode_with_suffix


def _barcode_with_first_digit_set(barcode: str, first_digit: str = "7") -> str:
    if not barcode:
        return barcode
    return f"{first_digit}{barcode[1:]}"


def build_overrides_for_multi_decoration(
    folder_path: str,
    png_filenames: Iterable[str],
    *,
    bottom_recipe: str = "glassRocksBottom",
    side_recipe: str = "glassRocksLaser",
) -> Dict[str, MultiDecorationOverride]:
    """
    Detect multi-decoration method orders (barcode like 1234567.1 / 1234567.2).

    Rules:
    - Group .1/.2 pairs that share the same base filename excluding the .1/.2 suffix.
    - Choose the image that is "more square" (aspect ratio closer to 1) as the bottom engraving:
        - recipe -> glassRocksBottom
        - remove .1/.2 from barcode
        - set first digit of barcode to 7
    - The other image is side engraving:
        - recipe -> glassRocksLaser
        - remove .1/.2 from barcode
    - If dimensions can't be read or aspect ratios are identical, pick the first file encountered as bottom.
    - If a file matches the .1/.2 pattern but has no pair, no override is produced (it will be
      handled by the normal pipeline).
    """
    filenames = [f for f in png_filenames if isinstance(f, str) and f.lower().endswith(".png")]

    # Map normalized key -> list of filenames (where normalized removes ".1"/".2" just after barcode digits)
    key_to_files: Dict[str, list[str]] = {}
    matches: Dict[str, re.Match] = {}

    for fn in filenames:
        m = _MULTI_DECORATION_RE.match(os.path.basename(fn))
        if not m:
            continue
        matches[fn] = m
        key = f"{m.group('barcode')}-{m.group('rest').lower()}"
        key_to_files.setdefault(key, []).append(fn)

    overrides: Dict[str, MultiDecorationOverride] = {}

    # First handle paired keys
    for key, fns in key_to_files.items():
        if len(fns) < 2:
            continue

        # Deterministic ordering: .1 before .2, then name
        def _sort_key(x: str) -> Tuple[int, str]:
            mm = matches.get(x)
            idx = int(mm.group("idx")) if mm else 99
            return (idx, x.lower())

        fns_sorted = sorted(fns, key=_sort_key)
        a, b = fns_sorted[0], fns_sorted[1]

        a_size = _load_image_size(os.path.join(folder_path, a))
        b_size = _load_image_size(os.path.join(folder_path, b))

        a_ratio = _aspect_ratio(*(a_size or (0, 0)))
        b_ratio = _aspect_ratio(*(b_size or (0, 0)))

        bottom_fn, side_fn = (a, b) if a_ratio <= b_ratio else (b, a)

        # Base barcode is digits before ".1"/".2"
        base_barcode = matches[bottom_fn].group("barcode")
        bottom_barcode = _barcode_with_first_digit_set(base_barcode, "7")
        side_barcode = base_barcode

        overrides[bottom_fn] = MultiDecorationOverride(
            barcode=bottom_barcode,
            recipe_name=bottom_recipe,
            fixed_filename=_replace_barcode_and_recipe(bottom_fn, bottom_barcode, bottom_recipe),
        )
        overrides[side_fn] = MultiDecorationOverride(
            barcode=side_barcode,
            recipe_name=side_recipe,
            fixed_filename=_replace_barcode_and_recipe(side_fn, side_barcode, side_recipe),
        )

    return overrides

