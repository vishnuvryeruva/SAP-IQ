import boto3
import subprocess
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash, send_from_directory
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

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize OpenAI client
client = OpenAI(api_key=OPENAI_API_KEY)

# Custom system message for the assistant
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

# SAP-specific knowledge base
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

app = Flask(__name__, static_folder='static')
app.secret_key = 'your_secret_key'  # Replace with your secret key

# Constants
UPLOAD_FOLDER = 'uploads'
STATIC_FOLDER = 'static'
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'doc', 'docx'}
ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'svg'}
MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size
CONVERSATION_LENGTH = 10
ASSISTANT_ID = "asst_D8x26bB9HstXP5EaqiI5ejaX"  # Your assistant ID

# Configure app
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH

# Create required folders
for folder in [UPLOAD_FOLDER, STATIC_FOLDER]:
    if not os.path.exists(folder):
        os.makedirs(folder)

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
    if module in SAP_KNOWLEDGE:
        return SAP_KNOWLEDGE[module]
    return None

@app.route('/')
def index():
    if 'username' not in session:
        return redirect(url_for('login'))
    return redirect(url_for('module', module_name='home'))

@app.route('/module/<module_name>')
def module(module_name):
    if 'username' not in session:
        return redirect(url_for('login'))
    
    # Validate module name
    valid_modules = ['home', 'fico', 'mm', 'sd', 'pp', 'hcm', 'ewm']
    if module_name.lower() not in valid_modules:
        return redirect(url_for('module', module_name='home'))
    
    return render_template('index.html', 
                         current_module=module_name,
                         conversation_history=get_module_conversation(module_name))

@app.route('/action/<action_name>')
def action(action_name):
    if 'username' not in session:
        return redirect(url_for('login'))
    
    if action_name == 'new_chat':
        module = request.args.get('module', 'home')
        if module in conversation_history:
            conversation_history[module].clear()
        return redirect(url_for('module', module_name=module))
    
    elif action_name == 'settings':
        return render_template('settings.html')
    
    return redirect(url_for('index'))

@app.route('/api/module/<module_name>/history')
def get_module_history(module_name):
    if 'username' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    history = list(get_module_conversation(module_name))
    return jsonify({'history': history})

@app.route('/api/module/<module_name>/clear', methods=['POST'])
def clear_module_history(module_name):
    if 'username' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    if module_name in conversation_history:
        conversation_history[module_name].clear()
        return jsonify({'success': True})
    return jsonify({'error': 'Module not found'}), 404

@app.route("/api/module/<module_name>/answer", methods=["POST"])
def module_answer(module_name):
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
                    assistant_id=ASSISTANT_ID,
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
        # Add your authentication logic here
        if username == 'admin' and password == 'password':  # Replace with proper authentication
            session['username'] = username
            return jsonify({'success': True})
        return jsonify({'success': False, 'message': 'Invalid credentials'})
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
        return jsonify({'error': 'No file provided'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    if file and allowed_file(file.filename):
        try:
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)

            # Analyze document
            content = analyze_sap_document(file_path)
            if content:
                # Add document content to conversation context
                get_module_conversation(module_name='home').append({
                    'role': 'system',
                    'content': f"Document uploaded: {filename}\nContent: {content[:1000]}..."  # Truncate long documents
                })
                save_conversation_to_file(get_module_conversation(module_name='home'), 'conversation_history.txt')

                # Add a welcome message to guide the user
                welcome_message = (
                    f"I've analyzed the document '{filename}'. You can now ask me questions about its contents. "
                    "For example:\n"
                    "- What are the main topics covered in this document?\n"
                    "- Can you explain the technical requirements?\n"
                    "- What BADIs or function modules are mentioned?"
                )
                
                get_module_conversation(module_name='home').append({
                    'role': 'assistant',
                    'content': welcome_message
                })
                save_conversation_to_file(get_module_conversation(module_name='home'), 'conversation_history.txt')

                return jsonify({
                    'success': True, 
                    'message': 'File uploaded successfully',
                    'systemMessage': welcome_message
                })

            return jsonify({
                'success': True,
                'message': 'File uploaded successfully',
                'systemMessage': f"Document '{filename}' has been uploaded successfully. However, I couldn't analyze its contents. Please make sure it's a text-based document."
            })

        except Exception as e:
            logger.error(f"Error uploading file: {e}")
            return jsonify({'error': str(e)}), 500

    return jsonify({'error': 'File type not allowed. Please upload a .txt, .pdf, .doc, or .docx file.'}), 400

@app.route('/clear_history', methods=['POST'])
def clear_history():
    if 'username' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    try:
        for module in conversation_history:
            conversation_history[module].clear()
        if os.path.exists('conversation_history.txt'):
            os.remove('conversation_history.txt')
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Error clearing history: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == "__main__":
    # Load conversation history on startup
    for module in conversation_history:
        conversation_history[module] = load_conversation_from_file(f'{module}_conversation_history.txt')
    app.run(debug=True)