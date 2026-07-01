1. Opens photo from input folder (HEIC, JPG, PNG), conerts image into pixel matrix for OpenCV. A copy of image is made for final product.
2. Prepare for edge detection - image is converted to greyscale.
3. Edges of receipt are found by looking where there is an abrupt brightness change.
4. Receipt outlines are found by looking at all white edge pixels and grouped into closed outline, largest area is kept as that will be receipt.
5. Outline is a bit bumpy so outline is simplified by ginoring small bumps.
6. Corners are ordered using math (top-left has the smallest x+y sum, bottom-right has the largest, etc)
7. Photo is straightened using perspective transform.
8. Photo is saved as PDF and emailed
