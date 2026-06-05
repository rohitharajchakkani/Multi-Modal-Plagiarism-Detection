-- Schema for the Plagiarism Detection System database
-- This file is executed by database.py to initialize tables.

CREATE TABLE IF NOT EXISTS comparisons (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    comparison_type TEXT NOT NULL,          -- 'text' or 'handwritten'
    input1_preview TEXT,                    -- First 200 chars of input 1
    input2_preview TEXT,                    -- First 200 chars of input 2
    input1_full TEXT,                       -- Full input 1 content
    input2_full TEXT,                       -- Full input 2 content
    similarity_score REAL NOT NULL,         -- Overall similarity percentage (0-100)
    method_used TEXT NOT NULL,              -- 'tfidf_cosine', 'token', 'ast', 'combined'
    result_category TEXT,                   -- 'Low Similarity', 'Moderate Similarity', 'High Plagiarism Detected'
    detailed_results TEXT,                  -- JSON string with method-level breakdown
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    email TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS comparison_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    comparison_type TEXT NOT NULL,          -- 'text', 'visual', 'web_text', 'web_visual'
    mode_used TEXT NOT NULL,                -- 'local' or 'web'
    file_names TEXT,                        -- Comma-separated or JSON list of file names
    input1_preview TEXT,
    input2_preview TEXT,
    input1_full TEXT,
    input2_full TEXT,
    similarity_score REAL NOT NULL,
    plagiarism_level TEXT NOT NULL,         -- 'No Plagiarism', 'Low Plagiarism', etc.
    method_used TEXT,
    detailed_results TEXT,                  -- JSON string with details/breakdowns
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS web_source_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    comparison_id INTEGER,
    source_url TEXT NOT NULL,
    source_title TEXT,
    matched_snippet TEXT,
    similarity_score REAL,
    source_type TEXT,                       -- 'Research Paper', 'Government Website', etc.
    reliability_score INTEGER,
    confidence_score REAL,
    plagiarism_level TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(comparison_id) REFERENCES comparison_history(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    message TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT 'info',  -- 'info', 'warning', 'success'
    is_read INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);
