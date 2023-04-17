import io
from typing import Tuple, Optional
from PIL import Image



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
        image = att_image.resize((width, height))

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
    att_image = Image.open(file)
    if crop is not True:
        h_issmall = height <= att_image.size[1]
        w_issmall = width <= att_image.size[0]
        if h_issmall and w_issmall:
            with io.BytesIO() as file:
                att_image.save(file, "PNG")
                return resize(file=file, height=height, width=width, crop=crop)
        elif h_issmall:
            att_image = Image.open(
                io.BytesIO(
                    resize(file, height=height, width=att_image.size[0])
                )
            )
        elif w_issmall:
            att_image = Image.open(
                io.BytesIO(resize(file, height=att_image.size[1], width=width))
            )
    img_width, img_height = att_image.size

    bg_image = Image.new("RGBA", (width, height), (0, 0, 0, 0))

    offset = (
        (bg_image.size[0] - img_width) // 2,
        (bg_image.size[1] - img_height) // 2,
    )
    bg_image.paste(att_image, offset)
    with io.BytesIO() as image_bytes:
        bg_image.save(image_bytes, "PNG")
        return image_bytes.getvalue(), bg_image.size


def fit_image(file: io.BytesIO, *, crop: Optional[bool] = False) -> bytes:
    img = Image.open(file)
    og_size = img.size
    bbox = img.getbbox()
    img = img.crop(bbox)

    if crop is not True:
        image = Image.new("RGBA", og_size, (0, 0, 0, 0))

        offset = (
            (image.width - img.width) // 2,
            (image.height - img.height) // 2,
        )
        image.paste(img, offset)
        img = image

    with io.BytesIO() as image_bytes:
        img.save(image_bytes, "PNG")
        return image_bytes.getvalue(), img.size