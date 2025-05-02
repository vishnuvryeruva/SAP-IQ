"""
SAP Optimized Assistant
Integrates with the existing SAP Assistant to provide optimized interactions with GPT-4o
specifically for SAP-related queries.
"""

import time
import logging
from datetime import datetime
import json
import re
from openai import OpenAI
from collections import deque

# Import centralized configuration
from config import *

# Import the optimized prompts and functions
from sap_optimized_prompts import (
    get_enhanced_system_message, 
    get_optimized_parameters,
    optimize_user_message,
    extract_sap_context,
    get_cached_response,
    cache_response,
    log_usage_stats
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SAPOptimizedAssistant:
    """
    Enhanced SAP Assistant that optimizes interactions with GPT-4o
    by using specialized prompts, caching, and context management.
    """
    
    def __init__(self, openai_client, assistant_id=None):
        """
        Initialize the optimized assistant.
        
        Args:
            openai_client: An initialized OpenAI client
            assistant_id: Optional ID of an OpenAI Assistant to use
        """
        self.client = openai_client
        self.assistant_id = assistant_id
        self.conversation_storage = {}  # Store conversations by module
        self.performance_metrics = {
            "total_tokens_in": 0,
            "total_tokens_out": 0,
            "total_api_calls": 0,
            "cache_hits": 0,
            "average_response_time": 0,
            "requests_served": 0
        }
    
    def get_conversation(self, module, max_length=10):
        """Get or create a conversation history for a module"""
        if module not in self.conversation_storage:
            self.conversation_storage[module] = deque(maxlen=max_length)
        return self.conversation_storage[module]
    
    def post_process_response(self, response):
        """
        Post-process the GPT-4o response to improve efficiency and quality.
        
        Args:
            response: The text response from GPT-4o
            
        Returns:
            str: Optimized response
        """
        # Standardize formatting for consistency
        response = self._standardize_code_blocks(response)
        response = self._format_sap_references(response)
        response = self._clean_excessive_newlines(response)
        return response
    
    def _standardize_code_blocks(self, text):
        """Ensure code blocks are properly formatted"""
        # Make sure ABAP code has the proper language tag
        text = re.sub(r'```(?!abap|ABAP)([^\n]*?\n[\s\S]*?```)', r'```abap\1', text)
        
        # Ensure all code blocks have triple backticks
        text = re.sub(r'(?<!`)`(?!`)([\s\S]*?)(?<!`)`(?!`)', r'```abap\n\1\n```', text)
        
        return text
    
    def _format_sap_references(self, text):
        """Format SAP references consistently"""
        # Format transaction codes like FB01
        text = re.sub(r'\b([A-Z]{2}\d{2}[A-Z]?)\b', r'**\1**', text)
        
        # Format table names like BSEG
        text = re.sub(r'\b([A-Z]{4})\b', lambda m: f"**{m.group(1)}**" 
                     if m.group(1) not in ["FROM", "WHERE", "JOIN", "WITH", "ABAP", "DATA", "TYPE", "FORM", "CALL"] 
                     else m.group(1), text)
        
        return text
    
    def _clean_excessive_newlines(self, text):
        """Remove excessive newlines for more compact responses"""
        # Replace 3+ newlines with 2 newlines
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text
    
    def answer_with_direct_api(self, module, user_message):
        """
        Get an answer using the OpenAI API directly (not through Assistant API).
        This approach uses our optimized prompts and context.
        
        Args:
            module: The SAP module context (e.g., 'fico', 'mm')
            user_message: The user's query
            
        Returns:
            tuple: (response text, generator function for streaming)
        """
        # Check cache first
        cached_response = get_cached_response(module, user_message)
        if cached_response:
            self.performance_metrics["cache_hits"] += 1
            
            # For consistency with the streaming API, wrap in a generator
            def cached_generator():
                yield cached_response
                
            return cached_response, cached_generator()
        
        # Get conversation history for this module
        conversation = self.get_conversation(module)
        
        # Add user message to history
        conversation.append({"role": "user", "content": user_message})
        
        # Get enhanced system message
        system_message = get_enhanced_system_message(module)
        
        # Create message array
        messages = [
            {"role": "system", "content": system_message}
        ]
        
        # Add recent conversation history (limited to reduce tokens)
        recent_history = list(conversation)[-10:] if conversation else []
        for msg in recent_history[:-1]:  # Exclude the message we just added
            if msg["role"] in ["user", "assistant"]:
                messages.append(msg)
        
        # Add the optimized user message
        optimized_message = optimize_user_message(user_message, module)
        messages[-1] = {"role": "user", "content": optimized_message}
        
        # Get optimized parameters
        params = get_optimized_parameters(module)
        
        # Record start time for performance measurement
        start_time = time.time()
        
        # Make the API call with streaming
        try:
            self.performance_metrics["total_api_calls"] += 1
            stream = self.client.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                stream=True,
                **params
            )
            
            # Define generator function for streaming
            def generate():
                full_response = ""
                
                for chunk in stream:
                    if chunk.choices and chunk.choices[0].delta.content:
                        content = chunk.choices[0].delta.content
                        full_response += content
                        yield content
                
                # After we have the full response
                if full_response:
                    # Post-process
                    processed_response = self.post_process_response(full_response)
                    
                    # Add to conversation history
                    conversation.append({"role": "assistant", "content": processed_response})
                    
                    # Cache for future use
                    cache_response(module, user_message, processed_response)
                    
                    # Log usage (in a real system, you'd get token counts from the API response)
                    duration = time.time() - start_time
                    tokens_in = len(" ".join([m["content"] for m in messages])) // 4  # Rough estimate
                    tokens_out = len(processed_response) // 4  # Rough estimate
                    
                    # Update metrics
                    self.performance_metrics["total_tokens_in"] += tokens_in
                    self.performance_metrics["total_tokens_out"] += tokens_out
                    
                    # Update average response time
                    self.performance_metrics["requests_served"] += 1
                    prev_avg = self.performance_metrics["average_response_time"]
                    n = self.performance_metrics["requests_served"]
                    self.performance_metrics["average_response_time"] = ((n-1) * prev_avg + duration) / n
                    
                    # Log metrics
                    log_usage_stats(module, user_message, tokens_in, tokens_out, duration)
            
            # Call generate once to start getting the full response
            full_response = ""
            for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    full_response += content
            
            # Post-process the complete response
            processed_response = self.post_process_response(full_response)
            
            # Add to conversation history
            conversation.append({"role": "assistant", "content": processed_response})
            
            # Cache for future use
            cache_response(module, user_message, processed_response)
            
            # Calculate metrics
            duration = time.time() - start_time
            tokens_in = len(" ".join([m["content"] for m in messages])) // 4  # Rough estimate
            tokens_out = len(processed_response) // 4  # Rough estimate
            
            # Update metrics
            self.performance_metrics["total_tokens_in"] += tokens_in
            self.performance_metrics["total_tokens_out"] += tokens_out
            self.performance_metrics["requests_served"] += 1
            
            # Update average response time
            prev_avg = self.performance_metrics["average_response_time"]
            n = self.performance_metrics["requests_served"]
            self.performance_metrics["average_response_time"] = ((n-1) * prev_avg + duration) / n
            
            # Log metrics
            log_usage_stats(module, user_message, tokens_in, tokens_out, duration)
            
            # Create a generator that yields the full response at once
            def simple_generator():
                yield processed_response
            
            return processed_response, simple_generator()
            
        except Exception as e:
            error_msg = f"Error getting answer: {str(e)}"
            logger.error(error_msg)
            return error_msg, (yield error_msg)
    
    def answer_with_assistants_api(self, module, user_message):
        """
        Get an answer using the OpenAI Assistants API.
        This uses threads and the specified assistant_id.
        
        Args:
            module: The SAP module context (e.g., 'fico', 'mm')
            user_message: The user's query
            
        Returns:
            tuple: (response text, generator function for streaming)
        """
        if not self.assistant_id:
            return "Assistant ID not configured", (yield "Assistant ID not configured")
        
        # Get conversation for this module
        conversation = self.get_conversation(module)
        
        # Add message to conversation history
        conversation.append({"role": "user", "content": user_message})
        
        try:
            # Create thread with optimized message
            thread = self.client.beta.threads.create()
            
            # Add the optimized user message
            optimized_message = optimize_user_message(user_message, module)
            self.client.beta.threads.messages.create(
                thread_id=thread.id,
                role="user",
                content=optimized_message
            )
            
            # Create run with streaming
            start_time = time.time()
            stream = self.client.beta.threads.runs.create(
                thread_id=thread.id,
                assistant_id=self.assistant_id,
                timeout=30,
                stream=True
            )
            
            # Define generator function for streaming
            def generate():
                assistant_response = ""
                for event in stream:
                    if event.data.object == "thread.message.delta":
                        for content in event.data.delta.content:
                            if content.type == "text":
                                assistant_response += content.text.value
                                yield content.text.value
                
                # Post-process after getting the full response
                if assistant_response:
                    processed_response = self.post_process_response(assistant_response)
                    
                    # Add to conversation history
                    conversation.append({"role": "assistant", "content": processed_response})
                    
                    # Cache for future use
                    cache_response(module, user_message, processed_response)
                    
                    # Log usage
                    duration = time.time() - start_time
                    tokens_in = len(optimized_message) // 4  # Rough estimate
                    tokens_out = len(processed_response) // 4  # Rough estimate
                    
                    # Update metrics
                    self.performance_metrics["total_api_calls"] += 1
                    self.performance_metrics["total_tokens_in"] += tokens_in
                    self.performance_metrics["total_tokens_out"] += tokens_out
                    self.performance_metrics["requests_served"] += 1
                    
                    # Update average response time
                    prev_avg = self.performance_metrics["average_response_time"]
                    n = self.performance_metrics["requests_served"]
                    self.performance_metrics["average_response_time"] = ((n-1) * prev_avg + duration) / n
                    
                    # Log metrics
                    log_usage_stats(module, user_message, tokens_in, tokens_out, duration)
            
            # Process stream to get full response first
            assistant_response = ""
            for event in stream:
                if event.data.object == "thread.message.delta":
                    for content in event.data.delta.content:
                        if content.type == "text":
                            assistant_response += content.text.value
            
            # Post-process
            processed_response = self.post_process_response(assistant_response)
            
            # Add to conversation history
            conversation.append({"role": "assistant", "content": processed_response})
            
            # Calculate metrics
            duration = time.time() - start_time
            tokens_in = len(optimized_message) // 4  # Rough estimate
            tokens_out = len(processed_response) // 4  # Rough estimate
            
            # Update metrics
            self.performance_metrics["total_api_calls"] += 1
            self.performance_metrics["total_tokens_in"] += tokens_in
            self.performance_metrics["total_tokens_out"] += tokens_out
            self.performance_metrics["requests_served"] += 1
            
            # Log metrics
            log_usage_stats(module, user_message, tokens_in, tokens_out, duration)
            
            # Create a generator that yields the full response at once
            def simple_generator():
                yield processed_response
            
            return processed_response, simple_generator()
            
        except Exception as e:
            error_msg = f"Error in assistants API: {str(e)}"
            logger.error(error_msg)
            return error_msg, (yield error_msg)
    
    def get_performance_metrics(self):
        """Get assistant performance metrics"""
        return self.performance_metrics
    
    def clear_conversation(self, module):
        """Clear conversation history for a module"""
        if module in self.conversation_storage:
            self.conversation_storage[module] = deque(maxlen=self.conversation_storage[module].maxlen)
            return True
        return False

# Factory function to create the optimized assistant
def create_optimized_assistant(api_key, assistant_id=None):
    """
    Create and return an optimized SAP Assistant instance.
    
    Args:
        api_key: OpenAI API key
        assistant_id: Optional ID of an OpenAI Assistant to use
        
    Returns:
        SAPOptimizedAssistant: An instance of the optimized assistant
    """
    client = OpenAI(api_key=api_key)
    return SAPOptimizedAssistant(client, assistant_id)
