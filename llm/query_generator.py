import openai
import json
import logging
from config.settings import config
from database.connector import db_connector

logger = logging.getLogger(__name__)

class SQLQueryGenerator:
    def __init__(self):
        self.client = openai.OpenAI(api_key=config.OPENAI_API_KEY)
        self.schema_info = None
    
    def get_schema_context(self):
        """
        Get database schema as context for LLM
        """
        if not self.schema_info:
            result = db_connector.get_schema_info()
            if result['success']:
                self.schema_info = self._format_schema_info(result['data'])
            else:
                logger.error("Failed to fetch schema information")
                self.schema_info = "Unable to fetch schema information"
        
        return self.schema_info
    
    def _format_schema_info(self, schema_data):
        """
        Format schema information for LLM prompt
        """
        tables = {}
        for row in schema_data:
            table_key = f"{row['TABLE_SCHEMA']}.{row['TABLE_NAME']}"
            if table_key not in tables:
                tables[table_key] = []
            tables[table_key].append({
                'column': row['COLUMN_NAME'],
                'type': row['DATA_TYPE'],
                'nullable': row['IS_NULLABLE']
            })
        
        schema_text = "Database Schema:\n"
        for table, columns in tables.items():
            schema_text += f"\n{table}:\n"
            for col in columns:
                schema_text += f"  - {col['column']} ({col['type']}) {'NULL' if col['nullable'] == 'YES' else 'NOT NULL'}\n"
        
        return schema_text
    
    def generate_sql_query(self, natural_language_query, conversation_history=None):
        """
        Generate SQL query from natural language using LLM
        """
        schema_context = self.get_schema_context()
        
        system_prompt = f"""
        You are a senior SQL developer. Generate accurate SQL Server compatible SQL queries based on natural language requests.

        {schema_context}

        Guidelines:
        1. Generate ONLY SQL code, no explanations
        2. Use SQL Server syntax
        3. Always use schema prefixes (dbo.) for tables
        4. Include WHERE clauses when filtering is implied
        5. Use appropriate JOINs when multiple tables are needed
        6. Add TOP 1000 if no specific limit is mentioned
        7. Use meaningful column aliases
        8. Handle date filters appropriately
        9. Avoid SELECT * unless specifically requested
        10. Include ORDER BY for ranking queries

        Return ONLY the SQL query without any markdown formatting or code blocks.
        """
        
        user_prompt = f"Generate SQL query for: {natural_language_query}"
        
        if conversation_history:
            user_prompt += f"\n\nPrevious context: {conversation_history}"
        
        try:
            response = self.client.chat.completions.create(
                model=config.LLM_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.1,
                max_tokens=500
            )
            
            sql_query = response.choices[0].message.content.strip()
            
            # Clean up the query (remove markdown code blocks if present)
            if sql_query.startswith("```sql"):
                sql_query = sql_query[6:]
            if sql_query.startswith("```"):
                sql_query = sql_query[3:]
            if sql_query.endswith("```"):
                sql_query = sql_query[:-3]
            
            return {
                'success': True,
                'sql_query': sql_query.strip(),
                'model_used': config.LLM_MODEL
            }
            
        except Exception as e:
            logger.error(f"LLM query generation error: {str(e)}")
            return {
                'success': False,
                'error': f"Failed to generate SQL query: {str(e)}"
            }
    
    def explain_query_results(self, query, results_summary):
        """
        Generate natural language explanation of query results
        """
        try:
            prompt = f"""
            SQL Query: {query}
            
            Results Summary: {results_summary}
            
            Provide a concise, business-friendly explanation of these results in 2-3 sentences.
            Focus on key insights and what the numbers mean.
            """
            
            response = self.client.chat.completions.create(
                model=config.LLM_MODEL,
                messages=[
                    {"role": "system", "content": "You are a data analyst explaining SQL query results to business users."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=200
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error(f"Result explanation error: {str(e)}")
            return "Unable to generate explanation for the results."

# Singleton instance
query_generator = SQLQueryGenerator()