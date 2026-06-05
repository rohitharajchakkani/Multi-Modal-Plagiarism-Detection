"""
Text-Based Plagiarism Comparison Engine.
Uses TF-IDF vectorization + cosine similarity, plus difflib sequence matching.
"""
import re
import string
from difflib import SequenceMatcher

# Try to import sklearn and nltk; provide fallbacks if not available
try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

try:
    import nltk
    from nltk.corpus import stopwords
    from nltk.tokenize import word_tokenize
    NLTK_AVAILABLE = True
except ImportError:
    NLTK_AVAILABLE = False


def ensure_nltk_data():
    """Download required NLTK data if not already present."""
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


def preprocess_text(text):
    """
    Preprocess text for comparison:
    1. Convert to lowercase
    2. Remove punctuation
    3. Tokenize into words
    4. Remove stopwords
    5. Rejoin into cleaned string

    Args:
        text: Raw input text string

    Returns:
        Cleaned text string ready for comparison
    """
    if not text or not text.strip():
        return ''

    # Lowercase
    text = text.lower()

    # Remove punctuation
    text = text.translate(str.maketrans('', '', string.punctuation))

    # Remove extra whitespace
    text = re.sub(r'\s+', ' ', text).strip()

    if NLTK_AVAILABLE:
        ensure_nltk_data()
        try:
            # Tokenize
            tokens = word_tokenize(text)
            
            # POS tagging to identify proper nouns (names/entities)
            pos_tags = nltk.pos_tag(tokens)
            
            # Filter out stopwords, short words, and proper nouns (NNP, NNPS)
            stop_words = set(stopwords.words('english'))
            filtered_tokens = []
            for word, tag in pos_tags:
                if word not in stop_words and len(word) > 1 and tag not in ('NNP', 'NNPS'):
                    filtered_tokens.append(word)
            
            return ' '.join(filtered_tokens)
        except Exception:
            # Fallback to simple splitting if NLTK fails
            pass

    # Simple fallback: split on whitespace and remove short words
    common_stopwords = {'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been',
                        'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will',
                        'would', 'could', 'should', 'may', 'might', 'can', 'shall',
                        'to', 'of', 'in', 'for', 'on', 'with', 'at', 'by', 'from',
                        'it', 'this', 'that', 'these', 'those', 'and', 'or', 'but',
                        'not', 'no', 'if', 'then', 'so', 'as', 'up', 'out', 'about'}
    tokens = text.split()
    tokens = [t for t in tokens if t not in common_stopwords and len(t) > 1]
    return ' '.join(tokens)


def compute_tfidf_similarity(text1, text2):
    """
    Compute similarity between two texts using TF-IDF + cosine similarity.

    Args:
        text1: First preprocessed text
        text2: Second preprocessed text

    Returns:
        Similarity score as a float between 0 and 100
    """
    if not text1 or not text2:
        return 0.0

    if text1 == text2:
        return 100.0

    if SKLEARN_AVAILABLE:
        try:
            vectorizer = TfidfVectorizer()
            tfidf_matrix = vectorizer.fit_transform([text1, text2])
            similarity = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])[0][0]
            return round(similarity * 100, 2)
        except Exception:
            pass

    # Fallback: simple word overlap (Jaccard similarity)
    words1 = set(text1.split())
    words2 = set(text2.split())
    if not words1 and not words2:
        return 0.0
    intersection = words1 & words2
    union = words1 | words2
    return round((len(intersection) / len(union)) * 100, 2) if union else 0.0


def compute_difflib_similarity(text1, text2):
    """
    Compute similarity using Python's difflib SequenceMatcher.
    This catches reordered and partially matching sequences.

    Args:
        text1: First text string
        text2: Second text string

    Returns:
        Similarity score as a float between 0 and 100
    """
    if not text1 or not text2:
        return 0.0

    if text1 == text2:
        return 100.0

    ratio = SequenceMatcher(None, text1, text2).ratio()
    return round(ratio * 100, 2)


def get_result_category(score):
    """
    Categorize the similarity score with realistic thresholds.

    Args:
        score: Similarity percentage (0-100)

    Returns:
        Category string
    """
    if score >= 61:
        return 'High Plagiarism Detected'
    elif score >= 41:
        return 'Moderate Plagiarism'
    elif score >= 21:
        return 'Slight Similarity'
    else:
        return 'No Plagiarism Detected / Common Text'


def analyze_text(text1, text2):
    """
    Run full text comparison pipeline.

    Steps:
    1. Preprocess both texts
    2. Compute TF-IDF cosine similarity
    3. Compute difflib sequence similarity
    4. Average both scores for overall result
    5. Categorize the result

    Args:
        text1: Raw first text input
        text2: Raw second text input

    Returns:
        Dictionary with overall score, category, and method breakdown
    """
    # Preprocess
    clean1 = preprocess_text(text1)
    clean2 = preprocess_text(text2)

    # Minimum Content Rule: check if preprocessed text has enough meaningful content
    MIN_WORDS = 5
    if len(clean1.split()) < MIN_WORDS or len(clean2.split()) < MIN_WORDS:
        return {
            'overall_score': 0.0,
            'category': 'Not enough meaningful content for plagiarism detection',
            'method': 'n/a',
            'breakdown': {
                'tfidf_cosine': 0.0,
                'sequence_matching': 0.0,
            },
            'preprocessed_text1': clean1,
            'preprocessed_text2': clean2,
        }

    # Compute similarities
    tfidf_score = compute_tfidf_similarity(clean1, clean2)
    difflib_score = compute_difflib_similarity(text1.lower(), text2.lower())

    # Overall score: weighted average (TF-IDF is more robust, give it more weight)
    overall_score = round((tfidf_score * 0.6) + (difflib_score * 0.4), 2)

    # Categorize
    category = get_result_category(overall_score)

    return {
        'overall_score': overall_score,
        'category': category,
        'method': 'tfidf_cosine',
        'breakdown': {
            'tfidf_cosine': tfidf_score,
            'sequence_matching': difflib_score,
        },
        'preprocessed_text1': clean1,
        'preprocessed_text2': clean2,
    }
