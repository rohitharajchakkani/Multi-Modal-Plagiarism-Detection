"""
PlagiarismAI - Web Source Detection Module.
Performs:
1. Academic text query extraction with title heuristics.
2. Live search API queries (Tavily/SerpAPI).
3. OCR validation & cleaning to avoid binary artifacts.
4. Web scraping & similarity checking.
5. Source reliability and confidence classification.
"""
import os
import re
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from text_similarity import compare_texts_hybrid
from plagiarism_utils import clean_generic_sentences, is_meaningful_content

load_dotenv()


def get_search_credentials():
    """Retrieve keys and settings from environment variables."""
    tavily_key = os.environ.get('TAVILY_API_KEY')
    serpapi_key = os.environ.get('SERPAPI_KEY')
    
    # Strip template variables if they are not updated
    if tavily_key == 'your_tavily_api_key_here' or not tavily_key:
        tavily_key = None
    if serpapi_key == 'your_serpapi_key_here' or not serpapi_key:
        serpapi_key = None
        
    provider = os.environ.get('SEARCH_PROVIDER', 'tavily').lower()
    return tavily_key, serpapi_key, provider


def clean_ocr_text(text):
    """
    Remove non-printable characters, binary artifacts, and corrupted symbols.
    Keeps only alphanumeric, whitespace, and basic punctuation.
    """
    if not text:
        return ""
        
    # Keep standard ASCII printable characters: space (32) to ~ (126), and newlines/tabs
    cleaned = re.sub(r'[^\x20-\x7E\n\r\t]', '', text)
    
    # Process line-by-line to filter out blocks of garbage characters (e.g. ■■■■■, ¥ØÆY, ÒuÚ0)
    lines = cleaned.split('\n')
    valid_lines = []
    
    for line in lines:
        line_stripped = line.strip()
        if not line_stripped:
            continue
            
        # Skip lines that are just raw symbols and contain no alphabetic chars
        if not re.search(r'[a-zA-Z]', line_stripped):
            if len(line_stripped) > 2:
                continue
                
        # Filter typical OCR garbage symbols
        words = line_stripped.split()
        clean_words = []
        for w in words:
            # Skip if it is pure punctuation
            if re.match(r'^[^a-zA-Z0-9]+$', w):
                continue
            # Skip if it contains known corrupted symbols
            if any(char in w for char in '■¥ØÆÒÚ'):
                continue
            clean_words.append(w)
            
        if clean_words:
            valid_lines.append(" ".join(clean_words))
            
    return "\n".join(valid_lines)


def check_ocr_quality(text):
    """
    Check OCR quality:
    - Calculates Quality Score based on character distributions.
    - Determines if the word count is sufficient (>= 10 meaningful alphabetic words).
    Returns (quality_score, is_acceptable).
    """
    if not text or not text.strip():
        return 0, False
        
    # Count alphabetic words with length >= 2
    words = re.findall(r'\b[a-zA-Z]{2,}\b', text)
    word_count = len(words)
    
    total_chars = len(text)
    if total_chars == 0:
        return 0, False
        
    # Proportion of alphanumeric/space characters to total characters
    alphanumeric_count = sum(1 for c in text if c.isalnum() or c.isspace())
    quality_score = int((alphanumeric_count / total_chars) * 100)
    
    # Bounded between 0 and 100
    quality_score = max(0, min(100, quality_score))
    
    is_acceptable = word_count >= 10
    return quality_score, is_acceptable


def extract_paper_metadata(text):
    """
    Extract Title and Keywords from OCR output using structural heuristics.
    """
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    title = ""
    keywords = []
    
    if not lines:
        return "", []
        
    # Heuristics to find paper Title:
    # Scan the first 8 lines. Find the first line that is long enough and not a journal header
    header_keywords = ['vol.', 'no.', 'issue', 'page', 'issn', 'isbn', 'proceedings', 'journal of', 'ieee', 'acm', 'springer', 'arxiv', 'doi:', 'http']
    candidate_lines = []
    for line in lines[:8]:
        line_lower = line.lower()
        if len(line) > 15 and not any(kw in line_lower for kw in header_keywords):
            candidate_lines.append(line)
            
    if candidate_lines:
        title = candidate_lines[0]
        # Merge if the title looks truncated (short word count and doesn't end with a period)
        if len(candidate_lines) > 1 and len(title.split()) < 7:
            if not title.endswith('.') and not candidate_lines[1].endswith('.'):
                title += " " + candidate_lines[1]
    else:
        # Fallback: find first line of at least 4 words
        for line in lines[:5]:
            if len(line.split()) >= 4:
                title = line
                break
                
    # Extract keywords (e.g. Keywords: deep learning, neural networks)
    kw_match = re.search(r'(?:keywords|key\s*words|index\s*terms)\s*[:\-]\s*([^\n\.]+)', text, re.IGNORECASE)
    if kw_match:
        kw_str = kw_match.group(1)
        keywords = [k.strip() for k in re.split(r'[,;]', kw_str) if k.strip()]
        
    return title.strip(), keywords


