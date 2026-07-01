# libraries to convert HEIC file to OpenCV supported file format
import os
import time
import smtplib
from email.message import EmailMessage
from pathlib import Path

from dotenv import load_dotenv
from PIL import Image
import PIL.JpegImagePlugin
import pillow_heif

import cv2
import numpy as np

pillow_heif.register_heif_opener()

# --- Email settings ---
# Credentials are loaded from a .env file in the same folder as this


load_dotenv()

SENDER_EMAIL = os.environ.get("SENDER_EMAIL")
SENDER_PASSWORD = os.environ.get("SENDER_PASSWORD")
RECIPIENT_EMAIL = os.environ.get("RECIPIENT_EMAIL")
EMAIL_PROVIDER = os.environ.get("EMAIL_PROVIDER", "gmail").lower()

if not all([SENDER_EMAIL, SENDER_PASSWORD, RECIPIENT_EMAIL, EMAIL_PROVIDER]):
    raise ValueError(
        "Missing email settings. Make sure you have a .env file with "
        "SENDER_EMAIL, SENDER_PASSWORD, RECIPIENT_EMAIL and EMAIL_PROVIDER set."
    )

EMAIL_SUBJECT = "Receipt"
DELAY_BETWEEN_EMAILS_SECONDS = 5

INPUT_DIR = Path("input")
OUTPUT_DIR = Path("output")
FAILED_DIR = Path("failed")

# Create the folders if they don't already exist, so the script
# doesn't crash the first time it's run on a fresh setup.
OUTPUT_DIR.mkdir(exist_ok=True)
FAILED_DIR.mkdir(exist_ok=True)

SUPPORTED_EXTENSIONS = [".heic", ".jpg", ".jpeg", ".png"]


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


def process_receipt(file_path: Path) -> Path:
    """
    Takes a single receipt photo, finds its edges, straightens it,
    and saves the result as a PDF in the output folder.

    Returns the path of the saved PDF.
    Raises an exception if anything goes wrong, so the caller can
    decide what to do with the failure (this function doesn't catch
    its own errors — that's handled in the main loop below).
    """
    pil_image = Image.open(file_path)

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

    contours, hierarchy = cv2.findContours(canny, cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)
    page = sorted(contours, key=cv2.contourArea, reverse=True)[:5]

    # find 4 corners of receipt
    corners = None
    for eps_factor in [0.02, 0.03, 0.04, 0.05, 0.06, 0.08, 0.10]:
        for c in page:
            peri = cv2.arcLength(c, True)
            epsilon = eps_factor * peri
            approx = cv2.approxPolyDP(c, epsilon, True)
            if len(approx) == 4:
                corners = approx
                break
        if corners is not None:
            break

    if corners is None:
        raise ValueError(f"Could not find a 4-point contour for {file_path.name}")

    # Flatten corners from shape (4, 1, 2) to a plain list of [x, y] pairs,
    # then sort into top-left, top-right, bottom-right, bottom-left order.
    corners_flat = np.concatenate(corners).tolist()
    ordered_corners = order_points(corners_flat)

    # finding the destination coordinates
    (tl, tr, br, bl) = ordered_corners

    widthA = np.sqrt(((br[0] - bl[0]) ** 2) + ((br[1] - bl[1]) ** 2))
    widthB = np.sqrt(((tr[0] - tl[0]) ** 2) + ((tr[1] - tl[1]) ** 2))
    maxWidth = max(int(widthA), int(widthB))

    heightA = np.sqrt(((tr[0] - br[0]) ** 2) + ((tr[1] - br[1]) ** 2))
    heightB = np.sqrt(((tl[0] - bl[0]) ** 2) + ((tl[1] - bl[1]) ** 2))
    maxHeight = max(int(heightA), int(heightB))

    destination_corners = [[0, 0], [maxWidth, 0], [maxWidth, maxHeight], [0, maxHeight]]

    # perspective transform - warp the original clean pixels, since
    # corners were found on the processed gray/edge version, but the
    # final scan should come from the unprocessed photo.
    matrix = cv2.getPerspectiveTransform(
        np.float32(ordered_corners),
        np.float32(destination_corners)
    )
    warped = cv2.warpPerspective(orig_img, matrix, (maxWidth, maxHeight), flags=cv2.INTER_LINEAR)

    # shows images for debugging
    # cv2.imshow("Edges", canny)
    # cv2.imshow("Warped", warped)
    # cv2.waitKey(0)
    # cv2.destroyAllWindows()

    # get warped photo and convert it back to pillow format, then save as PDF
    warped_rgb = cv2.cvtColor(warped, cv2.COLOR_BGR2RGB)
    pil_warped = Image.fromarray(warped_rgb)

    output_path = OUTPUT_DIR / f"{file_path.stem}.pdf"
    pil_warped.save(output_path)

    return output_path


