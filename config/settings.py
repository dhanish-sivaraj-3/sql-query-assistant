# config/settings.py
import os
import logging

logger = logging.getLogger(__name__)

class Config:
    # Aiven MySQL Database Configuration - ALL FROM ENVIRONMENT VARIABLES
    DB_SERVER = os.getenv('DB_SERVER', 'mysql-dhanish2468-a3a0.j.aivencloud.com')
    DB_PORT = os.getenv('DB_PORT', '20138')
    DB_USER = os.getenv('DB_USER', 'avnadmin')
    DB_PASSWORD = os.getenv('DB_PASSWORD', '')  # MUST be set in environment
    DEFAULT_DATABASES = ["defaultdb", "healthcare", "ecommerce"]
    
    MYSQL_SYSTEM_DATABASES = ["information_schema", "mysql", "performance_schema", "sys"]
    SQLSERVER_SYSTEM_DATABASES = ["master", "tempdb", "model", "msdb"]
    
    GEMINI_MODEL = os.getenv('GEMINI_MODEL', 'gemini-2.5-flash')
    MAX_ROWS_RETURN = int(os.getenv('MAX_ROWS_RETURN', '1000'))
    QUERY_TIMEOUT = int(os.getenv('QUERY_TIMEOUT', '30'))
    
    DB_TYPE_MYSQL = "mysql"
    DB_TYPE_SQLSERVER = "sqlserver"
    
    GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '')  # MUST be set in environment

config = Config()

print("✅ Configuration loaded for Aiven MySQL & Render")
