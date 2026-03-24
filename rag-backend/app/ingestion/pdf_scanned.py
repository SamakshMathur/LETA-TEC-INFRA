import pytesseract
import fitz  # PyMuPDF
import cv2
import numpy as np
from PIL import Image
import os
import io

# Set Tesseract Path (Common Default on Windows)
# If not found in PATH, check this location
possible_tesseract_path = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
if os.path.exists(possible_tesseract_path):
    pytesseract.pytesseract.tesseract_cmd = possible_tesseract_path

# Fallback or check if in PATH (usually winget adds it, but env var might need refresh)
# We rely on the above check or system PATH.

def remove_stamps(image):
    """
    Detects and removes colored stamps (Red, Blue, Purple) from the image using OpenCV.
    Converts PIL Image to OpenCV format, processes it, and returns a PIL Image.
    """
    # Convert PIL Image to OpenCV format (RGB -> BGR)
    open_cv_image = np.array(image)
    if open_cv_image.ndim == 2: # Grayscale
        open_cv_image = cv2.cvtColor(open_cv_image, cv2.COLOR_GRAY2BGR)
    else:
        open_cv_image = open_cv_image[:, :, ::-1].copy()

    # Convert to HSV color space for better color segmentation
    hsv = cv2.cvtColor(open_cv_image, cv2.COLOR_BGR2HSV)

    # Define color ranges for common stamp inks
    # Red (wraps around 0/180)
    lower_red1 = np.array([0, 70, 50])
    upper_red1 = np.array([10, 255, 255])
    lower_red2 = np.array([170, 70, 50])
    upper_red2 = np.array([180, 255, 255])

    # Blue
    lower_blue = np.array([90, 50, 50])
    upper_blue = np.array([130, 255, 255])

    # Purple/Violet
    lower_purple = np.array([120, 50, 50])
    upper_purple = np.array([160, 255, 255])

    # Create masks
    mask_red1 = cv2.inRange(hsv, lower_red1, upper_red1)
    mask_red2 = cv2.inRange(hsv, lower_red2, upper_red2)
    mask_blue = cv2.inRange(hsv, lower_blue, upper_blue)
    mask_purple = cv2.inRange(hsv, lower_purple, upper_purple)

    # Combine all masks
    mask = mask_red1 + mask_red2 + mask_blue + mask_purple

    # Dilate mask slightly to cover edges of the stamp
    kernel = np.ones((5, 5), np.uint8)
    mask = cv2.dilate(mask, kernel, iterations=1)

    # Inpaint the stamped area (remove stamp and fill with background)
    # NS stands for Navier-Stokes based method
    result = cv2.inpaint(open_cv_image, mask, 3, cv2.INPAINT_NS)

    # Convert back to RGB for PIL
    result = cv2.cvtColor(result, cv2.COLOR_BGR2RGB)
    return Image.fromarray(result)

def preprocess_image(image):
    """
    Applies noise reduction and thresholding to improve OCR accuracy.
    """
    # Convert to grayscale
    gray = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2GRAY)

    # Denoise (remove small specks)
    denoised = cv2.fastNlMeansDenoising(gray, h=10, templateWindowSize=7, searchWindowSize=21)

    # Adaptive Thresholding (good for varying lighting/shadows)
    # Creates a binary image (black text on white background)
    thresh = cv2.adaptiveThreshold(
        denoised, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
    )

    return Image.fromarray(thresh)

def extract_text_from_scanned_pdf(path):
    """
    Uses PyMuPDF (fitz) to rasterize PDF pages to images, then runs Tesseract OCR.
    Replaces pdf2image to avoid Poppler dependency.
    """
    doc = fitz.open(path)
    pages = []

    # Iterate over pages
    for page_num, page in enumerate(doc):
        # 300 DPI is usually sufficient for OCR. matrix(2,2) ~ 144 DPI (72*2).
        # We want higher quality as requested. matrix(4,4) ~ 288 DPI.
        mat = fitz.Matrix(4, 4) 
        pix = page.get_pixmap(matrix=mat)
        
        # Convert PyMuPDF Pixmap to PIL Image
        img_data = pix.tobytes("png")
        image = Image.open(io.BytesIO(img_data))
        
        # 1. Remove Stamps first (while still in color)
        clean_image = remove_stamps(image)
        
        # 2. Preprocess for OCR (Grayscale, Thresholding)
        final_image = preprocess_image(clean_image)

        # 3. OCR with better page segmentation for legal text
        try:
            text = pytesseract.image_to_string(
                final_image,
                lang="eng",
                config="--psm 3 --oem 3 -c preserve_interword_spaces=1"
            )
        except pytesseract.TesseractNotFoundError:
             print("Tesseract not found! Please ensure Tesseract-OCR is installed and in PATH.")
             text = ""
        except Exception as e:
            print(f"OCR Error on page {page_num+1}: {e}")
            text = ""

        pages.append({
            "text": text.strip() or "[OCR_EMPTY_PAGE]",
            "metadata": {
                "source": str(path),
                "page": page_num + 1,
                "type": "pdf_scanned_ocr_advanced"
            }
        })

    return pages

def extract_text_from_image(file_bytes: bytes) -> str:
    """
    Uses Tesseract OCR to extract text directly from image bytes,
    re-using the advanced stamp removal and preprocessing logic.
    """
    try:
        image = Image.open(io.BytesIO(file_bytes))
        
        # Convert to RGB if it has an Alpha channel or is grayscale
        if image.mode != 'RGB':
            image = image.convert('RGB')
            
        # 1. Remove Stamps first (while still in color)
        clean_image = remove_stamps(image)
        
        # 2. Preprocess for OCR (Grayscale, Thresholding)
        final_image = preprocess_image(clean_image)

        # 3. OCR with page segmentation for text
        text = pytesseract.image_to_string(
            final_image,
            lang="eng",
            config="--psm 3 --oem 3 -c preserve_interword_spaces=1"
        )
        return text.strip() or "[OCR_EMPTY_IMAGE]"
        
    except pytesseract.TesseractNotFoundError:
        print("Tesseract not found! Please ensure Tesseract-OCR is installed and in PATH.")
        return ""
    except Exception as e:
        print(f"Image OCR Error: {e}")
        return ""
