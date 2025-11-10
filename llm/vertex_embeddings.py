from google.cloud import aiplatform
import logging
from config.settings import config

logger = logging.getLogger(__name__)

class VertexEmbeddings:
    def __init__(self):
        self.client = aiplatform.gapic.PredictionServiceClient(
            client_options={
                "api_endpoint": f"{config.GCP_REGION}-aiplatform.googleapis.com"
            }
        )
        self.endpoint = f"projects/{config.GCP_PROJECT}/locations/{config.GCP_REGION}/publishers/google/models/{config.EMBEDDING_MODEL}"
    
    def get_embeddings(self, texts):
        """
        Get embeddings for a list of texts using Vertex AI
        """
        try:
            instances = [{"content": text} for text in texts]
            response = self.client.predict(
                endpoint=self.endpoint,
                instances=instances
            )
            
            embeddings = []
            for prediction in response.predictions:
                embeddings.append(prediction['embeddings']['values'])
            
            return embeddings
        except Exception as e:
            logger.error(f"Embedding generation error: {str(e)}")
            return None
    
    def get_schema_embeddings(self, schema_data):
        """
        Create embeddings for database schema for semantic search
        """
        schema_texts = []
        
        # Create meaningful text representations of schema
        for table in schema_data:
            table_text = f"Table {table['TABLE_SCHEMA']}.{table['TABLE_NAME']} has columns: "
            columns_text = ", ".join([f"{col['COLUMN_NAME']} ({col['DATA_TYPE']})" for col in table['columns']])
            schema_texts.append(table_text + columns_text)
        
        return self.get_embeddings(schema_texts)

# Singleton instance
vertex_embeddings = VertexEmbeddings()