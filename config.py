"""
Configuration settings for the Plagiarism Detection System.
"""
import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

# Flask settings
SECRET_KEY = os.environ.get('SECRET_KEY', 'plagiarism-detector-secret-key-2024')
DEBUG = True

# Database settings
DATABASE_PATH = os.path.join(BASE_DIR, 'plagiarism.db')
SCHEMA_PATH = os.path.join(BASE_DIR, 'schema.sql')

# Application settings
MAX_INPUT_LENGTH = 50000  # Maximum characters per input
PREVIEW_LENGTH = 200      # Characters to store as preview
