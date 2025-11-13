from flask import Flask, jsonify, request, render_template_string
import logging
from datetime import datetime
import os
import json
import signal

from config.settings import config
from database.connector import db_connector, DatabaseConnector
from llm.gemini_client import gemini_client

# Configure standard Python logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Store conversation history per database
conversation_history = {}

# Store custom connections by database
custom_connections = {}

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
                        <input type="text" id="customServer" placeholder="e.g., gateway01.ap-southeast-1.prod.aws.tidbcloud.com" 
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
        let currentDatabase = null;
        let sessionId = 'session_' + Math.random().toString(36).substr(2, 9);
        let currentConnectionInfo = null;
        
        // Store original password securely (not in DOM)
        let originalPassword = null;
    
        // Check system status on load
        async function checkSystemStatus() {
            // ... existing code ...
        }
        
        async function loadDatabases() {
            // ... existing code ...
        }
        
        // Select database
        async function selectDatabase(database, isCustom = false, serverInfo = null) {
            console.log('Selecting database:', database, 'Custom:', isCustom);
            currentDatabase = database;
            
            // Update UI
            document.getElementById('selectedDb').classList.remove('hidden');
            if (isCustom && serverInfo) {
                document.getElementById('selectedDb').innerHTML = `<i class="fas fa-table mr-1"></i>Database: ${database} (${serverInfo})`;
            } else {
                document.getElementById('selectedDb').innerHTML = `<i class="fas fa-table mr-1"></i>Database: ${database}`;
            }
            document.getElementById('queryFormSection').classList.remove('hidden');
            document.getElementById('currentDbName').textContent = database;
            
            // Store custom connection info globally for this database
            if (isCustom && currentConnectionInfo) {
                // Register this database with the custom connection
                await registerCustomDatabase(database, currentConnectionInfo);
            }
            
            // Load database info
            await loadDatabaseInfo(database, isCustom);
            
            // Scroll to query form
            document.getElementById('queryFormSection').scrollIntoView({ behavior: 'smooth' });
        }
        
        // Register custom database with backend
        async function registerCustomDatabase(database, connectionInfo) {
            try {
                const response = await fetch('/api/register-custom-db', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        database: database,
                        connection_info: connectionInfo
                    })
                });
                const data = await response.json();
                console.log('Custom database registration:', data);
            } catch (error) {
                console.error('Error registering custom database:', error);
            }
        }
        
        function showDatabaseSelection(databases, server, dbType, connectionData) {
            const databaseList = document.getElementById('databaseList');
            
            // Clear existing custom databases to avoid duplicates
            const existingCustomDbs = databaseList.querySelectorAll('.bg-green-50');
            existingCustomDbs.forEach(db => db.remove());
            
            databases.forEach(db => {
                const dbCard = document.createElement('div');
                dbCard.className = 'bg-green-50 rounded-lg p-4 border border-green-200 cursor-pointer hover:bg-green-100 transition duration-200 mb-2';
                dbCard.innerHTML = `
                    <div class="flex items-center">
                        <i class="fas fa-database text-green-500 mr-3"></i>
                        <div>
                            <h3 class="font-semibold text-green-800">${db}</h3>
                            <p class="text-green-600 text-sm">Custom ${dbType.toUpperCase()} • ${server}</p>
                        </div>
                    </div>
                `;
                dbCard.addEventListener('click', () => {
                    selectDatabase(db, true, connectionData.server_info);
                    // Store connection info for future queries - PRESERVE PASSWORD
                    currentConnectionInfo = {
                        server: server,
                        db_type: dbType,
                        username: document.getElementById('customUsername').value,
                        password: originalPassword, // Use stored password, not from DOM
                        port: document.getElementById('customPort').value || (dbType === 'mysql' ? '3306' : '1433')
                    };
                });
                databaseList.appendChild(dbCard);
            });
            
            // Scroll to show the new databases
            databaseList.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }
        
        async function loadDatabaseInfo(database, isCustom = false) {
            try {
                console.log('Loading database info for:', database, 'Custom:', isCustom);
                
                const requestBody = {
                    database: database,
                    is_custom: isCustom
                };
                
                // Add custom connection info if available - FIXED: Always use stored connection info
                if (currentConnectionInfo) {
                    requestBody.custom_connection = {
                        server: currentConnectionInfo.server,
                        db_type: currentConnectionInfo.db_type,
                        username: currentConnectionInfo.username,
                        password: currentConnectionInfo.password, // CRITICAL: Include password
                        port: currentConnectionInfo.port
                    };
                }
                
                const response = await fetch(`/api/databases/${encodeURIComponent(database)}/tables`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify(requestBody)
                });
                
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                
                const data = await response.json();
                console.log('Database info response:', data);
                
                const databaseInfo = document.getElementById('databaseInfo');
                const tablesList = document.getElementById('tablesList');
                
                if (data.success && data.tables && Object.keys(data.tables).length > 0) {
                    databaseInfo.classList.remove('hidden');
                    
                    let tablesHTML = `
                        <div class="flex items-center mb-4">
                            <i class="fas fa-info-circle mr-2"></i>
                            <span class="font-semibold">Database Schema: ${database}</span>
                            <span class="ml-2 px-2 py-1 bg-blue-100 text-blue-800 rounded text-xs">
                                ${data.table_count} table${data.table_count !== 1 ? 's' : ''}
                            </span>
                        </div>
                    `;
                    
                    Object.entries(data.tables).forEach(([tableName, columns]) => {
                        tablesHTML += `
                            <div class="bg-white rounded-lg p-4 border border-blue-200 mb-4 shadow-sm">
                                <div class="flex items-center justify-between mb-3">
                                    <div class="flex items-center">
                                        <i class="fas fa-table text-blue-500 mr-2"></i>
                                        <span class="font-semibold text-blue-800 text-lg">${tableName}</span>
                                    </div>
                                    <span class="px-2 py-1 bg-gray-100 text-gray-700 rounded text-xs">
                                        ${columns.length} column${columns.length !== 1 ? 's' : ''}
                                    </span>
                                </div>
                                <div class="border-t border-gray-200 pt-3">
                                    <p class="text-sm font-medium text-gray-700 mb-2">Columns:</p>
                                    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2">
                                        ${columns.map(col => `
                                            <div class="text-sm bg-gray-50 rounded-lg px-3 py-2 border border-gray-200 hover:bg-blue-50 transition-colors">
                                                <div class="flex items-center justify-between">
                                                    <span class="font-medium text-gray-900">${col.name}</span>
                                                    <div class="flex space-x-1">
                                                        ${col.primary_key ? '<span class="px-1 bg-green-100 text-green-800 rounded text-xs font-bold" title="Primary Key">PK</span>' : ''}
                                                        ${!col.nullable ? '<span class="px-1 bg-red-100 text-red-800 rounded text-xs font-bold" title="Not Null">NN</span>' : ''}
                                                    </div>
                                                </div>
                                                <div class="text-xs text-gray-500 mt-1">${col.type}</div>
                                            </div>
                                        `).join('')}
                                    </div>
                                </div>
                            </div>
                        `;
                    });
                    
                    tablesList.innerHTML = tablesHTML;
                } else {
                    databaseInfo.classList.remove('hidden');
                    tablesList.innerHTML = `<p class="text-blue-700 p-4 bg-blue-50 rounded-lg">${data.error || 'No tables found in this database'}</p>`;
                }
            } catch (error) {
                console.error('Error loading database info:', error);
                const databaseInfo = document.getElementById('databaseInfo');
                const tablesList = document.getElementById('tablesList');
                databaseInfo.classList.remove('hidden');
                tablesList.innerHTML = '<p class="text-red-700 p-4 bg-red-50 rounded-lg">Error loading database schema information. Check console for details.</p>';
            }
        }
        
        // Handle custom database connection with better error handling
        document.getElementById('connectCustomDb').addEventListener('click', async function() {
            const server = document.getElementById('customServer').value;
            const database = document.getElementById('customDatabase').value;
            const username = document.getElementById('customUsername').value;
            const password = document.getElementById('customPassword').value;
            const port = document.getElementById('customPort').value;
            const dbType = document.querySelector('input[name="dbType"]:checked').value;
            
            if (!server) {
                alert('Please enter server address');
                return;
            }
            
            if (!username) {
                alert('Please enter username');
                return;
            }
            
            if (!password) {
                alert('Please enter password');
                return;
            }
            
            const connectBtn = document.getElementById('connectCustomDb');
            const originalText = connectBtn.innerHTML;
            
            try {
                // Show loading state
                connectBtn.disabled = true;
                connectBtn.innerHTML = '<i class="fas fa-spinner fa-spin mr-2"></i>Connecting...';
                
                // Store the password securely for future use
                originalPassword = password;
                
                // Add timeout to fetch request
                const controller = new AbortController();
                const timeoutId = setTimeout(() => controller.abort(), 30000); // 30 second timeout
                
                const response = await fetch('/api/connect-custom', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        server: server,
                        database: database,
                        db_type: dbType,
                        username: username,
                        password: password,
                        port: port
                    }),
                    signal: controller.signal
                });
                
                clearTimeout(timeoutId);
                
                // Check if response is JSON
                const contentType = response.headers.get('content-type');
                if (!contentType || !contentType.includes('application/json')) {
                    const text = await response.text();
                    console.error('Non-JSON response:', text.substring(0, 500));
                    throw new Error('Server returned an error page. Check database credentials and connection details.');
                }
                
                const data = await response.json();
                console.log('Custom connection response:', data);
                
                if (data.success) {
                    // Store connection info for future queries
                    currentConnectionInfo = {
                        server: server,
                        db_type: dbType,
                        username: username,
                        password: password, // Store the password
                        port: port || (dbType === 'mysql' ? '3306' : '1433')
                    };
                    
                    if (data.available_databases && data.available_databases.length > 0) {
                        showDatabaseSelection(data.available_databases, server, dbType, data);
                        alert('✅ Connection successful! Please select a database from the list below.');
                    } else if (data.database) {
                        selectDatabase(data.database, true, data.server_info);
                        alert('✅ Connection successful! Database selected.');
                    } else {
                        alert('✅ Connected successfully but no databases found or selected.');
                    }
                    
                    // Clear password field for security (but we have it stored in currentConnectionInfo)
                    document.getElementById('customPassword').value = '';
                    
                } else {
                    alert('❌ Failed to connect: ' + (data.error || 'Unknown error'));
                }
            } catch (error) {
                console.error('Connection error:', error);
                
                if (error.name === 'AbortError') {
                    alert('❌ Connection timeout: The database server took too long to respond. Please check the server address and try again.');
                } else if (error.message.includes('JSON')) {
                    alert('❌ Connection error: The database server returned an unexpected response. Please check your credentials and connection details.');
                } else {
                    alert('❌ Connection error: ' + error.message);
                }
            } finally {
                // Restore button state
                connectBtn.disabled = false;
                connectBtn.innerHTML = '<i class="fas fa-link mr-2"></i>Connect to Custom Database';
            }
        });
    
        // Handle form submission
        document.getElementById('queryForm').addEventListener('submit', async function(e) {
            e.preventDefault();
            if (!currentDatabase) {
                alert('Please select a database first');
                return;
            }
            await processQuery(document.getElementById('query').value, currentDatabase);
        });
    
        // Handle example buttons
        document.querySelectorAll('.example-btn').forEach(btn => {
            btn.addEventListener('click', function() {
                if (!currentDatabase) {
                    alert('Please select a database first');
                    return;
                }
                document.getElementById('query').value = this.textContent.trim();
                processQuery(this.textContent.trim(), currentDatabase);
            });
        });
    
        // Clear history
        document.getElementById('clearHistory').addEventListener('click', function() {
            sessionId = 'session_' + Math.random().toString(36).substr(2, 9);
            document.getElementById('historySection').classList.add('hidden');
            document.getElementById('historyList').innerHTML = '';
            // Also clear connection info when clearing history
            currentConnectionInfo = null;
            originalPassword = null;
        });
    
        async function processQuery(query, database) {
            const button = document.querySelector('#queryForm button');
            const resultsDiv = document.getElementById('results');
            
            // Show loading state
            button.disabled = true;
            button.innerHTML = '<i class="fas fa-spinner fa-spin mr-2"></i>Generating SQL with Gemini...';
            resultsDiv.classList.add('hidden');
            
            try {
                const requestBody = { 
                    query: query,
                    database: database,
                    session_id: sessionId 
                };
                
                // Add custom connection info if available - FIXED: Always include password
                if (currentConnectionInfo) {
                    requestBody.custom_connection = {
                        server: currentConnectionInfo.server,
                        db_type: currentConnectionInfo.db_type,
                        username: currentConnectionInfo.username,
                        password: currentConnectionInfo.password, // CRITICAL: Include password
                        port: currentConnectionInfo.port
                    };
                }
                
                const response = await fetch('/api/query', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify(requestBody)
                });
                
                const data = await response.json();
                console.log('Query response:', data);
                
                if (data.success) {
                    displaySuccessResults(data);
                    addToHistory(query, data, database);
                } else {
                    displayError(data.error);
                }
                
            } catch (error) {
                console.error('Query error:', error);
                displayError('Network error: ' + error.message);
            } finally {
                button.disabled = false;
                button.innerHTML = '<i class="fas fa-paper-plane mr-2"></i>Generate & Execute SQL';
            }
        }
    
        function displaySuccessResults(data) {
            // ... existing code ...
        }
    
        function renderResultsTable(data, columns) {
            // ... existing code ...
        }
    
        function displayError(error) {
            // ... existing code ...
        }
    
        function addToHistory(query, data, database) {
            // ... existing code ...
        }
    
        function copyToClipboard(text) {
            // ... existing code ...
        }
    
        // Initialize when DOM is fully loaded
        document.addEventListener('DOMContentLoaded', function() {
            console.log('DOM fully loaded, initializing SQL Query Assistant...');
            setTimeout(() => {
                checkSystemStatus();
            }, 100);
        });
    </script>
