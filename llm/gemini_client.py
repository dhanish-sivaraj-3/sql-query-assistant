import google.generativeai as genai
import logging
import os
from config.settings import config

logger = logging.getLogger(__name__)

class GeminiSQLGenerator:
    def __init__(self):
        self.initialized = False
        self.model = None
        self.schema_cache = {}
        
        # Configure Gemini with API key from environment
        api_key = os.getenv('GEMINI_API_KEY')
        if not api_key:
            logger.error("❌ GEMINI_API_KEY environment variable not set")
            logger.error("Please set GEMINI_API_KEY in Render environment variables")
            return
        
        try:
            genai.configure(api_key=api_key)
            self.model = genai.GenerativeModel(config.GEMINI_MODEL)
            self.initialized = True
            logger.info(f"✅ Gemini configured successfully with model: {config.GEMINI_MODEL}")
        except Exception as e:
            logger.error(f"❌ Failed to configure Gemini: {str(e)}")
    
    def is_initialized(self):
        return self.initialized and self.model is not None
    
    def get_schema_context(self, db_connector, database=None):
        """
        Get database schema as context for Gemini
        """
        if not self.is_initialized():
            return "AI service not available. Please check Gemini API key configuration."
            
        db = database or db_connector.database
        if not db:
            return "No database selected. Please select a database first."
        
        if db not in self.schema_cache:
            try:
                result = db_connector.get_detailed_tables_info(db)
                if result['success']:
                    self.schema_cache[db] = self._format_schema_info(result['tables'], db)
                else:
                    logger.error(f"Failed to fetch schema information for {db}")
                    self.schema_cache[db] = f"Unable to fetch schema information for {db}"
            except Exception as e:
                logger.error(f"Error getting schema for {db}: {e}")
                self.schema_cache[db] = f"Schema information unavailable for {db}"
        
        return self.schema_cache[db]
    
    def _format_schema_info(self, tables_data, database_name):
        """
        Format schema information for Gemini prompt with ACTUAL column names
        """
        schema_text = f"Database: {database_name}\n\nACTUAL SCHEMA - Use ONLY these tables and columns:\n"
        
        for table, columns in tables_data.items():
            schema_text += f"\nTable: {table}\n"
            schema_text += "Columns:\n"
            for col in columns:
                key_info = ""
                if col['primary_key']:
                    key_info = " (PRIMARY KEY)"
                
                nullable_info = " (NULLABLE)" if col['nullable'] else " (NOT NULL)"
                
                schema_text += f"  - {col['name']} ({col['type']}){key_info}{nullable_info}\n"
        
        # Add specific examples for each database
        if database_name == "healthcare" and "healthcare_data" in tables_data:
            schema_text += """
Common Query Examples for healthcare:
- For patient details: SELECT Name, Age, Gender, Medical_Condition FROM healthcare_data
- For billing information: SELECT Name, Insurance_Provider, Billing_Amount FROM healthcare_data
- For admission details: SELECT Name, Date_of_Admission, Doctor, Hospital FROM healthcare_data
"""
        elif database_name == "ecommerce" and "ecommerce_data" in tables_data:
            schema_text += """
Common Query Examples for ecommerce:
- For customer orders: SELECT customer_id, order_id, product_name, quantity FROM ecommerce_data
- For sales analysis: SELECT product_name, quantity, unit_price FROM ecommerce_data
- For order details: SELECT order_id, order_date, order_status, payment_method FROM ecommerce_data
"""
        elif database_name == "customer" and "customer_table" in tables_data:
            schema_text += """
Common Query Examples for customer database:
- Count records: SELECT COUNT(*) FROM customer_table
- Get customer details: SELECT customer_id, first_name, last_name, email FROM customer_table
- Find customers by location: SELECT first_name, last_name, city, country FROM customer_table WHERE city = 'value'
"""
        
        return schema_text
    
    def _get_table_name(self, database):
        """
        Get the main table name for a database
        """
        table_mapping = {
            "healthcare": "healthcare_data",
            "ecommerce": "ecommerce_data", 
            "customer": "customer_table",
            "defaultdb": "ecommerce_data"
        }
        return table_mapping.get(database, "customer_table")
    
    def clear_schema_cache(self, database=None):
        """Clear schema cache to force refresh"""
        if database:
            if database in self.schema_cache:
                del self.schema_cache[database]
                logger.info(f"Cleared schema cache for {database}")
        else:
            self.schema_cache.clear()
            logger.info("Cleared all schema cache")
    
    def generate_sql_query(self, natural_language_query, db_connector, database=None, conversation_history=None):
        """
        Generate SQL query from natural language using Gemini
        """
        if not self.is_initialized():
            return {
                'success': False,
                'error': "Gemini AI service not available. Please check if GEMINI_API_KEY is set in environment variables."
            }
            
        try:
            schema_context = self.get_schema_context(db_connector, database)
            
            # Improved system prompt focused purely on SQL generation
            system_prompt = f"""
You are a SQL query generator. Your ONLY task is to convert natural language requests into valid SQL queries.

DATABASE SCHEMA:
{schema_context}

CRITICAL RULES:
1. Use ONLY the table names and column names shown in the schema above
2. Do NOT invent or assume table or column names that are not listed
3. Generate ONLY the SQL code without any explanations, markdown, or additional text
4. Use proper SQL syntax for MySQL
5. Use backticks for column names with spaces or special characters
6. Always include a LIMIT clause if not specified to prevent large result sets
7. If counting records, use COUNT(*)
8. Use proper WHERE clause syntax for filtering

Natural Language Request: "{natural_language_query}"

Generate ONLY the SQL query:
"""
            
            logger.info(f"Generating SQL for: {natural_language_query}")
            logger.info(f"Using database: {database}")
            
            response = self.model.generate_content(
                system_prompt,
                generation_config={
                    "temperature": 0.1,
                    "top_p": 0.8,
                    "top_k": 40,
                    "max_output_tokens": 500,
                }
            )
            
            logger.info(f"Gemini response received: {response}")
            
            if response.candidates and len(response.candidates) > 0:
                candidate = response.candidates[0]
                logger.info(f"Candidate finish reason: {candidate.finish_reason}")
                
                if candidate.finish_reason == 1:  # STOP - successful completion
                    if candidate.content and candidate.content.parts:
                        sql_query = candidate.content.parts[0].text.strip()
                        
                        # Clean up the query - remove any markdown or explanations
                        if sql_query.startswith("```sql"):
                            sql_query = sql_query[6:]
                        if sql_query.startswith("```"):
                            sql_query = sql_query[3:]
                        if sql_query.endswith("```"):
                            sql_query = sql_query[:-3]
                        
                        # Remove any explanatory text after the SQL
                        sql_query = sql_query.split(';')[0] + ';' if ';' in sql_query else sql_query
                        sql_query = sql_query.split('\n')[0] if '\n' in sql_query else sql_query
                        
                        logger.info(f"Generated SQL: {sql_query}")
                        
                        return {
                            'success': True,
                            'sql_query': sql_query.strip(),
                            'model_used': config.GEMINI_MODEL,
                            'database': database
                        }
                    else:
                        logger.error(f"No content parts in response")
                        return {
                            'success': False,
                            'error': "AI model did not generate any SQL content."
                        }
                else:
                    logger.error(f"Content generation blocked. Finish reason: {candidate.finish_reason}")
                    # Try a simpler, more direct approach
                    return self._generate_simple_sql(natural_language_query, database)
            else:
                logger.error("No candidates in response")
                return {
                    'success': False,
                    'error': "AI model did not return any response"
                }
            
        except Exception as e:
            logger.error(f"Gemini query generation error: {str(e)}")
            # Fallback to simple SQL generation
            return self._generate_simple_sql(natural_language_query, database)
    
    def _generate_simple_sql(self, natural_language_query, database):
        """
        Fallback method to generate simple SQL queries when Gemini fails
        """
        try:
            # Simple rule-based SQL generation as fallback
            query_lower = natural_language_query.lower()
            
            if "count" in query_lower and "record" in query_lower:
                sql = f"SELECT COUNT(*) FROM customer_table;"
            elif "count" in query_lower:
                sql = f"SELECT COUNT(*) FROM customer_table;"
            elif "top" in query_lower or "first" in query_lower:
                # Extract number from query
                import re
                numbers = re.findall(r'\d+', natural_language_query)
                limit = numbers[0] if numbers else "10"
                sql = f"SELECT * FROM customer_table LIMIT {limit};"
            elif "select" in query_lower and "from" in query_lower:
                # If it already looks like SQL, use it as is
                sql = natural_language_query
                if not sql.endswith(';'):
                    sql += ';'
            else:
                # Default select with limit
                sql = f"SELECT * FROM customer_table LIMIT 10;"
            
            logger.info(f"Generated fallback SQL: {sql}")
            
            return {
                'success': True,
                'sql_query': sql,
                'model_used': 'fallback',
                'database': database
            }
            
        except Exception as e:
            logger.error(f"Fallback SQL generation failed: {str(e)}")
            return {
                'success': False,
                'error': f"Failed to generate SQL query: {str(e)}"
            }
    
    def explain_query_results(self, query, results_summary, database):
        """
        Generate natural language explanation of query results using Gemini
        """
        if not self.is_initialized():
            return "AI service not available for explanation."
            
        try:
            prompt = f"""
            Explain these SQL query results in simple terms:
            
            Database: {database}
            Query: {query}
            
            Results: {results_summary}
            
            Provide a brief, business-friendly explanation focusing on what the data shows.
            Keep it to 2-3 sentences maximum.
            """
            
            response = self.model.generate_content(prompt)
            
            if response.candidates and len(response.candidates) > 0:
                candidate = response.candidates[0]
                if candidate.content and candidate.content.parts:
                    return candidate.content.parts[0].text.strip()
            
            return "Query executed successfully. Results are displayed above."
            
        except Exception as e:
            logger.error(f"Result explanation error: {str(e)}")
            return "Query executed successfully. Results are displayed above."

# Singleton instance
gemini_client = GeminiSQLGenerator()
