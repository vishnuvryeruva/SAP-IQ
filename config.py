"""
Configuration Module for SAP Assistant
Centralizes all configuration settings for the application
"""

import os
from dotenv import load_dotenv

# Load environment variables from .env file if present
load_dotenv()

# OpenAI API Configuration
# Priority: 1. Environment variable 2. Fallback to hardcoded (for development only)
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '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')
OPENAI_ASSISTANT_ID = os.getenv('OPENAI_ASSISTANT_ID', 'asst_D8x26bB9HstXP5EaqiI5ejaX')

# Application Settings
APP_SECRET_KEY = os.getenv('APP_SECRET_KEY', 'your_secret_key')  # Change in production
DEBUG_MODE = os.getenv('DEBUG_MODE', 'True').lower() == 'true'
PORT = int(os.getenv('PORT', 5000))

# File Upload Settings
UPLOAD_FOLDER = os.getenv('UPLOAD_FOLDER', 'uploads')
STATIC_FOLDER = os.getenv('STATIC_FOLDER', 'static')
MAX_CONTENT_LENGTH = int(os.getenv('MAX_CONTENT_LENGTH', 16 * 1024 * 1024))  # 16MB default
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'doc', 'docx'}
ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'svg'}

# AWS Configuration (if applicable)
AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID', '')
AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY', '')
AWS_REGION = os.getenv('AWS_REGION', 'us-east-1')
S3_BUCKET_NAME = os.getenv('S3_BUCKET_NAME', '')

# Conversation Settings
CONVERSATION_LENGTH = int(os.getenv('CONVERSATION_LENGTH', 10))

# Create required folders
def ensure_directories():
    """Ensure that required directories exist"""
    for folder in [UPLOAD_FOLDER, STATIC_FOLDER]:
        if not os.path.exists(folder):
            os.makedirs(folder)
