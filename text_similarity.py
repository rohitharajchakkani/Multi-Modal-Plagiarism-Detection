"""
PlagiarismAI - Text Similarity Engine.
Computes:
1. TF-IDF Cosine Similarity (40% weight)
2. Bag-of-Words Cosine Similarity (30% weight)
3. Semantic Similarity using sentence-transformers (30% weight)
"""
import string
import re
from difflib import SequenceMatcher
from sklearn.feature_extraction.text import TfidfVectorizer, CountVectorizer
from sklearn.metrics.pairwise import cosine_similarity
# Proper noun filtering is configured via NLTK pos tagging in plagiarism_utils

try:
    import nltk
    from nltk.corpus import stopwords
    from nltk.tokenize import word_tokenize
    NLTK_AVAILABLE = True
except ImportError:
    NLTK_AVAILABLE = False

try:
    from sentence_transformers import SentenceTransformer, util
    import torch
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False

# Global cached model
_semantic_model = None


def get_semantic_model():
    """Load and cache the sentence-transformers model."""
    global _semantic_model
    if _semantic_model is None:
        if SENTENCE_TRANSFORMERS_AVAILABLE:
            try:
                # Load with CPU default to handle non-CUDA environments
                _semantic_model = SentenceTransformer('all-MiniLM-L6-v2', device='cpu')
            except Exception as e:
                print(f"[Similarity] Warning: Failed to load SentenceTransformer: {e}")
                _semantic_model = None
    return _semantic_model


def ensure_nltk_data():
    """Download required NLTK datasets."""
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


def clean_text_for_vectorization(text):
    """
    Standard preprocessing: lowercase, remove punctuation, remove English stopwords,
    ignore short words.
    """
    if not text or not text.strip():
        return ""
    
    text = text.lower()
    # Translate punctuation to spaces to keep word boundaries
    text = text.translate(str.maketrans(string.punctuation, ' ' * len(string.punctuation)))
    # Reduce whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    
    if NLTK_AVAILABLE:
        ensure_nltk_data()
        try:
            tokens = word_tokenize(text)
            stop_words = set(stopwords.words('english'))
            # Filter proper nouns (NNP/NNPS) if desired, but here we just do stopwords and short words
            tagged = nltk.pos_tag(tokens)
            filtered = [w for w, tag in tagged if w not in stop_words and len(w) > 1 and tag not in ('NNP', 'NNPS')]
            return " ".join(filtered)
        except Exception:
            pass
            
    # Fallback basic stop words list
    basic_stops = {'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had',
                   'do', 'does', 'did', 'will', 'would', 'should', 'to', 'of', 'in', 'for', 'on', 'with', 'at',
                   'by', 'from', 'it', 'this', 'that', 'and', 'or', 'but', 'not', 'if', 'then', 'so', 'as'}
    tokens = text.split()
    filtered = [t for t in tokens if t not in basic_stops and len(t) > 1]
    return " ".join(filtered)


def compute_tfidf_similarity(clean1, clean2):
    """Compute TF-IDF cosine similarity."""
    if not clean1 or not clean2:
        return 0.0
    try:
        vectorizer = TfidfVectorizer()
        tfidf = vectorizer.fit_transform([clean1, clean2])
        sim = cosine_similarity(tfidf[0:1], tfidf[1:2])[0][0]
        return round(float(sim) * 100, 2)
    except Exception:
        # Fallback: simple intersection of words
        w1 = set(clean1.split())
        w2 = set(clean2.split())
        if not w1 or not w2:
            return 0.0
        return round((len(w1 & w2) / len(w1 | w2)) * 100, 2)


def compute_bow_similarity(clean1, clean2):
    """Compute CountVectorizer (Bag-of-Words) cosine similarity."""
    if not clean1 or not clean2:
        return 0.0
    try:
        vectorizer = CountVectorizer()
        bow = vectorizer.fit_transform([clean1, clean2])
        sim = cosine_similarity(bow[0:1], bow[1:2])[0][0]
        return round(float(sim) * 100, 2)
    except Exception:
        # Fallback: token ratio match
        match = SequenceMatcher(None, clean1.split(), clean2.split()).ratio()
        return round(match * 100, 2)