def send_receipt_email(pdf_path: Path):
    """
    Sends a single PDF as an email attachment to the configured
    recipient. Raises an exception if anything goes wrong, so the
    caller can decide how to handle the failure — same pattern as
    process_receipt().
    """
    if not SENDER_PASSWORD:
        raise ValueError("No app password found in .env - cannot send email.")

    # Build the email message: who it's from, who it's to, the
    # subject line, and a short body.
    msg = EmailMessage()
    msg["From"] = SENDER_EMAIL
    msg["To"] = RECIPIENT_EMAIL
    msg["Subject"] = EMAIL_SUBJECT
    msg.set_content(f"Attached: {pdf_path.name}")

    # Read the PDF file as raw bytes and attach it to the email.
    with open(pdf_path, "rb") as f:
        pdf_bytes = f.read()

    msg.add_attachment(
        pdf_bytes,
        maintype="application",
        subtype="pdf",
        filename=pdf_path.name,
    )

    if EMAIL_PROVIDER == "outlook":
        # Outlook uses port 587 with STARTTLS - connects unencrypted
        # then upgrades to encrypted after the initial handshake.
        with smtplib.SMTP("smtp.office365.com", 587) as smtp:
            smtp.starttls()
            smtp.login(SENDER_EMAIL, SENDER_PASSWORD)
            smtp.send_message(msg)
    else:
        # Gmail uses port 465 with SSL - encrypted from
        # the start of the connection. Requires an App Password,
        # not your normal Gmail password.
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(SENDER_EMAIL, SENDER_PASSWORD)
            smtp.send_message(msg)


# --- Main loop: go through every file in the input folder ---

processed_count = 0
failed_count = 0
emailed_count = 0
email_failed_count = 0

for file_path in sorted(INPUT_DIR.iterdir()):
    if file_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        continue  # skip anything that isn't an image we support

    print(f"Processing: {file_path.name}")

    try:
        output_path = process_receipt(file_path)
        print(f"  Saved: {output_path.name}")
        processed_count += 1

        # Now try to email the PDF we just created.
        try:
            send_receipt_email(output_path)
            print(f"  Emailed: {output_path.name}")
            emailed_count += 1
        except Exception as email_error:
            # The PDF itself was created fine — only the email failed.
            # We don't move the original photo to failed/ in this case,
            # since the scan succeeded; we just log the email problem.
            print(f"  Email failed: {email_error}")
            email_failed_count += 1

        # Wait a few seconds before the next email, so we don't send
        # a burst of emails in a row and risk being rate-limited.
        time.sleep(DELAY_BETWEEN_EMAILS_SECONDS)

    except Exception as e:
        # Something went wrong with this one file - log it and move
        # the original photo into the failed folder, but keep going
        # rather than stopping the whole batch.
        print(f"  Failed: {e}")
        failed_count += 1

        failed_path = FAILED_DIR / file_path.name
        file_path.rename(failed_path)

print(f"\nDone. Processed: {processed_count}, Failed: {failed_count}, "
      f"Emailed: {emailed_count}, Email failures: {email_failed_count}")