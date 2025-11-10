# config/settings.py - UPDATED FOR NEW ACCOUNT & AIVEN

import os
import logging

logger = logging.getLogger(__name__)

class Config:
    # Aiven MySQL Database Configuration
    DB_SERVER = "mysql-dhanish2468-a3a0.j.aivencloud.com"
    DB_PORT = "20138"
    DB_USER = "avnadmin"
    DB_PASSWORD = os.getenv('DB_PASSWORD', '')    
    DEFAULT_DATABASES = ["healthcare", "ecommerce"]  # Aiven databases
    # System databases to exclude
    MYSQL_SYSTEM_DATABASES = ["information_schema", "mysql", "performance_schema", "sys"]
    SQLSERVER_SYSTEM_DATABASES = ["master", "tempdb", "model", "msdb"]
    
    # New Google Cloud Project Details
    GCP_PROJECT = os.getenv('GOOGLE_CLOUD_PROJECT', 'top-caldron-477810-k3')
    GCP_REGION = os.getenv('GCP_REGION', 'us-central1')
    GEMINI_MODEL = os.getenv('GEMINI_MODEL', 'gemini-2.5-flash')
    MAX_ROWS_RETURN = int(os.getenv('MAX_ROWS_RETURN', '1000'))
    QUERY_TIMEOUT = int(os.getenv('QUERY_TIMEOUT', '30'))
    
    # Database types
    DB_TYPE_MYSQL = "mysql"
    DB_TYPE_SQLSERVER = "sqlserver"
    
    # New Gemini API Key
    GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', 'AIzaSyAb8RN6KvQqZ3KwDNt9bXhg6UE0QiIZM_ax5uRQK_ZIh5nHf6sw')

# Global config instance
config = Config()

print("✅ Configuration loaded for Aiven MySQL & New GCP Project")