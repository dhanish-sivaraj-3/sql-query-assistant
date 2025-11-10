import pymysql
from sqlalchemy import create_engine, text, inspect
from contextlib import contextmanager
import logging
from config.settings import config
import os
from urllib.parse import quote_plus
import json
from datetime import date, datetime

logger = logging.getLogger(__name__)

class DatabaseConnector:
    def __init__(self, database=None, db_type="mysql", custom_config=None):
        self.database = database
        self.db_type = db_type
        self.custom_config = custom_config or {}
        self.engine = None
        self._create_engine()
    
    def _build_connection_string(self):
        """Build connection string based on database type"""
        if self.db_type == "sqlserver":
            return self._build_sqlserver_connection_string()
        else:  # mysql
            return self._build_mysql_connection_string()
    
    def _build_mysql_connection_string(self):
        """Build MySQL connection string for Aiven with SSL"""
        server = self.custom_config.get('server', config.DB_SERVER)
        port = self.custom_config.get('port', config.DB_PORT)
        user = self.custom_config.get('user', config.DB_USER)
        password = self.custom_config.get('password', config.DB_PASSWORD)
        
        encoded_password = quote_plus(password)
        base_string = f"mysql+pymysql://{user}:{encoded_password}@{server}:{port}"
        
        # Aiven SSL configuration
        ssl_params = "ssl_ca=/app/ca.pem&ssl_verify_cert=true"
        
        if self.database:
            return f"{base_string}/{self.database}?{ssl_params}"
        else:
            return f"{base_string}/?{ssl_params}"
    
    def _build_sqlserver_connection_string(self):
        """Build SQL Server connection string"""
        server = self.custom_config.get('server', '')
        port = self.custom_config.get('port', '1433')
        user = self.custom_config.get('user', '')
        password = self.custom_config.get('password', '')
        database = self.database or ''
        
        logger.info(f"SQL Server Connection - Server: {server}, User: {user}, Database: {database}")
        
        if not server or not user or not password:
            raise Exception("SQL Server connection requires server, user, and password")
        
        server_clean = server.split(':')[0]
        
        if database:
            return f"mssql+pymssql://{user}:{password}@{server_clean}:{port}/{database}"
        else:
            return f"mssql+pymssql://{user}:{password}@{server_clean}:{port}"

    def _create_engine(self):
        """Create database engine with Aiven SSL support"""
        try:
            connection_string = self._build_connection_string()
            logger.info(f"Creating engine for {self.db_type} - Aiven MySQL")
            
            if self.db_type == "mysql":
                ssl_args = {
                    "ssl": {
                        "ca": "/app/ca.pem",
                        "check_hostname": True,
                        "verify_mode": True
                    }
                }
                self.engine = create_engine(
                    connection_string, 
                    pool_pre_ping=True, 
                    pool_recycle=3600,
                    connect_args={
                        "connect_timeout": 10,
                        **ssl_args
                    }
                )
            else:
                self.engine = create_engine(
                    connection_string,
                    pool_pre_ping=True,
                    pool_recycle=3600,
                )
                
            logger.info("Aiven MySQL engine created successfully")
            
        except Exception as e:
            logger.error(f"Aiven engine creation failed: {str(e)}")
            raise
    
    def set_database(self, database):
        """Set active database"""
        self.database = database
        self._create_engine()
    
    def set_custom_config(self, custom_config):
        """Update custom configuration"""
        self.custom_config = custom_config
        self._create_engine()
    
    @contextmanager
    def get_connection(self):
        """Get database connection with context management"""
        connection = None
        try:
            connection = self.engine.connect()
            yield connection
        except Exception as e:
            logger.error(f"Database connection error: {str(e)}")
            raise
        finally:
            if connection:
                connection.close()
    
    def execute_query(self, query, params=None, return_data=True):
        """Execute SQL query safely with parameters - without pandas"""
        try:
            with self.get_connection() as conn:
                if return_data:
                    result = conn.execute(text(query), params or {})
                    rows = result.fetchall()
                    
                    # Convert to list of dictionaries
                    columns = list(result.keys())
                    data = []
                    for row in rows:
                        row_dict = {}
                        for i, col in enumerate(columns):
                            value = row[i]
                            # Convert date/datetime objects to strings for JSON serialization
                            if isinstance(value, (date, datetime)):
                                value = value.isoformat()
                            row_dict[col] = value
                        data.append(row_dict)
                    
                    return {
                        'success': True,
                        'data': data,
                        'row_count': len(data),
                        'columns': columns
                    }
                else:
                    result = conn.execute(text(query), params or {})
                    conn.commit()
                    return {
                        'success': True,
                        'affected_rows': result.rowcount
                    }
        except Exception as e:
            logger.error(f"Query execution error: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_databases(self):
        """Get list of all databases - FILTERED to show only user databases"""
        try:
            if self.db_type == "mysql":
                query = """
                SELECT schema_name as database_name 
                FROM information_schema.schemata 
                WHERE schema_name NOT IN (
                    'information_schema', 'mysql', 'performance_schema', 'sys',
                    'innodb', 'tmp'
                )
                ORDER BY schema_name
                """
            else:
                query = """
                SELECT name as database_name 
                FROM sys.databases 
                WHERE name NOT IN (
                    'master', 'tempdb', 'model', 'msdb'
                )
                AND state = 0
                ORDER BY name
                """
            
            with self.get_connection() as conn:
                result = conn.execute(text(query))
                
                if self.db_type == "mysql":
                    databases = [row[0] for row in result]
                else:
                    databases = [row[0] for row in result]
                    
                logger.info(f"Found {len(databases)} user databases: {databases}")
                return {
                    'success': True,
                    'databases': databases,
                    'server': self.custom_config.get('server', config.DB_SERVER),
                    'db_type': self.db_type,
                    'total_count': len(databases)
                }
        except Exception as e:
            logger.error(f"Error getting databases: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'databases': config.DEFAULT_DATABASES if self.db_type == "mysql" else [],
                'server': self.custom_config.get('server', config.DB_SERVER)
            }
    
    def get_detailed_tables_info(self, database=None):
        """Get detailed table information including column names"""
        db = database or self.database
        if not db:
            return {'success': False, 'error': 'No database selected'}
        
        try:
            current_db = self.database
            self.set_database(db)
            
            inspector = inspect(self.engine)
            tables = inspector.get_table_names()
            
            tables_with_columns = {}
            for table in tables:
                columns = inspector.get_columns(table)
                tables_with_columns[table] = [
                    {
                        'name': col['name'],
                        'type': str(col['type']),
                        'nullable': col['nullable'],
                        'primary_key': 'primary_key' in col and col['primary_key']
                    }
                    for col in columns
                ]
            
            if current_db:
                self.set_database(current_db)
            
            return {
                'success': True,
                'tables': tables_with_columns,
                'database': db,
                'table_count': len(tables),
                'db_type': self.db_type
            }
        except Exception as e:
            logger.error(f"Error getting detailed tables info for {db}: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def test_connection(self, database=None):
        """Test database connection"""
        try:
            db = database or self.database
            
            if db:
                self.set_database(db)
            
            with self.get_connection() as conn:
                conn.execute(text("SELECT 1"))
            
            logger.info("Aiven MySQL connection test successful")
            return True
        except Exception as e:
            logger.error(f"Aiven connection test failed: {str(e)}")
            return False

# Global connector instance (default Aiven MySQL)
db_connector = DatabaseConnector()
