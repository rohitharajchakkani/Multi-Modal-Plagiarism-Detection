"""
PlagiarismAI - Helper utilities for text classification, false positive prevention, and scoring.
"""
import re

try:
    import nltk
    from nltk.corpus import stopwords
    from nltk.tokenize import word_tokenize
    NLTK_AVAILABLE = True
except ImportError:
    NLTK_AVAILABLE = False


def ensure_nltk_data():
    """Ensure that required NLTK resources are downloaded."""
    if NLTK_AVAILABLE:
        try:
            nltk.data.find('tokenizers/punkt_tab')
        except LookupError:
            nltk.download('punkt_tab', quiet=True)
        try:
            nltk.data.find('corpora/stopwords')
        except LookupError:
            nltk.download('stopwords', quiet=True)
        try:
            nltk.data.find('taggers/averaged_perceptron_tagger')
        except LookupError:
            nltk.download('averaged_perceptron_tagger', quiet=True)
        try:
            nltk.data.find('taggers/averaged_perceptron_tagger_eng')
        except LookupError:
            nltk.download('averaged_perceptron_tagger_eng', quiet=True)


def get_plagiarism_level(score):
    """
    Get the plagiarism level description, color code, and explanation based on score thresholds:
    0-20%: Green (No Plagiarism)
    21-40%: Yellow (Low Plagiarism)
    41-60%: Orange (Moderate Plagiarism)
    61-100%: Red (High Plagiarism)
    """
    score = float(score)
    if score <= 20:
        return {
            'label': 'No Plagiarism',
            'color': '#2ecc71', # Green
            'class': 'success',
            'explanation': 'The document shows negligible similarity to matched sources. This is typically considered original content.'
        }
    elif score <= 40:
        return {
            'label': 'Low Plagiarism',
            'color': '#f1c40f', # Yellow
            'class': 'warning-low',
            'explanation': 'Some common phrases or minor overlaps detected. Likely standard references or coincidental matching.'
        }
    elif score <= 60:
        return {
            'label': 'Moderate Plagiarism',
            'color': '#e67e22', # Orange
            'class': 'warning-mod',
            'explanation': 'Significant parts of the text match external sources. Paraphrasing or citations may be lacking.'
        }
    else:
        return {
            'label': 'High Plagiarism',
            'color': '#e74c3c', # Red
            'class': 'danger',
            'explanation': 'Extensive matches detected across multiple sections. High probability of verbatim copying or copy-paste plagiarism.'
        }


def clean_generic_sentences(text):
    """
    Remove generic sentences like "My name is Vaishnavi" or "My name is Jaya".
    """
    if not text:
        return ""
    
    # Split text into sentences
    sentences = re.split(r'(?<=[.!?])\s+', text)
    cleaned_sentences = []
    
    # Regular expressions for common name/intro phrases
    intro_patterns = [
        r'\bmy\s+name\s+is\s+[a-zA-Z\s]+',
        r'\bi\s+am\s+[a-zA-Z\s]+',
        r'\bthis\s+is\s+[a-zA-Z\s]+(?:\'s)?\s+(?:assignment|homework|project)',
        r'\bsubmitted\s+by\s+[a-zA-Z\s]+',
        r'\broll\s+number\s+\d+',
        r'\bstudent\s+id\s+\d+'
    ]
    
    for s in sentences:
        is_generic = False
        s_lower = s.lower().strip()
        for pattern in intro_patterns:
            if re.search(pattern, s_lower):
                is_generic = True
                break
        
        # Also filter out extremely short sentences (less than 3 words)
        if len(s_lower.split()) < 3:
            is_generic = True
            
        if not is_generic:
            cleaned_sentences.append(s)
            
    return " ".join(cleaned_sentences)


def is_meaningful_content(text, min_tokens=5):
    """
    Validates if the text contains a minimum amount of meaningful content (tokens).
    Returns (bool, message).
    """
    if not text or not text.strip():
        return False, "Document is empty."
        
    cleaned = clean_generic_sentences(text)
    words = cleaned.split()
    
    if len(words) < min_tokens:
        return False, "Not enough meaningful content for plagiarism detection."
        
    return True, ""


def filter_proper_nouns(text):
    """
    Extract proper nouns using POS tagging so they can be optionally ignored or filtered.
    """
    if not text or not NLTK_AVAILABLE:
        return text
        
    ensure_nltk_data()
    try:
        tokens = word_tokenize(text)
        tagged = nltk.pos_tag(tokens)
        
        # Remove words tagged as NNP (Proper Noun Singular) or NNPS (Proper Noun Plural)
        filtered = [word for word, tag in tagged if tag not in ('NNP', 'NNPS')]
        return " ".join(filtered)
    except Exception:
        return text
