"""Preview helpers: resize + base64 JPEG for WebSocket emit."""

import base64
import io

import PIL
from PIL import Image


def pilimTobase64Jpg(pilim):
    """Convert a PIL image to a base64-encoded JPEG string."""
    b = io.BytesIO()
    pilim.save(b, format="JPEG")
    data = b.getvalue()
    return base64.b64encode(data).decode("utf-8")


if int(PIL.Image.__version__[0]) <= 5:

    def resizeImage(image: Image, newresol, resample=PIL.Image.NEAREST, reducing_gap=1.0):
        return image.resize(newresol, resample=resample)

else:

    def resizeImage(image: Image, newresol, resample=PIL.Image.NEAREST, reducing_gap=1.0):
        return image.resize(newresol, resample=resample, reducing_gap=reducing_gap)
