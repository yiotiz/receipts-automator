# libraries to convert HEIC file to OpenCV supported file format
from PIL import Image
import pillow_heif

import cv2
import numpy as np
import matplotlib.pyplot as plt


# convert HEIC file to OpenCV format
pillow_heif.register_heif_opener()
pil_image = Image.open("input/IMG_5177.HEIC")

# convert image to pixel matrix
img = np.array(pil_image)

# 3. Convert RGB → BGR (OpenCV format)
img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)


# load image
cv2.imshow("Image", img)

cv2.waitKey(0)

cv2.destroyAllWindows()