</body>
</html>
'''

@app.route('/')
def home():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/health')
def health():
    """Health check endpoint for Render"""
    try:
        db_connected = db_connector.test_connection()
    except Exception as e:
        logger.error(f"Database connection test failed: {e}")
        db_connected = False
    
    # Test Gemini connection
    gemini_connected = False
    try:
        # Simple test to check if Gemini is configured
        gemini_connected = gemini_client.is_initialized()
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

@app.route('/api/databases')
def get_databases():
    """Get list of all available databases"""
    try:
        result = db_connector.get_databases()
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error getting databases: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "databases": config.DEFAULT_DATABASES
        }), 500

@app.route('/api/databases/<database>/tables', methods=['POST'])
def get_tables_with_columns(database):
    """Get tables for a specific database with column information"""
    try:
        data = request.get_json()
        is_custom = data.get('is_custom', False)
        custom_connection = data.get('custom_connection')
        
        logger.info(f"Getting tables for {database}, custom: {is_custom}")
        
        if custom_connection:
            # Use provided custom connection
            logger.info(f"Using provided custom connection for tables - Password provided: {bool(custom_connection.get('password'))}")
            temp_connector = DatabaseConnector(
                database=database,
                db_type=custom_connection.get('db_type', 'mysql'),
                custom_config={
                    'server': custom_connection.get('server'),
                    'user': custom_connection.get('username'),
                    'password': custom_connection.get('password'),  # CRITICAL: Include password
                    'port': custom_connection.get('port', '3306')
                }
            )
            result = temp_connector.get_detailed_tables_info(database)
        elif is_custom and database in custom_connections:
            # Use stored custom connection
            connection_info = custom_connections[database]
            logger.info(f"Using stored custom connection for tables - Password provided: {bool(connection_info.get('password'))}")
            temp_connector = DatabaseConnector(
                database=database,
                db_type=connection_info.get('db_type', 'mysql'),
                custom_config={
                    'server': connection_info.get('server'),
                    'user': connection_info.get('username'),
                    'password': connection_info.get('password'),  # CRITICAL: Include password
                    'port': connection_info.get('port', '3306')
                }
            )
            result = temp_connector.get_detailed_tables_info(database)
        else:
            # Use default connection
            result = db_connector.get_detailed_tables_info(database)
        
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error getting tables for {database}: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/register-custom-db', methods=['POST'])
def register_custom_database():
    """Register a custom database connection"""
    try:
        data = request.get_json()
        database = data.get('database')
        connection_info = data.get('connection_info')
        
        if not database or not connection_info:
            return jsonify({"success": False, "error": "Database and connection info are required"}), 400
        
        custom_connections[database] = connection_info
        logger.info(f"Registered custom database: {database} with server: {connection_info.get('server')}")
        
        return jsonify({"success": True, "message": f"Custom database {database} registered"})
    except Exception as e:
        logger.error(f"Error registering custom database: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/connect-custom', methods=['POST'])
def connect_custom_database():
    """Connect to a custom database"""
    try:
        data = request.get_json()
        server = data.get('server', '').strip()
        database = data.get('database', '').strip()
        db_type = data.get('db_type', 'mysql')
        username = data.get('username', '').strip()
        password = data.get('password', '').strip()
        port = data.get('port', '').strip()
        
        logger.info(f"Custom connection attempt: {server} (Type: {db_type}, DB: {database}, Port: {port})")
        
        if not server:
            return jsonify({"success": False, "error": "Server address is required"}), 400
        if not username:
            return jsonify({"success": False, "error": "Username is required"}), 400
        if not password:
            return jsonify({"success": False, "error": "Password is required"}), 400
        
        # Set default port if not provided
        if not port:
            port = '4000' if 'tidbcloud' in server.lower() else '3306'
        
        custom_config = {
            'server': server,
            'user': username,
            'password': password,
            'port': port
        }
        
        # Test connection without specific database first
        try:
            temp_connector = DatabaseConnector(
                database=None,  # Connect without specific database first
                db_type=db_type,
                custom_config=custom_config
            )
            
            if temp_connector.test_connection():
                # Get available databases
                db_result = temp_connector.get_databases()
                
                if db_result['success']:
                    # Store connection info for all available databases
                    for db_name in db_result['databases']:
                        custom_connections[db_name] = {
                            'server': server,
                            'db_type': db_type,
                            'username': username,
                            'password': password,
                            'port': port
                        }
                    
                    # If a specific database was provided, test connection to it
                    specific_db_success = False
                    if database and database in db_result['databases']:
                        try:
                            specific_connector = DatabaseConnector(
                                database=database,
                                db_type=db_type,
                                custom_config=custom_config
                            )
                            specific_db_success = specific_connector.test_connection()
                        except Exception as specific_error:
                            logger.error(f"Specific database connection failed: {specific_error}")
                            specific_db_success = False
                    
                    return jsonify({
                        "success": True,
                        "message": f"Successfully connected to {server}",
                        "database": database if specific_db_success else None,
                        "db_type": db_type,
                        "available_databases": db_result['databases'],
                        "server_info": f"{server}:{port}"
                    })
                else:
                    return jsonify({
                        "success": True,
                        "message": f"Connected to server but could not list databases: {db_result.get('error', 'Unknown error')}",
                        "database": None,
                        "db_type": db_type,
                        "available_databases": [],
                        "server_info": f"{server}:{port}"
                    })
            else:
                return jsonify({
                    "success": False,
                    "error": f"Failed to connect to server {server}. Please check credentials and ensure the server allows connections from Render."
                }), 400
                
        except Exception as conn_error:
            logger.error(f"Connection error details: {str(conn_error)}")
            return jsonify({
                "success": False, 
                "error": f"Connection failed: {str(conn_error)}"
            }), 400
            
    except Exception as e:
        logger.error(f"Custom connection error: {str(e)}")
        return jsonify({
            "success": False, 
            "error": f"Connection failed: {str(e)}"
        }), 500

@app.route('/api/test-connection', methods=['POST'])
def test_connection():
    """Simple connection test endpoint"""
    try:
        data = request.get_json()
        # Simple test that returns quickly
        return jsonify({
            "success": True,
            "message": "Connection test endpoint working"
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/api/query', methods=['POST'])
def handle_query():
    start_time = datetime.utcnow()
    
    try:
        data = request.get_json()
        query = data.get('query', '').strip()
        database = data.get('database')
        session_id = data.get('session_id', 'default')
        custom_connection = data.get('custom_connection')
        
        if not query:
            return jsonify({"success": False, "error": "Query is required"}), 400
        
        if not database:
            return jsonify({"success": False, "error": "Database selection is required"}), 400
        
        logger.info(f"Processing query for database {database}: {query}")
        
        # Determine which connector to use
        current_connector = None
        
        if custom_connection:
            # Use provided custom connection (from frontend)
            logger.info(f"Using provided custom connection for {database}")
            logger.info(f"Custom connection details - Server: {custom_connection.get('server')}, User: {custom_connection.get('username')}, Password provided: {bool(custom_connection.get('password'))}")
            
            current_connector = DatabaseConnector(
                database=database,
                db_type=custom_connection.get('db_type', 'mysql'),
                custom_config={
                    'server': custom_connection.get('server'),
                    'user': custom_connection.get('username'),
                    'password': custom_connection.get('password'),  # CRITICAL: Make sure password is included
                    'port': custom_connection.get('port', '3306')
                }
            )
        elif database in custom_connections:
            # Use stored custom connection
            connection_info = custom_connections[database]
            logger.info(f"Using stored custom connection for {database}")
            logger.info(f"Stored connection details - Server: {connection_info.get('server')}, User: {connection_info.get('username')}, Password provided: {bool(connection_info.get('password'))}")
            
            current_connector = DatabaseConnector(
                database=database,
                db_type=connection_info.get('db_type', 'mysql'),
                custom_config={
                    'server': connection_info.get('server'),
                    'user': connection_info.get('username'),
                    'password': connection_info.get('password'),  # CRITICAL: Make sure password is included
                    'port': connection_info.get('port', '3306')
                }
            )
        else:
            # Use the default connector
            logger.info(f"Using default connector for {database}")
            db_connector.set_database(database)
            current_connector = db_connector
        
        # Test the connection first
        logger.info("Testing database connection...")
        if not current_connector.test_connection():
            return jsonify({
                "success": False,
                "error": f"Failed to connect to database {database}. Please check connection details."
            }), 500
        
        logger.info("Database connection test successful, generating SQL with Gemini...")
        
        # Generate SQL query using Gemini - pass the current_connector
        llm_result = gemini_client.generate_sql_query(
            query, 
            current_connector,  # Pass the actual connector we're using
            database
        )
        
        if not llm_result['success']:
            return jsonify({
                "success": False,
                "error": llm_result['error']
            }), 500
        
        generated_sql = llm_result['sql_query']
        logger.info(f"Generated SQL: {generated_sql}")
        
        # Execute the query
        logger.info("Executing SQL query...")
        execution_result = current_connector.execute_query(generated_sql)
        
        if not execution_result['success']:
            return jsonify({
                "success": False,
                "error": f"SQL execution failed: {execution_result['error']}",
                "generated_sql": generated_sql
            }), 500
        
        # Prepare results summary for explanation
        results_summary = {
            'row_count': execution_result['row_count'],
            'columns': execution_result['columns'],
            'sample_data': execution_result['data'][:3] if execution_result['data'] else []
        }
        
        # Generate explanation
        explanation = gemini_client.explain_query_results(
            query, 
            json.dumps(results_summary),
            database
        )
        
        # Update conversation history
        history_key = f"{session_id}_{database}"
        if history_key not in conversation_history:
            conversation_history[history_key] = []
        
        conversation_history[history_key].append({
            'query': query,
            'sql': generated_sql,
            'timestamp': datetime.utcnow().isoformat()
        })
        
        if len(conversation_history[history_key]) > 10:
            conversation_history[history_key] = conversation_history[history_key][-10:]
        
        execution_time_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
        
        return jsonify({
            "success": True,
            "natural_language_query": query,
            "generated_sql": generated_sql,
            "explanation": explanation,
            "execution_result": {
                "success": True,
                "data": execution_result['data'],
                "row_count": execution_result['row_count'],
                "columns": execution_result['columns']
            },
            "execution_time_ms": round(execution_time_ms, 2),
            "model_used": llm_result['model_used'],
            "database": database,
            "session_id": session_id
        })
        
    except Exception as e:
        logger.error(f"Error processing query: {str(e)}")
        return jsonify({
            "success": False,
            "error": f"Server error: {str(e)}"
        }), 500

@app.route('/api/schema/<database>')
def get_schema(database):
    """Get database schema information"""
    try:
        result = db_connector.get_detailed_tables_info(database)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error fetching schema for {database}: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/clear-cache', methods=['POST'])
def clear_cache():
    """Clear Gemini schema cache"""
    try:
        gemini_client.clear_schema_cache()
        return jsonify({"success": True, "message": "Cache cleared"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    logger.info(f"🚀 Starting Multi-Database SQL Assistant on port {port}")
    logger.info(f"📊 Default databases: {config.DEFAULT_DATABASES}")
    logger.info(f"🔗 Database server: {config.DB_SERVER}:{config.DB_PORT}")
    app.run(host='0.0.0.0', port=port, debug=False)