def generate_search_queries(text):
    """
    Construct top 3-5 meaningful search queries.
    Priority:
    1. Paper Title
    2. Paper Title + top keywords
    3. Abstract keywords combination
    4. Longest meaningful sentences (fallback)
    """
    title, keywords = extract_paper_metadata(text)
    queries = []
    
    # 1. Primary Query: Paper Title (punctuation stripped for Google/Tavily search)
    if title:
        clean_title = re.sub(r'[^\w\s]', '', title)
        if len(clean_title.split()) >= 4:
            queries.append(clean_title.strip())
            
    # 2. Secondary Query: Title + Keywords
    if title and keywords:
        kw_combo = " ".join(keywords[:3])
        queries.append(f"{title} {kw_combo}".strip())
        
    # 3. Tertiary Query: Keywords + context
    if keywords:
        kw_query = " ".join(keywords[:4]) + " research paper"
        queries.append(kw_query)
        
    # 4. Fallback Query: extract longest academic sentence
    cleaned_text = clean_generic_sentences(text)
    sentences = re.split(r'(?<=[.!?])\s+', cleaned_text)
    candidate_sentences = []
    for s in sentences:
        s_clean = s.strip()
        words = s_clean.split()
        if 10 <= len(words) <= 25:
            s_clean_punc = re.sub(r'[^\w\s]', '', s_clean)
            candidate_sentences.append(s_clean_punc)
            
    candidate_sentences.sort(key=len, reverse=True)
    for cs in candidate_sentences[:2]:
        if cs not in queries:
            queries.append(cs)
            
    # De-duplicate and filter
    final_queries = []
    for q in queries:
        q_clean = q.strip()
        if q_clean and q_clean not in final_queries:
            final_queries.append(q_clean)
            
    return final_queries[:4]


def search_with_tavily(query, api_key):
    """Search using Tavily search API."""
    if not api_key:
        return []
    url = "https://api.tavily.com/search"
    payload = {
        "api_key": api_key,
        "query": query,
        "search_depth": "basic",
        "max_results": 3
    }
    try:
        response = requests.post(url, json=payload, timeout=8)
        if response.status_code == 200:
            results = response.json().get('results', [])
            return [{'url': r.get('url'), 'title': r.get('title'), 'snippet': r.get('content')} for r in results if r.get('url')]
    except Exception as e:
        print(f"[Web Search] Tavily search error: {e}")
    return []


def search_with_serpapi(query, api_key):
    """Search using SerpAPI (Google organic search)."""
    if not api_key:
        return []
    url = "https://serpapi.com/search"
    params = {
        "api_key": api_key,
        "engine": "google",
        "q": query,
        "num": 3
    }
    try:
        response = requests.get(url, params=params, timeout=8)
        if response.status_code == 200:
            organic = response.json().get('organic_results', [])
            return [{'url': r.get('link'), 'title': r.get('title'), 'snippet': r.get('snippet')} for r in organic if r.get('link')]
    except Exception as e:
        print(f"[Web Search] SerpAPI search error: {e}")
    return []


from urllib.parse import urlparse

def is_local_or_private_url(url):
    """Determine if a URL points to local, loopback, or private networks."""
    if not url:
        return True
    url_lower = url.lower()
    local_patterns = [
        r'localhost',
        r'127\.0\.0\.1',
        r'0\.0\.0\.0',
        r'192\.168\.',
        r'10\.',
        r'172\.(1[6-9]|2[0-9]|3[0-1])\.',
        r'169\.254\.'
    ]
    try:
        parsed = urlparse(url_lower)
        hostname = parsed.hostname
        if not hostname:
            return True
        if any(re.search(pat, hostname) for pat in local_patterns):
            return True
    except Exception:
        return True
    return False


def fetch_page_text(url):
    """Fetch text content from a web page using BeautifulSoup."""
    if is_local_or_private_url(url):
        print(f"[Web Search] Scraper skipped local/private URL: {url}")
        return ""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36'
    }
    try:
        response = requests.get(url, headers=headers, timeout=5)
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            # Remove scripts, headers, styles
            for script in soup(["script", "style", "nav", "footer", "header"]):
                script.decompose()
            text = soup.get_text()
            # Remove extra spacing
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            return " ".join(chunk for chunk in chunks if chunk)
    except Exception as e:
        print(f"[Web Search] Scraper failed for {url}: {e}")
    return ""


