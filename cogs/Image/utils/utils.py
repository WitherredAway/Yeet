import io
import re
from typing import Tuple, Optional, Union

from PIL import Image

from cogs.Image.utils.constants import ASPECT_RATIO_ORIGINAL


def resize(
    file: io.BytesIO,
    *,
    height: int,
    width: int,
    crop: Optional[bool] = False,
) -> Tuple[bytes, Tuple[int]]:
    att_image = Image.open(file)
    img_width, img_height = att_image.size

    if crop is True:
        image = Image.new("RGBA", (width, height), (0, 0, 0, 0))

        offset = (
            (image.size[0] - img_width) // 2,
            (image.size[1] - img_height) // 2,
        )
        image.paste(att_image, offset)
    else:
        image = att_image.resize((width, height), Image.ANTIALIAS)

    with io.BytesIO() as image_bytes:
        image.save(image_bytes, "PNG")
        return image_bytes.getvalue(), image.size


def center_resize(
    file: io.BytesIO,
    *,
    height: int,
    width: int,
    crop: Optional[bool] = None,
) -> Tuple[bytes, Tuple[int]]:
    new_size = (width, height)
    img = Image.open(file)
    original_size = img.size

    # Calculate the new size of the image while maintaining its aspect ratio
    width_ratio = new_size[0] / original_size[0]
    height_ratio = new_size[1] / original_size[1]
    ratio = min(width_ratio, height_ratio)
    new_width = int(original_size[0] * ratio)
    new_height = int(original_size[1] * ratio)

    # Resize the image only if crop is not true
    if crop is not True:
        img = img.resize((new_width, new_height), Image.ANTIALIAS)

    # Create a new image with the desired size and paste the resized image on top
    final_img = Image.new("RGBA", new_size, (255, 255, 255, 0))
    x = int((new_size[0] - new_width) / 2)
    y = int((new_size[1] - new_height) / 2)
    final_img.paste(img, (x, y))

    with io.BytesIO() as img_bytes:
        final_img.save(img_bytes, "PNG")
        return img_bytes.getvalue(), final_img.size


def fit_image(file: io.BytesIO) -> bytes:
    img = Image.open(file)
    bbox = img.getbbox()
    img = img.crop(bbox)

    with io.BytesIO() as image_bytes:
        img.save(image_bytes, "PNG")
        return image_bytes.getvalue(), img.size
