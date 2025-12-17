from datetime import timedelta
import os
from decouple import config

class Config:
    SECRET_KEY = config('SECRET_KEY')
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(days=7)
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    SUPABASE_DB_USER = config('SUPABASE_DB_USER')
    SUPABASE_DB_PASSWORD = config('SUPABASE_DB_PASSWORD')
    SUPABASE_DB_HOST = config('SUPABASE_DB_HOST')
    SUPABASE_DB_PORT = config('SUPABASE_DB_PORT', cast=int)
    SUPABASE_DB_NAME = config('SUPABASE_DB_NAME')

    SQLALCHEMY_DATABASE_URI = (
        f"postgresql+psycopg2://{SUPABASE_DB_USER}:"
        f"{SUPABASE_DB_PASSWORD}@{SUPABASE_DB_HOST}:"
        f"{SUPABASE_DB_PORT}/{SUPABASE_DB_NAME}"
    )

    SUPABASE_URL = config('SUPABASE_URL')
    SUPABASE_KEY = config('SUPABASE_KEY')
    SUPABASE_BUCKET = config('SUPABASE_BUCKET', default='captured-faces')
    
    # Maileroo SMTP settings
    MAILERO_API_KEY = config('MAILERO_API_KEY', default='your-mailero-api-key')
    MAILERO_SENDER = config('MAILERO_SENDER', default='no-reply@yourdomain.com')
    
    # Africa's Talking settings
    AT_USERNAME = config('AT_USERNAME')
    AT_API_KEY = config('AT_API_KEY')
    AT_VIRTUAL_NUMBER = config('AT_VIRTUAL_NUMBER')
    OWNER_PHONE_NUMBER = config('OWNER_PHONE_NUMBER')
    BASE_URL = config('BASE_URL')
    
    # Push notification webhook (e.g., Firebase or custom service)
    PUSH_WEBHOOK_URL = config('PUSH_WEBHOOK_URL', default='https://your-push-service.com/webhook')
    
    # Notification toggles
    EMAIL_ENABLED = config('EMAIL_ENABLED', default=True, cast=bool)
    PUSH_ENABLED = config('PUSH_ENABLED', default=True, cast=bool)
    CALL_ENABLED = config('CALL_ENABLED', default=False, cast=bool)

    KNOWN_FACES_DIR = config('KNOWN_FACES_DIR')
    MODEL_NAME = config('MODEL_NAME')
    UNKNOWN_LABEL = config('UNKNOWN_LABEL')
    RECOGNITION_THRESHOLD = config('RECOGNITION_THRESHOLD', cast=float)
    CONFIDENCE_THRESHOLD = config('CONFIDENCE_THRESHOLD', cast=float)