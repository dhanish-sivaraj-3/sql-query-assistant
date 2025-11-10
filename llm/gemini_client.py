import google.generativeai as genai
import logging
import os
from config.settings import config

logger = logging.getLogger(__name__)

class GeminiSQLGenerator:
    def __init__(self):
        # Configure Gemini with API key from environment
        api_key = os.getenv('GEMINI_API_KEY')
        if api_key:
            genai.configure(api_key=api_key)
            logger.info(f"Using Gemini with API key authentication - Model: {config.GEMINI_MODEL}")
        else:
            # Fallback to application default credentials
            genai.configure()
            logger.info(f"Using Gemini with application default credentials - Model: {config.GEMINI_MODEL}")
        
        self.model = genai.GenerativeModel(config.GEMINI_MODEL)
        self.schema_cache = {}  # Cache schemas by database
    
    def get_schema_context(self, db_connector, database=None):
        """
        Get database schema as context for Gemini
        """
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
        
        return schema_text
    
    def _get_table_name(self, database):
        """
        Get the main table name for a database
        """
        table_mapping = {
            "healthcare": "healthcare_table",
            "ecommerce": "ecommerce_table"
        }
        return table_mapping.get(database, "ecommerce_data")  # default to ecommerce_data
    
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
        Generate SQL query from natural language using Gemini 2.5 Flash
        """
        schema_context = self.get_schema_context(db_connector, database)
        
        system_prompt = f"""
        You are a SQL expert. Generate SQL queries using ONLY the tables and columns that exist in the actual database schema.

        {schema_context}

        CRITICAL RULES:
        1. Use ONLY the table names and column names shown in the schema above
        2. Do NOT invent or assume table or column names that are not listed
        3. Generate ONLY the SQL code, no explanations
        4. Use LIMIT for row limits
        5. If unsure about columns, use SELECT * but add LIMIT
        6. Use backticks for column names with spaces or special characters
        7. For SQL Server, use TOP instead of LIMIT
        8. Use proper SQL syntax based on the database type

        Natural Language Request: "{natural_language_query}"

        SQL Query:
        """
        
        try:
            response = self.model.generate_content(
                system_prompt,
                generation_config={
                    "temperature": 0.1,
                    "top_p": 0.8,
                    "top_k": 40,
                    "max_output_tokens": 500,
                }
            )
            
            # Better response handling for Gemini 2.5 Flash
            if response.candidates and len(response.candidates) > 0:
                candidate = response.candidates[0]
                if candidate.content and candidate.content.parts:
                    sql_query = candidate.content.parts[0].text.strip()
                    
                    # Clean up the query
                    if sql_query.startswith("```sql"):
                        sql_query = sql_query[6:]
                    if sql_query.startswith("```"):
                        sql_query = sql_query[3:]
                    if sql_query.endswith("```"):
                        sql_query = sql_query[:-3]
                    
                    return {
                        'success': True,
                        'sql_query': sql_query.strip(),
                        'model_used': config.GEMINI_MODEL,
                        'database': database
                    }
                else:
                    logger.error(f"No content parts in response. Finish reason: {candidate.finish_reason}")
                    return {
                        'success': False,
                        'error': f"AI model did not generate content. Finish reason: {candidate.finish_reason}"
                    }
            else:
                logger.error("No candidates in response")
                return {
                    'success': False,
                    'error': "AI model did not return any response"
                }
            
        except Exception as e:
            logger.error(f"Gemini 2.5 Flash query generation error: {str(e)}")
            return {
                'success': False,
                'error': f"Failed to generate SQL query: {str(e)}"
            }
    
    def explain_query_results(self, query, results_summary, database):
        """
        Generate natural language explanation of query results using Gemini 2.5 Flash
        """
        try:
            prompt = f"""
            Database: {database}
            User Question: {query}
            
            Query Results Summary: {results_summary}
            
            Provide a concise, business-friendly explanation of these results in 2-3 sentences.
            Focus on key insights and what the numbers mean.
            """
            
            response = self.model.generate_content(prompt)
            
            if response.candidates and len(response.candidates) > 0:
                candidate = response.candidates[0]
                if candidate.content and candidate.content.parts:
                    return candidate.content.parts[0].text.strip()
            
            return "Unable to generate explanation for the results."
            
        except Exception as e:
            logger.error(f"Result explanation error: {str(e)}")
            return "Unable to generate explanation for the results."

# Singleton instance
gemini_client = GeminiSQLGenerator()