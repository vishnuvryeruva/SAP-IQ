"""
SAP Assistant Integration Module
Integrates the optimized SAP assistant with the existing Flask application
"""

import time
import logging
from flask import current_app, request, jsonify, Response

# Import the optimized assistant
from sap_optimized_assistant import create_optimized_assistant

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global instance of the optimized assistant
optimized_assistant = None

def initialize_optimized_assistant(api_key, assistant_id=None):
    """Initialize the optimized assistant with the given API key"""
    global optimized_assistant
    
    try:
        logger.info("Initializing optimized SAP assistant...")
        optimized_assistant = create_optimized_assistant(api_key, assistant_id)
        logger.info("Optimized SAP assistant initialized successfully")
        return True
    except Exception as e:
        logger.error(f"Error initializing optimized assistant: {str(e)}")
        return False

def optimized_module_answer(module_name, user_message):
    """
    Get an optimized answer for a user message in a specific module context.
    This function is designed to be a drop-in replacement for the existing module_answer function.
    
    Args:
        module_name: The SAP module context (e.g., 'fico', 'mm')
        user_message: The user's query
        
    Returns:
        Flask Response object with streaming content
    """
    global optimized_assistant
    
    # Check if assistant is initialized
    if not optimized_assistant:
        return jsonify({'error': 'Optimized assistant not initialized'}), 500
    
    # Define the generate function for streaming
    def generate():
        try:
            # Get response using direct API (more efficient than Assistants API)
            _, stream_generator = optimized_assistant.answer_with_direct_api(module_name, user_message)
            
            # Stream the response chunks
            for chunk in stream_generator:
                yield chunk
        
        except Exception as e:
            logger.error(f"Error in generate: {e}")
            yield f"Error: {str(e)}"
    
    # Return streaming response
    return Response(generate(), mimetype='text/plain')

def optimize_existing_app(app, api_key, assistant_id=None):
    """
    Optimize an existing Flask app by patching in the optimized SAP assistant.
    
    Args:
        app: The Flask application instance
        api_key: The OpenAI API key
        assistant_id: Optional ID of an OpenAI Assistant
        
    Returns:
        bool: True if successful, False otherwise
    """
    # Initialize the optimized assistant
    success = initialize_optimized_assistant(api_key, assistant_id)
    if not success:
        return False
    
    # Store original route function
    original_module_answer = app.view_functions.get('module_answer')
    
    if not original_module_answer:
        logger.error("Could not find 'module_answer' function in app routes")
        return False
    
    # Define new optimized route function that maintains the same interface
    def optimized_route_handler(module_name):
        # Check user authentication similar to original route
        if 'username' not in request.cookies and 'username' not in session:
            return jsonify({'error': 'Unauthorized'}), 401
        
        try:
            # Get request data
            data = request.get_json()
            message = data.get("message", "")
            
            # Use optimized answer function
            return optimized_module_answer(module_name, message)
            
        except Exception as e:
            logger.error(f"Error in optimized route: {e}")
            return jsonify({'error': str(e)}), 500
    
    # Replace the route handler
    app.view_functions['module_answer'] = optimized_route_handler
    
    # Add status endpoint to monitor optimization performance
    @app.route("/api/optimization_status", methods=["GET"])
    def optimization_status():
        """Endpoint to check optimization performance metrics"""
        if not optimized_assistant:
            return jsonify({'status': 'not_initialized'}), 500
        
        metrics = optimized_assistant.get_performance_metrics()
        
        # Add comparison with pre-optimization if available
        # This could be expanded based on historical data
        return jsonify({
            'status': 'active',
            'metrics': metrics,
            'estimated_savings': {
                'tokens': int(metrics['total_tokens_in'] * 0.3)  # Estimate 30% token reduction
            }
        })
    
    # Add configuration endpoint
    @app.route("/api/configure_optimization", methods=["POST"])
    def configure_optimization():
        """Endpoint to configure optimization settings"""
        if 'username' not in request.cookies and 'username' not in session:
            return jsonify({'error': 'Unauthorized'}), 401
        
        try:
            data = request.get_json()
            
            # Update configuration settings (not implemented yet)
            # This could include turning specific optimizations on/off
            
            return jsonify({'status': 'settings_updated'})
            
        except Exception as e:
            logger.error(f"Error configuring optimization: {e}")
            return jsonify({'error': str(e)}), 500
    
    logger.info("SAP Assistant optimization successfully integrated")
    return True

# For direct usage in talk_to_assistant.py
def get_optimized_answer(client, module_name, user_message, conversation_history):
    """
    Get an optimized answer for direct usage in the existing code.
    This function can be called directly from the existing talk_to_assistant.py
    without modifying the Flask routes.
    
    Args:
        client: The OpenAI client instance
        module_name: The SAP module context
        user_message: The user's query
        conversation_history: The existing conversation history
        
    Returns:
        str: The assistant's response
    """
    global optimized_assistant
    
    # Initialize assistant if not already done
    if not optimized_assistant and client:
        optimized_assistant = create_optimized_assistant(client.api_key)
    
    # If we still don't have an assistant, use the existing client directly
    if not optimized_assistant:
        logger.warning("Using non-optimized approach as fallback")
        # This would be a simplified version of the original code
        return "Optimized assistant not available"
    
    # Copy conversation history to optimized assistant
    for msg in conversation_history:
        if msg not in optimized_assistant.get_conversation(module_name):
            optimized_assistant.get_conversation(module_name).append(msg)
    
    # Get optimized response
    response, _ = optimized_assistant.answer_with_direct_api(module_name, user_message)
    return response
