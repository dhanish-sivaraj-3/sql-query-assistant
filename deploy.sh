#!/bin/bash

# Set variables for NEW PROJECT
PROJECT_ID="top-caldron-477810-k3"
REGION="us-central1"
SERVICE_NAME="sql-query-assistant"

echo "🚀 Deploying Multi-Database SQL Query Assistant to NEW PROJECT with Aiven MySQL..."

# Set the project
gcloud config set project $PROJECT_ID

echo "🔍 Checking for syntax errors..."
python -m py_compile app.py && echo "✅ app.py: No syntax errors"
python -m py_compile database/connector.py && echo "✅ database/connector.py: No syntax errors"
python -m py_compile llm/gemini_client.py && echo "✅ llm/gemini_client.py: No syntax errors"
python -m py_compile config/settings.py && echo "✅ config/settings.py: No syntax errors"

# Build and deploy with Aiven MySQL
gcloud run deploy $SERVICE_NAME \
    --source . \
    --region $REGION \
    --platform managed \
    --allow-unauthenticated \
    --set-env-vars="DB_SERVER=mysql-dhanish2468-a3a0.j.aivencloud.com,DB_PORT=20138,DB_USER=avnadmin,DB_PASSWORD=,GCP_REGION=us-central1,GEMINI_MODEL=gemini-2.5-flash,MAX_ROWS_RETURN=1000,GEMINI_API_KEY=AIzaSyAb8RN6KvQqZ3KwDNt9bXhg6UE0QiIZM_ax5uRQK_ZIh5nHf6sw,GCP_PROJECT=top-caldron-477810-k3" \
    --cpu=2 \
    --memory=2Gi \
    --timeout=300 \
    --concurrency=80

if [ $? -eq 0 ]; then
    echo "✅ Enhanced deployment complete to NEW PROJECT!"
    echo ""
    echo "🎯 Features Deployed:"
    echo "   • Aiven MySQL as Default Database"
    echo "   • Multi-Database Support (MySQL & SQL Server)"
    echo "   • Enhanced Schema Display with Column Information"
    echo "   • Custom Database Connection Interface"
    echo "   • Improved UI with Database Type Selection"
    echo "   • SSL-Enabled Aiven Connection"

    SERVICE_URL=$(gcloud run services describe $SERVICE_NAME --region $REGION --format 'value(status.url)' 2>/dev/null)
    if [ -n "$SERVICE_URL" ]; then
        echo "🌐 Your enhanced application is available at: $SERVICE_URL"
        echo ""
        echo "📚 Usage Instructions:"
        echo "   1. Aiven databases (defaultdb, healthcare, ecommerce) will appear automatically"
        echo "   2. Click any database to view detailed schema with columns"
        echo "   3. Use 'Connect Custom Database' for external MySQL/SQL Server connections"
        echo "   4. Select database type (MySQL/SQL Server) for custom connections"
        echo "   5. Enter server details, credentials, and connect"
    fi
else
    echo "❌ Deployment failed. Checking build logs..."
    BUILD_ID=$(gcloud builds list --limit=1 --format="value(ID)")
    if [ -n "$BUILD_ID" ]; then
        echo "📋 Build logs: https://console.cloud.google.com/cloud-build/builds;region=us-central1/$BUILD_ID?project=$PROJECT_ID"
        echo ""
        echo "🔧 Common fixes:"
        echo "   - Check Dockerfile syntax"
        echo "   - Verify all required files are present"
        echo "   - Ensure no syntax errors in Python files"
        echo "   - Verify Aiven database is accessible"
    fi
fi

# Display deployment status
echo ""
echo "📊 Checking deployment status..."
gcloud run services describe $SERVICE_NAME --region $REGION --format="value(status.url)"