def classify_source(url):
    """Classify URL source type, reliability label, and score."""
    url_lower = url.lower()
    
    # 1. Research Papers (IEEE, ACM, Wiley, Springer, Elsevier/ScienceDirect, arXiv, Scholar, ResearchGate)
    research_domains = [
        'researchgate.net', 'scholar.google', 'springer.com', 'ieee.org', 
        'acm.org', 'elsevier.com', 'arxiv.org', 'sciencedirect.com', 
        'wiley.com', 'jstor.org', 'ncbi.nlm.nih.gov', 'doi.org'
    ]
    if any(d in url_lower for d in research_domains) or '.edu' in url_lower:
        return {
            'type': 'Research Paper',
            'reliability_label': 'Very High',
            'reliability_score': 95
        }
        
    # 2. Government websites
    gov_domains = ['.gov', '.mil', '.gov.in', '.gov.uk', '.go.jp', '.gov.au']
    if any(d in url_lower for d in gov_domains):
        return {
            'type': 'Government Website',
            'reliability_label': 'Very High',
            'reliability_score': 95
        }
        
    # 3. Wikipedia
    if 'wikipedia.org' in url_lower:
        return {
            'type': 'Wikipedia',
            'reliability_label': 'High',
            'reliability_score': 85
        }
        
    # 4. Educational websites
    edu_domains = ['britannica.com', 'coursera.org', 'khanacademy.org', 'udemy.com', 'edx.org', 'quizlet.com', 'chegg.com']
    if any(d in url_lower for d in edu_domains):
        return {
            'type': 'Educational Website',
            'reliability_label': 'High',
            'reliability_score': 85
        }
        
    # 5. News websites
    news_domains = ['news.', 'cnn.com', 'bbc.co.uk', 'bbc.com', 'reuters.com', 'nytimes.com', 'theguardian.com', 'washingtonpost.com', 'bloomberg.com']
    if any(d in url_lower for d in news_domains):
        return {
            'type': 'News Website',
            'reliability_label': 'Medium',
            'reliability_score': 60
        }
        
    # 6. Default blogs / portals
    return {
        'type': 'Blog/Other',
        'reliability_label': 'Medium',
        'reliability_score': 50
    }


def run_web_source_detection(raw_text):
    """
    Executes the full web detection pipeline.
    Strips binary characters, performs quality checks, generates queries, and searches.
    """
    tavily_key, serpapi_key, provider = get_search_credentials()
    
    # API Key check
    if provider == 'tavily' and not tavily_key:
        return {'error': 'Web search API key is missing. Please add your API key in the .env file.'}
    if provider == 'serpapi' and not serpapi_key:
        return {'error': 'Web search API key is missing. Please add your API key in the .env file.'}

    # 0. Early exit if raw text is empty or unreadable
    if not raw_text or not raw_text.strip():
        return {
            'error': 'No readable text detected. Please upload a clearer poster, infographic, handwritten note, or scanned document.',
            'low_quality': True,
            'ocr_quality_score': 0
        }
        
    # 1. OCR text sanitization (stripping corrupted binary glyphs)
    cleaned_text = clean_ocr_text(raw_text)
    
    # 2. OCR Quality Validation check
    quality_score, is_acceptable = check_ocr_quality(cleaned_text)
    if not is_acceptable:
        return {
            'error': 'OCR quality too low for reliable source detection.',
            'low_quality': True,
            'ocr_quality_score': quality_score
        }
        
    # 3. Generate Search Queries (Title, Keywords prioritized)
    queries = generate_search_queries(cleaned_text)
    title, keywords = extract_paper_metadata(cleaned_text)
    
    if not queries:
        return {
            'error': 'Not enough meaningful content to create search queries.',
            'not_enough_content': True,
            'ocr_quality_score': quality_score
        }

    # 4. Search live web sources
    raw_results = []
    for q in queries:
        if provider == 'tavily':
            raw_results.extend(search_with_tavily(q, tavily_key))
        else:
            raw_results.extend(search_with_serpapi(q, serpapi_key))

    # De-duplicate URL entries
    seen_urls = set()
    unique_results = []
    for r in raw_results:
        url = r.get('url')
        if url not in seen_urls:
            seen_urls.add(url)
            unique_results.append(r)

    # 5. Scrape, compare similarity and classify reliability
    web_matches = []
    for r in unique_results:
        url = r['url']
        source_title = r['title']
        snippet = r['snippet'] or ""
        
        # Crawl actual website body text
        page_text = fetch_page_text(url)
        compare_target = page_text if len(page_text) > 100 else snippet
        
        if not compare_target:
            continue
            
        comp = compare_texts_hybrid(cleaned_text, compare_target)
        similarity = comp['overall_score']
        
        if similarity < 10.0:
            continue
            
        classification = classify_source(url)
        confidence = round(min(100.0, similarity * 1.05), 2)
        
        from plagiarism_utils import get_plagiarism_level
        plag_level = get_plagiarism_level(similarity)['label']
        
        web_matches.append({
            'url': url,
            'title': source_title,
            'snippet': snippet[:300] + ('...' if len(snippet) > 300 else ''),
            'similarity_score': similarity,
            'source_type': classification['type'],
            'reliability_label': classification['reliability_label'],
            'reliability_score': classification['reliability_score'],
            'confidence_score': confidence,
            'plagiarism_level': plag_level
        })

    # Sort descending
    web_matches.sort(key=lambda x: x['similarity_score'], reverse=True)
    
    return {
        'matches': web_matches,
        'ocr_quality_score': quality_score,
        'extracted_title': title,
        'extracted_keywords': keywords,
        'generated_queries': queries
    }
