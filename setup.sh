#!/bin/bash

echo "🔧 Setting up Enhanced Multi-Database SQL Query Assistant for NEW PROJECT..."

# Set NEW project
PROJECT_ID="top-caldron-477810-k3"
gcloud config set project $PROJECT_ID

echo "📁 New Project: $PROJECT_ID"
echo "🔗 Aiven MySQL Instance: mysql-dhanish2468-a3a0.j.aivencloud.com:20138"
echo "👤 Database User: avnadmin"
echo "📊 Default Databases: defaultdb, healthcare, ecommerce"
echo "🔐 SSL: Enabled with Aiven CA"
echo "🤖 AI Model: Gemini 2.5 Flash"
echo "🗄️  Supported Databases: MySQL, SQL Server"
echo "🌐 Multi-Database Support: ✅ Enabled"

# Check if required APIs are enabled
echo "🔍 Checking required APIs..."
APIS=(
    "run.googleapis.com"
    "cloudbuild.googleapis.com"
    "containerregistry.googleapis.com"
    "aiplatform.googleapis.com"
)

for API in "${APIS[@]}"; do
    if gcloud services list --enabled --filter="name:$API" | grep -q "$API"; then
        echo "   ✅ $API: Enabled"
    else
        echo "   🔄 Enabling $API..."
        gcloud services enable "$API"
    fi
done

# Make scripts executable
chmod +x deploy.sh

echo ""
echo "✅ Enhanced setup complete for NEW PROJECT!"
echo ""
echo "🚀 Ready to deploy with advanced features:"
echo "   • Aiven MySQL as primary database"
echo "   • SSL-enabled database connections"
echo "   • Multi-database support (MySQL & SQL Server)"
echo "   • Enhanced schema visualization with column details"
echo "   • Custom database connection interface"
echo "   • Improved AI-powered SQL generation"
echo ""
echo "📋 To deploy, run: ./deploy.sh"