from flask import Flask, jsonify, request, render_template_string
import logging
from datetime import datetime
import os
import json

from config.settings import config
from database.connector import db_connector, DatabaseConnector
from llm.gemini_client import gemini_client

# Configure standard Python logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Store conversation history per database
conversation_history = {}

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>Multi-Database SQL Assistant</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
</head>
<body class="bg-gray-50 min-h-screen p-4">
    <div class="max-w-7xl mx-auto">
        <!-- Header -->
        <div class="text-center mb-8">
            <div class="flex items-center justify-center mb-4">
                <i class="fas fa-database text-4xl text-blue-500 mr-3"></i>
                <h1 class="text-4xl font-bold text-gray-800">Multi-Database SQL Assistant</h1>
            </div>
            <p class="text-xl text-gray-600">Query Multiple Databases with Natural Language</p>
            <div class="mt-4 flex justify-center space-x-4">
                <span id="dbStatus" class="px-3 py-1 bg-red-100 text-red-800 rounded-full text-sm">
                    <i class="fas fa-database mr-1"></i>Database: Checking...
                </span>
                <span id="aiStatus" class="px-3 py-1 bg-red-100 text-red-800 rounded-full text-sm">
                    <i class="fas fa-robot mr-1"></i>AI: Checking...
                </span>
                <span id="selectedDb" class="px-3 py-1 bg-blue-100 text-blue-800 rounded-full text-sm hidden">
                    <i class="fas fa-table mr-1"></i>Database: None
                </span>
            </div>
        </div>

        <!-- Database Selection -->
        <div class="bg-white rounded-2xl shadow-lg p-6 mb-8">
            <h2 class="text-2xl font-semibold text-gray-800 mb-4">
                <i class="fas fa-database mr-2"></i>Select Database
            </h2>
            <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-4" id="databaseList">
                <!-- Databases will be loaded here -->
            </div>
            
            <!-- Custom Database Connection -->
            <div class="mt-6 p-4 bg-gray-50 rounded-lg">
                <h3 class="text-lg font-semibold text-gray-700 mb-3">
                    <i class="fas fa-plug mr-2"></i>Connect Custom Database
                </h3>
                
                <!-- Database Type Selection -->
                <div class="mb-4">
                    <label class="block text-sm font-medium text-gray-700 mb-2">Database Type</label>
                    <div class="flex space-x-4">
                        <label class="inline-flex items-center">
                            <input type="radio" name="dbType" value="mysql" checked class="db-type-radio">
                            <span class="ml-2">MySQL</span>
                        </label>
                        <label class="inline-flex items-center">
                            <input type="radio" name="dbType" value="sqlserver" class="db-type-radio">
                            <span class="ml-2">SQL Server</span>
                        </label>
                    </div>
                </div>
                
                <div class="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
                    <div>
                        <label class="block text-sm font-medium text-gray-700 mb-1">Server</label>
                        <input type="text" id="customServer" placeholder="e.g., DESKTOP-PL02DVO or 192.168.0.86" 
                               class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500">
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-gray-700 mb-1">Port</label>
                        <input type="text" id="customPort" placeholder="3306 for MySQL, 1433 for SQL Server" 
                               class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500">
                    </div>
                </div>
                
                <div class="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
                    <div>
                        <label class="block text-sm font-medium text-gray-700 mb-1">Username</label>
                        <input type="text" id="customUsername" placeholder="Database username" 
                               class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500">
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-gray-700 mb-1">Password</label>
                        <input type="password" id="customPassword" placeholder="Database password" 
                               class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500">
                    </div>
                </div>
                
                <div class="mb-4">
                    <label class="block text-sm font-medium text-gray-700 mb-1">Database Name (Optional)</label>
                    <input type="text" id="customDatabase" placeholder="Leave empty to see all databases" 
                           class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500">
                </div>
                
                <button id="connectCustomDb" 
                        class="px-4 py-2 bg-green-500 text-white rounded-lg hover:bg-green-600 focus:outline-none focus:ring-2 focus:ring-green-500">
                    <i class="fas fa-link mr-2"></i>Connect to Custom Database
                </button>
            </div>
        </div>

        <!-- Query Form (Initially Hidden) -->
        <div id="queryFormSection" class="bg-white rounded-2xl shadow-lg p-6 mb-8 hidden">
            <h2 class="text-2xl font-semibold text-gray-800 mb-4">
                <i class="fas fa-comment-dots mr-2"></i>Ask Questions About Your Data
            </h2>
            <form id="queryForm" class="space-y-4">
                <div>
                    <label class="block text-sm font-medium text-gray-700 mb-2">
                        What would you like to know about <span id="currentDbName" class="font-semibold">your database</span>?
                    </label>
                    <textarea 
                        id="query" 
                        name="query"
                        rows="3"
                        placeholder="Example: Show me the top 10 products by sales..."
                        class="w-full px-4 py-3 border border-gray-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none"
                        required
                    ></textarea>
                </div>
                <div class="flex space-x-4">
                    <button 
                        type="submit"
                        class="flex-1 px-6 py-3 bg-blue-500 text-white rounded-xl hover:bg-blue-600 focus:outline-none focus:ring-2 focus:ring-blue-500 font-semibold text-lg transition duration-200"
                    >
                        <i class="fas fa-paper-plane mr-2"></i>Generate & Execute SQL
                    </button>
                    <button 
                        type="button"
                        id="clearHistory"
                        class="px-6 py-3 bg-gray-500 text-white rounded-xl hover:bg-gray-600 focus:outline-none focus:ring-2 focus:ring-gray-500 font-semibold transition duration-200"
                    >
                        <i class="fas fa-trash mr-2"></i>Clear History
                    </button>
                </div>
            </form>
        </div>

        <!-- Database Info -->
        <div id="databaseInfo" class="bg-blue-50 rounded-2xl p-6 mb-8 hidden">
            <h3 class="text-lg font-semibold text-blue-800 mb-3">
                <i class="fas fa-info-circle mr-2"></i>Database Schema Information
            </h3>
            <div id="tablesList" class="text-blue-700">
                <!-- Tables with columns will be listed here -->
            </div>
        </div>

        <!-- Results Section -->
        <div id="results" class="hidden"></div>

        <!-- Conversation History -->
        <div id="historySection" class="bg-white rounded-2xl shadow-lg p-6 mt-8 hidden">
            <h3 class="text-xl font-semibold text-gray-800 mb-4">
                <i class="fas fa-history mr-2"></i>Conversation History
            </h3>
            <div id="historyList" class="space-y-3"></div>
        </div>

        <!-- Example Queries -->
        <div class="bg-green-50 rounded-2xl p-6 mt-8">
            <h3 class="text-lg font-semibold text-green-800 mb-3">
                <i class="fas fa-lightbulb mr-2"></i>Try These Example Queries:
            </h3>
            <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
                <button class="example-btn bg-white text-green-600 px-4 py-3 rounded-lg border border-green-200 hover:bg-green-50 transition duration-200 text-left">
                    "Show top 10 products by sales"
                </button>
                <button class="example-btn bg-white text-green-600 px-4 py-3 rounded-lg border border-green-200 hover:bg-green-50 transition duration-200 text-left">
                    "What's the monthly revenue trend?"
                </button>
                <button class="example-btn bg-white text-green-600 px-4 py-3 rounded-lg border border-green-200 hover:bg-green-50 transition duration-200 text-left">
                    "How many patients were admitted last month?"
                </button>
                <button class="example-btn bg-white text-green-600 px-4 py-3 rounded-lg border border-green-200 hover:bg-green-50 transition duration-200 text-left">
                    "Show customer distribution by region"
                </button>
            </div>
        </div>
    </div>

    <script>
        // Your existing JavaScript code here...
        // (Keep all your existing JavaScript code)
    </script>
</body>
</html>
'''

@app.route('/')
def home():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/health')
def health():
    """Health check endpoint"""
    db_connected = db_connector.test_connection()
    
    # Test Gemini connection
    gemini_connected = False
    try:
        test_response = gemini_client.model.generate_content("Test")
        gemini_connected = True
    except Exception as e:
        logger.error(f"Gemini connection test failed: {e}")
        gemini_connected = False
    
    return jsonify({
        "status": "healthy",
        "service": "Multi-Database SQL Query Assistant",
        "database_user": config.DB_USER,
        "database_connected": db_connected,
        "gemini_connected": gemini_connected,
        "default_databases": config.DEFAULT_DATABASES,
        "timestamp": datetime.utcnow().isoformat()
    })

# ... include all your other existing routes (get_databases, get_tables, connect_custom, query, etc.) ...

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8000))
    logger.info(f"🚀 Starting Multi-Database SQL Query Assistant on port {port}")
    logger.info(f"📊 Default databases: {config.DEFAULT_DATABASES}")
    logger.info(f"🔗 Database server: {config.DB_SERVER}:{config.DB_PORT}")
    app.run(host='0.0.0.0', port=port, debug=False)