def compute_semantic_similarity(text1, text2):
    """
    Compute semantic similarity using sentence-transformers (all-MiniLM-L6-v2).
    Falls back to difflib sequence matching if not available.
    """
    if not text1 or not text2:
        return 0.0
        
    model = get_semantic_model()
    if model:
        try:
            # Encode sentences
            emb1 = model.encode(text1, convert_to_tensor=True)
            emb2 = model.encode(text2, convert_to_tensor=True)
            # Compute cosine similarity
            cos_sim = util.cos_sim(emb1, emb2).item()
            # Clip between 0 and 1
            cos_sim = max(0.0, min(1.0, cos_sim))
            return round(cos_sim * 100, 2)
        except Exception as e:
            print(f"[Semantic Similarity] Error running model: {e}")
            
    # Fallback: difflib SequenceMatcher on original text (captures paraphrased structures to an extent)
    matcher = SequenceMatcher(None, text1.lower(), text2.lower())
    return round(matcher.ratio() * 100, 2)


def check_paraphrasing_and_exact(text1, text2):
    """
    Calculate auxiliary metrics:
    - Exact Matches: percentage of identical word sequences.
    - Paraphrased Content: estimated similarity of non-verbatim overlaps.
    - Unique Content: remaining original content percentage.
    """
    matcher = SequenceMatcher(None, text1.lower().split(), text2.lower().split())
    matching_blocks = matcher.get_matching_blocks()
    
    total_words1 = len(text1.split())
    if total_words1 == 0:
        return 0.0, 0.0, 100.0
        
    exact_words = sum(block.size for block in matching_blocks)
    exact_percentage = round((exact_words / total_words1) * 100, 2)
    
    # Estimate paraphrasing based on structural similarity minus exact matches
    # If structural sequence matcher is high but words aren't identical, it indicates paraphrased sentences
    semantic_score = compute_semantic_similarity(text1, text2)
    
    # If exact matches are high, paraphrased content is low
    # Paraphrased is the semantic similarity that represents rewritten blocks
    paraphrased_percentage = round(max(0.0, semantic_score - exact_percentage), 2)
    
    # Ensure percentages add up logically
    unique_percentage = round(max(0.0, 100.0 - exact_percentage - paraphrased_percentage), 2)
    
    return exact_percentage, paraphrased_percentage, unique_percentage


def compare_texts_hybrid(text1, text2):
    """
    Main entry point for text comparison.
    Calculates final similarity score as:
      40% TF-IDF + 30% Cosine (BoW) + 30% Semantic
    """
    clean1 = clean_text_for_vectorization(text1)
    clean2 = clean_text_for_vectorization(text2)
    
    tfidf_score = compute_tfidf_similarity(clean1, clean2)
    bow_score = compute_bow_similarity(clean1, clean2)
    semantic_score = compute_semantic_similarity(text1, text2)
    
    final_score = round(
        (0.40 * tfidf_score) +
        (0.30 * bow_score) +
        (0.30 * semantic_score),
        2
    )
    
    exact_matches, paraphrased, unique = check_paraphrasing_and_exact(text1, text2)
    
    # Determine the used method description
    method_str = "Hybrid (TF-IDF + Cosine + SentenceTransformers)"
    if not get_semantic_model():
        method_str = "Hybrid (TF-IDF + Cosine + SequenceMatcher Fallback)"
        
    return {
        'overall_score': final_score,
        'method': method_str,
        'breakdown': {
            'tfidf_similarity': tfidf_score,
            'cosine_similarity': bow_score,
            'semantic_similarity': semantic_score
        },
        'analytics': {
            'exact_matches': exact_matches,
            'paraphrased_content': paraphrased,
            'unique_content': unique
        },
        'preprocessed_text1': clean1,
        'preprocessed_text2': clean2
    }
