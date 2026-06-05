"""
PlagiarismAI - Visual Similarity Engine.
Computes:
1. OCR Text Similarity (40% weight)
2. Layout Similarity (30% weight) - Canny edge correlation
3. Image Hash Similarity (20% weight) - dHash Hamming distance
4. Color Similarity (10% weight) - HSV histogram correlation
"""
import os
import cv2
import numpy as np

try:
    import fitz  # PyMuPDF
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False

from engine.ocr_engine import extract_text_from_file
from text_similarity import compare_texts_hybrid


def load_image_from_file(file_path):
    """
    Load an image from a file path. If it's a PDF, render the first page as an image.
    Returns OpenCV image array or None if loading fails.
    """
    if not os.path.exists(file_path):
        return None
        
    ext = file_path.lower().split('.')[-1]
    
    if ext == 'pdf':
        if not PYMUPDF_AVAILABLE:
            return None
        try:
            doc = fitz.open(file_path)
            if len(doc) == 0:
                return None
            # Render first page
            page = doc[0]
            pix = page.get_pixmap(dpi=150)
            img_data = pix.tobytes("png")
            nparr = np.frombuffer(img_data, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            return img
        except Exception as e:
            print(f"[Visual] Error rendering PDF page: {e}")
            return None
    else:
        try:
            # Read Unicode file path support with numpy
            img = cv2.imdecode(np.fromfile(file_path, dtype=np.uint8), cv2.IMREAD_COLOR)
            return img
        except Exception as e:
            print(f"[Visual] Error reading image file: {e}")
            return None


def compute_layout_similarity(img1, img2):
    """
    Compute layout structure similarity using resized Canny edge map cross-correlation.
    """
    try:
        # Resize to standard size
        size = (256, 256)
        g1 = cv2.resize(cv2.cvtColor(img1, cv2.COLOR_BGR2GRAY), size)
        g2 = cv2.resize(cv2.cvtColor(img2, cv2.COLOR_BGR2GRAY), size)
        
        # Detect edges
        edges1 = cv2.Canny(g1, 50, 150)
        edges2 = cv2.Canny(g2, 50, 150)
        
        # Calculate cross correlation of edge maps
        result = cv2.matchTemplate(edges1, edges2, cv2.TM_CCOEFF_NORMED)
        similarity = max(0.0, float(result[0][0])) * 100
        return round(similarity, 2)
    except Exception as e:
        print(f"[Visual] Layout Similarity error: {e}")
        return 0.0


def compute_dhash(image, hash_size=8):
    """Compute difference hash (dHash) of an image."""
    try:
        # Resize to (hash_size + 1, hash_size) to look at horizontal differences
        gray = cv2.resize(cv2.cvtColor(image, cv2.COLOR_BGR2GRAY), (hash_size + 1, hash_size))
        # Compute differences between adjacent columns
        diff = gray[:, 1:] > gray[:, :-1]
        return diff
    except Exception:
        return None


def compute_hash_similarity(img1, img2):
    """Compute image similarity based on dHash Hamming distance."""
    h1 = compute_dhash(img1)
    h2 = compute_dhash(img2)
    
    if h1 is None or h2 is None:
        return 0.0
        
    # Count differences
    mismatches = np.count_nonzero(h1 != h2)
    total_bits = h1.size
    
    # Calculate similarity percentage
    similarity = (1.0 - (mismatches / total_bits)) * 100
    return round(similarity, 2)


def compute_color_similarity(img1, img2):
    """Compute color distribution similarity in HSV space using histogram correlation."""
    try:
        hsv1 = cv2.cvtColor(img1, cv2.COLOR_BGR2HSV)
        hsv2 = cv2.cvtColor(img2, cv2.COLOR_BGR2HSV)
        
        # Compute 2D Hue-Saturation histogram
        hist1 = cv2.calcHist([hsv1], [0, 1], None, [50, 60], [0, 180, 0, 256])
        hist2 = cv2.calcHist([hsv2], [0, 1], None, [50, 60], [0, 180, 0, 256])
        
        # Normalize histograms
        cv2.normalize(hist1, hist1, 0, 1, cv2.NORM_MINMAX)
        cv2.normalize(hist2, hist2, 0, 1, cv2.NORM_MINMAX)
        
        # Calculate correlation index (-1 to 1)
        correlation = cv2.compareHist(hist1, hist2, cv2.HISTCMP_CORREL)
        
        # Map from [-1, 1] range to [0, 100] similarity
        similarity = max(0.0, correlation) * 100
        return round(similarity, 2)
    except Exception as e:
        print(f"[Visual] Color Similarity error: {e}")
        return 0.0


def compare_visual_documents(path1, path2):
    """
    Main pipeline for comparing two visual documents:
    OCR text similarity (40%) + Layout (30%) + Hash similarity (20%) + Color (10%)
    """
    # 1. OCR text extraction & similarity
    txt1 = extract_text_from_file(path1)
    txt2 = extract_text_from_file(path2)
    
    # Run text analysis
    text_results = compare_texts_hybrid(txt1, txt2)
    ocr_sim = text_results['overall_score']
    
    # 2. Image loading for CV metrics
    img1 = load_image_from_file(path1)
    img2 = load_image_from_file(path2)
    
    if img1 is None or img2 is None:
        # If OpenCV fail, return OCR similarity as full score with a warning
        return {
            'overall_score': ocr_sim,
            'breakdown': {
                'ocr_text_similarity': ocr_sim,
                'layout_similarity': 0.0,
                'visual_hash_similarity': 0.0,
                'color_similarity': 0.0
            },
            'ocr_text1': txt1,
            'ocr_text2': txt2,
            'warning': "Failed to render images. Calculation falls back entirely to OCR text comparison."
        }
        
    layout_sim = compute_layout_similarity(img1, img2)
    hash_sim = compute_hash_similarity(img1, img2)
    color_sim = compute_color_similarity(img1, img2)
    
    # Combined score
    final_score = round(
        (0.40 * ocr_sim) +
        (0.30 * layout_sim) +
        (0.20 * hash_sim) +
        (0.10 * color_sim),
        2
    )
    
    return {
        'overall_score': final_score,
        'breakdown': {
            'ocr_text_similarity': ocr_sim,
            'layout_similarity': layout_sim,
            'visual_hash_similarity': hash_sim,
            'color_similarity': color_sim
        },
        'ocr_text1': txt1,
        'ocr_text2': txt2
    }
