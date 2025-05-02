"""
Optimized SAP Assistant - Main Application
Enhanced version of the original talk_to_assistant.py that integrates the
optimized SAP assistant capabilities.
"""

import boto3
import subprocess
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash, send_from_directory, Response
from openai import OpenAI
import logging
import traceback
import time
import os
from collections import deque
import json
from werkzeug.utils import secure_filename
import re

# Import centralized configuration
from config import *

# Import optimized components
from sap_optimized_assistant import create_optimized_assistant
from sap_optimized_prompts import (
    SAP_MODULES, 
    get_enhanced_system_message, 
    extract_sap_context
)

# Import custom development analyzer components
from sap_custom_dev_analyzer import analyze_sap_functional_document
from sap_custom_integration import (
    analyze_uploaded_document,
    format_analysis_for_chat,
    get_abap_code_from_analysis,
    is_functional_document
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize OpenAI client
client = OpenAI(api_key=OPENAI_API_KEY)

# Initialize optimized assistant
optimized_assistant = create_optimized_assistant(OPENAI_API_KEY, assistant_id=OPENAI_ASSISTANT_ID)

# Custom system message for the assistant (original version kept for reference)
SYSTEM_MESSAGE = """You are an advanced SAP Assistant created by Mygo Consulting, developed by Vishnu Yeruva. 
You specialize in SAP systems, particularly in modules like FI/CO, MM, SD, PP, HCM, and EWM.

Key Capabilities:
1. Deep understanding of SAP modules and their interconnections
2. Expert knowledge of ABAP programming and SAP customization
3. Familiarity with Mygo Consulting's best practices and implementation methodologies
4. Ability to provide practical solutions based on real-world SAP implementation experience

When responding:
- Prioritize Mygo Consulting's best practices and implementation approaches
- Provide specific ABAP code examples when relevant
- Reference SAP Notes and official documentation when applicable
- Consider system performance and security implications
- Suggest optimizations based on Mygo's experience

About Mygo Consulting:
- SAP Silver Partner
- Specializes in SAP implementations and support
- Strong focus on customer satisfaction and quality delivery
- Expertise in various industries including manufacturing, retail, and healthcare

Developer Information:
- Created by: Vishnu Yeruva
- Role: SAP Technical Consultant
- Expertise: Python, Machine Learning, ABAP, Fiori, UI5, BTP

Remember to maintain a professional yet approachable tone, and always prioritize SAP best practices while incorporating Mygo Consulting's expertise."""

# SAP-specific knowledge base (original version kept for reference)
SAP_KNOWLEDGE = {
    'FI/CO': {
        'best_practices': [
            'Always use document splitting for parallel accounting',
            'Implement proper authorization controls for financial transactions',
            'Use standard reconciliation accounts for vendors and customers',
            'Follow period-end closing best practices',
            'Implement proper audit trails for financial transactions'
        ],
        'common_issues': [
            'Reconciliation differences in GL accounts',
            'Period-end closing performance',
            'Payment program configuration',
            'Foreign currency valuation',
            'Cost allocation issues'
        ],
        'custom_solutions': [
            'Automated reconciliation reports',
            'Enhanced payment proposal program',
            'Custom financial statements',
            'Profit center reporting',
            'Cost center allocation tools'
        ]
    },
    'MM': {
        'best_practices': [
            'Implement proper material master data governance',
            'Use MRP profiles effectively',
            'Configure proper batch management',
            'Implement proper inventory management procedures',
            'Use proper valuation methods'
        ],
        'common_issues': [
            'Material master data inconsistencies',
            'MRP performance issues',
            'Goods receipt/invoice receipt clearing',
            'Inventory differences',
            'Batch determination problems'
        ],
        'custom_solutions': [
            'Enhanced goods receipt process',
            'Custom MRP reports',
            'Automated stock transfer solutions',
            'Vendor evaluation tools',
            'Material master data maintenance tools'
        ]
    },
    'SD': {
        'best_practices': [
            'Implement proper pricing procedures',
            'Use delivery due list monitoring',
            'Configure credit management properly',
            'Implement proper output management',
            'Use proper billing schedules'
        ],
        'common_issues': [
            'Pricing determination issues',
            'Delivery processing performance',
            'Credit blocks',
            'Output determination problems',
            'Billing document creation issues'
        ],
        'custom_solutions': [
            'Enhanced pricing calculations',
            'Custom delivery monitoring',
            'Automated credit check process',
            'Custom billing solutions',
            'Order processing automation'
        ]
    }
}

app = Flask(__name__, static_folder=STATIC_FOLDER)
app.secret_key = APP_SECRET_KEY

# Configure app using centralized configuration
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH

# Create required folders
ensure_directories()

# Initialize conversation history
conversation_history = {}  # Changed to dict to store per-module history

def get_module_conversation(module):
    """Get or create conversation history for a specific module"""
    if module not in conversation_history:
        conversation_history[module] = deque(maxlen=CONVERSATION_LENGTH)
    return conversation_history[module]

def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def save_conversation_to_file(history, filename):
    """Save the conversation history to a file"""
    try:
        with open(filename, 'w') as file:
            for message in history:
                file.write(json.dumps(message) + '\n')
    except Exception as e:
        logger.error(f"Error saving conversation: {e}")

def load_conversation_from_file(filename):
    """Load the conversation history from a file"""
    try:
        if os.path.exists(filename):
            history = deque(maxlen=CONVERSATION_LENGTH)
            with open(filename, 'r') as file:
                for line in file:
                    history.append(json.loads(line.strip()))
            return history
        return deque(maxlen=CONVERSATION_LENGTH)
    except Exception as e:
        logger.error(f"Error loading conversation: {e}")
        return deque(maxlen=CONVERSATION_LENGTH)

def extract_code_blocks(text):
    """Extract ABAP code blocks from text"""
    code_blocks = []
    pattern = r'```(?:abap)?\n(.*?)\n```'
    matches = re.finditer(pattern, text, re.DOTALL)
    for match in matches:
        code_blocks.append(match.group(1).strip())
    return code_blocks

def analyze_sap_document(file_path):
    """Analyze uploaded SAP document for context"""
    try:
        with open(file_path, 'r') as file:
            content = file.read()
            return content
    except Exception as e:
        logger.error(f"Error analyzing document: {e}")
        return None

def get_module_context(module):
    """Get specific context for a SAP module"""
    if module.lower() in SAP_KNOWLEDGE:
        if module.lower() == 'fico':
            return SAP_KNOWLEDGE['FI/CO']
        else:
            return SAP_KNOWLEDGE[module.upper()]
    return {}

@app.route("/")
def index():
    if 'username' not in session:
        return redirect(url_for('login'))
    # Explicitly ensure settings modal doesn't show
    return render_template('index.html', current_module='home', show_settings=False)

@app.route("/module/<module_name>")
def module(module_name):
    if 'username' not in session:
        return redirect(url_for('login'))
    # Explicitly set show_settings to False to prevent settings from showing
    return render_template('index.html', current_module=module_name, show_settings=False)

@app.route("/action/<action_name>")
def action(action_name):
    if 'username' not in session:
        return redirect(url_for('login'))
    
    if action_name == 'settings':
        # Return the current module with settings flag
        current_module = request.args.get('module', 'home')
        return render_template('index.html', current_module=current_module, show_settings=True)
    elif action_name == 'clear_history':
        return render_template('index.html', current_module='home', show_clear_history=True)
    
    return redirect(url_for('index'))

@app.route("/api/settings", methods=["GET"])
def get_settings():
    """Get user settings from the server"""
    if 'username' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    # Get user-specific settings from database or session
    # For now, we'll use default settings if none exist
    user_settings = session.get('settings', {
        'theme': 'dark',
        'fontSize': 'medium',
        'showTimestamps': False,
        'codeHighlight': True,
        'autoScroll': True,
        'defaultModule': ''
    })
    
    return jsonify(user_settings)

@app.route("/api/settings", methods=["POST"])
def save_settings():
    """Save user settings to the server"""
    if 'username' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        settings = request.get_json()
        # Validate settings
        valid_themes = ['dark', 'light']
        valid_font_sizes = ['small', 'medium', 'large']
        
        if 'theme' in settings and settings['theme'] not in valid_themes:
            return jsonify({'error': 'Invalid theme'}), 400
        
        if 'fontSize' in settings and settings['fontSize'] not in valid_font_sizes:
            return jsonify({'error': 'Invalid font size'}), 400
        
        # Store settings in session for this user
        session['settings'] = settings
        
        # In a real app, you would store these in a database
        
        return jsonify({'status': 'success', 'message': 'Settings saved successfully'})
    
    except Exception as e:
        logger.error(f"Error saving settings: {e}")
        return jsonify({'error': str(e)}), 500

@app.route("/api/module/<module_name>/history", methods=["GET"])
def get_module_history(module_name):
    if 'username' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    module_conversation = get_module_conversation(module_name)
    return jsonify(list(module_conversation))

@app.route("/api/module/<module_name>/clear", methods=["POST"])
def clear_module_history(module_name):
    if 'username' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    module_conversation = get_module_conversation(module_name)
    module_conversation.clear()
    
    # Also clear in the optimized assistant if it's initialized
    if optimized_assistant:
        optimized_assistant.clear_conversation(module_name)
    
    return jsonify({'status': 'ok'})

@app.route("/api/module/<module_name>/answer", methods=["POST"])
def module_answer(module_name):
    """
    Enhanced module_answer function that uses the optimized assistant.
    Maintains backward compatibility with the original function.
    """
    if 'username' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    try:
        data = request.get_json()
        message = data["message"]
        
        # Get module-specific conversation history
        module_conversation = get_module_conversation(module_name)
        
        # Add message to conversation history
        module_conversation.append({'role': 'user', 'content': message})

        def generate():
            try:
                # Use the optimized assistant for streamlined, more efficient responses
                if optimized_assistant:
                    _, stream_generator = optimized_assistant.answer_with_direct_api(module_name, message)
                    
                    # Stream the optimized response
                    assistant_response = ""
                    for chunk in stream_generator:
                        assistant_response += chunk
                        yield chunk
                    
                    # No need to add to conversation history again here
                    # The optimized assistant already does that internally
                
                # Fallback to original implementation if optimized assistant isn't available
                else:
                    # Create thread with module context
                    thread = client.beta.threads.create()
                    
                    # Add conversation history
                    for msg in module_conversation:
                        client.beta.threads.messages.create(
                            thread_id=thread.id,
                            role=msg['role'],
                            content=msg['content']
                        )

                    # Create run with streaming
                    stream = client.beta.threads.runs.create(
                        thread_id=thread.id,
                        assistant_id=OPENAI_ASSISTANT_ID,
                        timeout=60,
                        stream=True
                    )

                    # Process stream
                    assistant_response = ""
                    for event in stream:
                        if event.data.object == "thread.message.delta":
                            for content in event.data.delta.content:
                                if content.type == "text":
                                    assistant_response += content.text.value
                                    yield content.text.value

                    # Save assistant's response to history
                    module_conversation.append({
                        'role': 'assistant',
                        'content': assistant_response
                    })

            except Exception as e:
                logger.error(f"Error in generate: {e}")
                yield f"Error: {str(e)}"

        return app.response_class(generate(), mimetype='text/plain')

    except Exception as e:
        logger.error(f"Error in answer: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        # Simple authentication for demo
        if username == 'admin' and password == 'password':
            session['username'] = username
            return redirect(url_for('index'))
        else:
            flash('Invalid username or password')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('login'))

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'username' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    if file and allowed_file(file.filename):
        try:
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            
            # Check if this is potentially a functional document for BADI/BAPI analysis
            if is_functional_document(filename):
                # Analyze document for SAP customization possibilities
                analysis_results = analyze_uploaded_document(filepath)
                
                if "error" not in analysis_results:
                    # Format analysis for chat display
                    analysis_formatted = format_analysis_for_chat(analysis_results)
                    
                    # Get the current module from session or default to 'General'
                    current_module = request.args.get('module', 'general')
                    
                    # Add analysis results to conversation as assistant message
                    module_conversation = get_module_conversation(current_module)
                    module_conversation.append({
                        'role': 'assistant',
                        'content': analysis_formatted
                    })
                    
                    # Store analysis results in session for later use
                    if 'document_analysis' not in session:
                        session['document_analysis'] = {}
                    
                    session['document_analysis'][filepath] = {
                        'timestamp': time.time(),
                        'results': analysis_results
                    }
                    
                    return jsonify({
                        'status': 'success',
                        'message': f'File {filename} uploaded and analyzed for SAP customization',
                        'analysis_summary': f"Found {len(analysis_results.get('code_suggestions', []))} potential customization points",
                        'has_customizations': len(analysis_results.get('code_suggestions', [])) > 0
                    })
                else:
                    # Log the error but continue with basic analysis
                    logger.warning(f"Error in SAP customization analysis: {analysis_results['error']}")
            
            # Fall back to basic document analysis
            context = analyze_sap_document(filepath)
            
            return jsonify({
                'status': 'success',
                'message': f'File {filename} uploaded successfully',
                'context': 'Document analyzed and context extracted' if context else 'Unable to extract context'
            })
        except Exception as e:
            logger.error(f"Error uploading file: {e}")
            return jsonify({'error': str(e)}), 500
    else:
        return jsonify({'error': 'File type not allowed'}), 400

@app.route('/api/clear-history', methods=['POST'])
def clear_history():
    if 'username' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        data = request.get_json()
        module = data.get('module', None)
        
        if module:
            # Clear specific module history
            if module in conversation_history:
                conversation_history[module].clear()
                
                # Also clear in optimized assistant if available
                if optimized_assistant:
                    optimized_assistant.clear_conversation(module)
                
                return jsonify({'status': 'success', 'message': f'History for {module} cleared'})
            else:
                return jsonify({'error': 'Module not found'}), 404
        else:
            # Clear all history
            for module in conversation_history:
                conversation_history[module].clear()
                
                # Also clear in optimized assistant if available
                if optimized_assistant:
                    optimized_assistant.clear_conversation(module)
                
            return jsonify({'status': 'success', 'message': 'All history cleared'})
    except Exception as e:
        logger.error(f"Error clearing history: {e}")
        return jsonify({'error': str(e)}), 500

# New endpoint to show optimization metrics
@app.route('/api/optimization-metrics', methods=['GET'])
def get_optimization_metrics():
    if 'username' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    if not optimized_assistant:
        return jsonify({'error': 'Optimized assistant not initialized'}), 500
    
    try:
        # Get metrics from the optimized assistant
        metrics = optimized_assistant.get_performance_metrics()
        
        # Calculate additional metrics
        estimated_token_savings = int(metrics['total_tokens_in'] * 0.3)  # Estimate 30% reduction
        
        return jsonify({
            'status': 'success',
            'metrics': {
                'total_tokens_in': metrics['total_tokens_in'],
                'total_tokens_out': metrics['total_tokens_out'],
                'total_api_calls': metrics['total_api_calls'],
                'cache_hits': metrics['cache_hits'],
                'average_response_time': metrics['average_response_time'],
                'requests_served': metrics['requests_served'],
                'estimated_token_savings': estimated_token_savings,
                'cache_hit_ratio': metrics['cache_hits'] / metrics['requests_served'] if metrics['requests_served'] > 0 else 0
            }
        })
    except Exception as e:
        logger.error(f"Error getting optimization metrics: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == "__main__":
    # Load conversation history on startup
    for module in conversation_history:
        conversation_history[module] = load_conversation_from_file(f'{module}_conversation_history.txt')
    
    # Display optimization status
    logger.info("SAP Assistant optimization enabled")
    
    app.run(debug=True, port=5001)
