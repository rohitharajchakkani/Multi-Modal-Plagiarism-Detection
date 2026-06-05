"""
OCR Engine for PlagiarismAI.
Uses pytesseract to extract text from images and PyMuPDF to render PDFs into images for page-by-page OCR.
"""
import os
import cv2
import numpy as np

try:
    import pytesseract
    PYTESSERACT_AVAILABLE = True
except ImportError:
    PYTESSERACT_AVAILABLE = False

try:
    import fitz  # PyMuPDF
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False

# Ensure tesseract path is set on Windows if installed in default path
if os.name == 'nt' and PYTESSERACT_AVAILABLE:
    tesseract_path = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
    if os.path.exists(tesseract_path):
        pytesseract.pytesseract.tesseract_cmd = tesseract_path


def preprocess_image_for_ocr(image):
    """
    Advanced OpenCV Preprocessing Pipeline for Tesseract OCR:
    1. Grayscale
    2. Adaptive Resize (upscale low resolution images)
    3. Denoising using Median Blur
    4. Contrast Enhancement (CLAHE)
    5. Binarization (Otsu's Thresholding)
    """
    if image is None:
        return None
        
    # 1. Grayscale
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    
    # 2. Adaptive Resize: upscale image if it is too small for character recognition
    h, w = gray.shape[:2]
    if w < 1500 or h < 1500:
        scale = max(1500.0 / w, 1500.0 / h)
        gray = cv2.resize(gray, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_CUBIC)
        
    # 3. Denoise with Median Blur (removes minor salt/pepper noise while preserving text strokes)
    denoised = cv2.medianBlur(gray, 3)
    
    # 4. Enhance Contrast using CLAHE
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(denoised)
    
    # 5. Binarization using Otsu's Thresholding
    _, thresh = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    
    return thresh


def extract_text_from_image(image_path):
    """
    Extract text from an image file after running it through the preprocessing pipeline.
    """
    if not PYTESSERACT_AVAILABLE:
        return "Error: pytesseract is not installed."
        
    try:
        # Read the image using OpenCV with Unicode file path compatibility
        image = cv2.imdecode(np.fromfile(image_path, dtype=np.uint8), cv2.IMREAD_COLOR)
        if image is None:
            return "Error: Could not read image file."
            
        processed_img = preprocess_image_for_ocr(image)
        
        # Run Tesseract OCR on the processed image
        custom_config = r'--oem 3 --psm 6'
        text = pytesseract.image_to_string(processed_img, config=custom_config)
        return text
    except Exception as e:
        return f"OCR Error: {str(e)}"


def extract_text_from_pdf(pdf_path):
    """
    Convert every page of the PDF into a high-res image first,
    then apply image preprocessing and run OCR on every page.
    Combines the extracted text page-by-page.
    """
    if not PYMUPDF_AVAILABLE:
        return "Error: PyMuPDF (fitz) is not installed."
    if not PYTESSERACT_AVAILABLE:
        return "Error: pytesseract is not installed."
        
    try:
        doc = fitz.open(pdf_path)
        full_text = []
        
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            
            # Render page to a high-res image (2x zoom factor)
            zoom = 2
            mat = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=mat, dpi=150)
            img_data = pix.tobytes("png")
            
            # Load into OpenCV
            nparr = np.frombuffer(img_data, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            # Preprocess
            processed_img = preprocess_image_for_ocr(img)
            
            # Extract text
            custom_config = r'--oem 3 --psm 6'
            page_text = pytesseract.image_to_string(processed_img, config=custom_config)
            full_text.append(page_text)
            
        return "\n".join(full_text)
    except Exception as e:
        return f"PDF OCR Error: {str(e)}"


def extract_text_from_file(file_path):
    """
    Route extraction based on extension. Images and PDFs are run through OCR.
    """
    if not os.path.exists(file_path):
        return f"Error: File does not exist at {file_path}"
        
    ext = file_path.lower().split('.')[-1]
    
    if ext == 'pdf':
        return extract_text_from_pdf(file_path)
    elif ext in ['jpg', 'jpeg', 'png', 'bmp', 'tiff']:
        return extract_text_from_image(file_path)
    else:
        return f"Error: Unsupported visual file type: {ext}"
