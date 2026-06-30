# libraries to convert HEIC file to OpenCV supported file format
from PIL import Image
import pillow_heif

import cv2
import numpy as np


def order_points(pts):
    # rearrange coordinates to order:
    # top-left, top-right, bottom-right, bottom-left
    rect = np.zeros((4, 2), dtype='float32')
    pts = np.array(pts)
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]
    rect[2] = pts[np.argmax(s)]

    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)]
    rect[3] = pts[np.argmax(diff)]
    return rect.astype('int').tolist()


# convert HEIC file to OpenCV format
pillow_heif.register_heif_opener()
pil_image = Image.open("input/IMG_6423.HEIC")

img = np.array(pil_image)
img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)

# Keep the clean original to warp at the end.
orig_img = img.copy()

# edge detection directly on the original photo
gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
gray = cv2.GaussianBlur(gray, (5, 5), 0)

# scans image and finds spot where brightness changes, hence edge
canny = cv2.Canny(gray, 50, 150)
canny = cv2.dilate(canny, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)), iterations=2)

con = np.zeros_like(img)
contours, hierarchy = cv2.findContours(canny, cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)
page = sorted(contours, key=cv2.contourArea, reverse=True)[:5]


for i, dc in enumerate(page):
    area = cv2.contourArea(dc)
    peri = cv2.arcLength(dc, True)
    approx = cv2.approxPolyDP(dc, 0.02 * peri, True)
    print(f"Contour {i}: area={area:.0f}, points={len(approx)}")


# find 4 corners of receipt
corners = None
winning_contour = None
for eps_factor in [0.02, 0.03, 0.04, 0.05, 0.06, 0.08, 0.10]:
    for c in page:
        peri = cv2.arcLength(c, True)
        epsilon = eps_factor * peri
        approx = cv2.approxPolyDP(c, epsilon, True)
        if len(approx) == 4:
            corners = approx
            winning_contour = c
            break
    if corners is not None:
        break

if corners is None:
    raise ValueError("Could not find a 4-point contour for the receipt.")

cv2.drawContours(con, winning_contour, -1, (0, 255, 255), 3)
cv2.drawContours(con, corners, -1, (0, 255, 0), 10)

# Flatten corners from shape (4, 1, 2) to a plain list of [x, y] pairs,
# then sort into top-left, top-right, bottom-right, bottom-left order.
corners_flat = np.concatenate(corners).tolist()
ordered_corners = order_points(corners_flat)

for index, c_point in enumerate(ordered_corners):
    character = chr(65 + index)
    cv2.putText(con, character, tuple(c_point), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 0, 0), 1, cv2.LINE_AA)

# finding the destination coordinates
# This part already generalizes to any receipt length, since maxWidth/
# maxHeight are computed from the actual detected corners each time.
(tl, tr, br, bl) = ordered_corners

widthA = np.sqrt(((br[0] - bl[0]) ** 2) + ((br[1] - bl[1]) ** 2))
widthB = np.sqrt(((tr[0] - tl[0]) ** 2) + ((tr[1] - tl[1]) ** 2))
maxWidth = max(int(widthA), int(widthB))

heightA = np.sqrt(((tr[0] - br[0]) ** 2) + ((tr[1] - br[1]) ** 2))
heightB = np.sqrt(((tl[0] - bl[0]) ** 2) + ((tl[1] - bl[1]) ** 2))
maxHeight = max(int(heightA), int(heightB))

destination_corners = [[0, 0], [maxWidth, 0], [maxWidth, maxHeight], [0, maxHeight]]

# perspective transform
# we warp orig_img corners
# were found on the processed gray/edge version, but the final scan
# should come from the original clean pixels.
matrix = cv2.getPerspectiveTransform(
    np.float32(ordered_corners),
    np.float32(destination_corners)
)
warped = cv2.warpPerspective(orig_img, matrix, (maxWidth, maxHeight), flags=cv2.INTER_LINEAR)

# cv2.imshow("Original", orig_img)
# cv2.imshow("Edges", canny)
# cv2.imshow("Contours", con)
cv2.imshow("Warped", warped)

cv2.waitKey(0)
cv2.destroyAllWindows()