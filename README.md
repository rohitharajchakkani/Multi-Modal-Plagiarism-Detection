# Multi-Modal Plagiarism Detection System

A modern, full-stack academic web application that detects plagiarism in **text** and **source code** using three levels of analysis.

## Features

- **Text Comparison** — TF-IDF vectorization + cosine similarity with NLTK preprocessing
- **Token-Based Comparison** — Code tokenization with Jaccard, sequence, and n-gram similarity
- **AST Structural Comparison** — Abstract Syntax Tree analysis for Python code
- **Dashboard** — Real-time statistics and quick navigation
- **History** — Searchable, filterable history with pagination
- **Reports** — Detailed, printable comparison reports
- **Admin Panel** — System overview and database management

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Backend | Python 3, Flask |
| Frontend | HTML5, CSS3, JavaScript |
| Database | SQLite |
| ML/NLP | scikit-learn, NLTK |
| Design | Glassmorphism, Dark Theme |

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Download NLTK data
python -c "import nltk; nltk.download('punkt_tab'); nltk.download('stopwords')"

# 3. Run the application
python app.py
```

## Project Structure

```
plagiarism model/
├── app.py                  # Flask application (all routes)
├── config.py               # Configuration settings
├── database.py             # SQLite database operations
├── schema.sql              # Database schema
├── requirements.txt        # Python dependencies
├── engine/                 # Plagiarism detection engines
│   ├── text_comparison.py  # TF-IDF + cosine similarity
│   ├── token_comparison.py # Token-based comparison
│   └── ast_comparison.py   # AST structural comparison
├── templates/              # Jinja2 HTML templates
│   ├── base.html, landing.html, select_mode.html,
│   ├── text_compare.html, code_compare.html,
│   ├── result.html, dashboard.html, history.html,
│   ├── report.html, admin.html, about.html
└── static/
    ├── css/style.css       # Glassmorphism design system
    └── js/main.js          # Frontend interactions
```

## Pages

| Page | URL | Description |
|------|-----|-------------|
| Landing | `/` | Hero page with feature cards |
| Select Mode | `/select` | Choose text or code comparison |
| Text Compare | `/text-compare` | Enter two text passages |
| Code Compare | `/code-compare` | Enter two code snippets |
| Result | `/result/<id>` | Animated plagiarism meter |
| Dashboard | `/dashboard` | Statistics overview |
| History | `/history` | Past comparisons table |
| Report | `/report/<id>` | Detailed printable report |
| Admin | `/admin` | System management |
| About | `/about` | Project documentation |
