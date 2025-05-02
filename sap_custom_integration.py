"""
SAP Custom Development Integration Module
Integrates the SAP custom development analyzer with the main application.
"""

import os
import logging
import json
from flask import jsonify

# Import the custom development analyzer
from sap_custom_dev_analyzer import analyze_sap_functional_document

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# List of document extensions that can be analyzed for functional requirements
FUNCTIONAL_DOC_EXTENSIONS = {'txt', 'pdf', 'doc', 'docx', 'md'}

def is_functional_document(filename):
    """Check if the file is likely to be a functional document"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in FUNCTIONAL_DOC_EXTENSIONS

def analyze_uploaded_document(file_path):
    """
    Analyze an uploaded document for BADIs, BAPIs, and enhancement points.
    
    Args:
        file_path: Path to the uploaded document
        
    Returns:
        dict: Analysis results
    """
    try:
        # Check if file exists
        if not os.path.exists(file_path):
            return {"error": f"File not found: {file_path}"}
        
        # Check if file is a functional document
        if not is_functional_document(file_path):
            return {"error": "File is not a supported functional document type"}
        
        # Analyze the document
        analysis_results = analyze_sap_functional_document(file_path)
        
        # Log the analysis
        logger.info(f"Document analysis completed: {len(analysis_results.get('code_suggestions', []))} code suggestions generated")
        
        return analysis_results
    
    except Exception as e:
        logger.error(f"Error analyzing document: {str(e)}")
        return {"error": str(e)}

def format_analysis_for_chat(analysis_results):
    """
    Format analysis results for display in the chat interface.
    
    Args:
        analysis_results: The analysis results from analyze_uploaded_document
        
    Returns:
        str: Formatted message for the chat
    """
    if "error" in analysis_results:
        return f"Error analyzing document: {analysis_results['error']}"
    
    # Start with identified module
    module = analysis_results.get("identified_module", "Unknown")
    message_parts = [f"## SAP Document Analysis Results\n\nIdentified SAP Module: **{module}**\n"]
    
    # Add identified objects
    dev_objects = analysis_results.get("potential_development_objects", {})
    
    # Add BADIs
    badis = dev_objects.get("BADIs", [])
    if badis:
        message_parts.append("\n### Identified Business Add-Ins (BADIs)\n")
        for i, badi in enumerate(badis, 1):
            message_parts.append(f"{i}. **{badi['name']}**: {badi['description']}")
    
    # Add BAPIs
    bapis = dev_objects.get("BAPIs", [])
    if bapis:
        message_parts.append("\n### Identified Business APIs (BAPIs)\n")
        for i, bapi in enumerate(bapis, 1):
            message_parts.append(f"{i}. **{bapi['name']}**: {bapi['description']}")
    
    # Add Enhancements
    enhancements = dev_objects.get("Enhancements", [])
    if enhancements:
        message_parts.append("\n### Identified Enhancement Points\n")
        for i, enhancement in enumerate(enhancements, 1):
            message_parts.append(f"{i}. **{enhancement['name']}**: {enhancement['description']}")
    
    # Add requirements
    requirements = analysis_results.get("requirements", [])
    if requirements:
        message_parts.append("\n### Extracted Requirements\n")
        for i, req in enumerate(requirements, 1):
            message_parts.append(f"{i}. {req}")
    
    # Add suggested approach
    approach = analysis_results.get("suggested_approach", {})
    if approach and approach.get("approach") != "Undetermined":
        message_parts.append(f"\n### Recommended Development Approach\n")
        message_parts.append(f"**{approach.get('approach')}**: {approach.get('explanation')}")
    
    # Add code suggestions
    code_suggestions = analysis_results.get("code_suggestions", [])
    if code_suggestions:
        message_parts.append("\n### Generated ABAP Code Templates\n")
        for i, suggestion in enumerate(code_suggestions, 1):
            message_parts.append(f"#### {i}. {suggestion['type']}: {suggestion['name']}\n")
            message_parts.append(f"Description: {suggestion['description']}\n")
            message_parts.append("```abap\n" + suggestion['code'] + "\n```\n")
    
    # If no development objects found
    if not badis and not bapis and not enhancements:
        message_parts.append("\n**No specific SAP development objects were identified in this document.**\n")
        message_parts.append("Consider uploading a more detailed functional specification or provide more specific requirements.")
    
    return "\n".join(message_parts)

def get_abap_code_from_analysis(analysis_results, dev_type=None, index=0):
    """
    Extract specific ABAP code from analysis results.
    
    Args:
        analysis_results: The analysis results
        dev_type: Type of development object (BADI, BAPI, Enhancement)
        index: Index of the code suggestion to retrieve
        
    Returns:
        str: ABAP code or error message
    """
    code_suggestions = analysis_results.get("code_suggestions", [])
    
    if not code_suggestions:
        return "No code suggestions available from document analysis."
    
    # Filter by type if specified
    if dev_type:
        filtered_suggestions = [s for s in code_suggestions if s["type"] == dev_type]
        if not filtered_suggestions:
            return f"No {dev_type} code suggestions available."
        
        if index < len(filtered_suggestions):
            return filtered_suggestions[index]["code"]
        else:
            return f"Index {index} out of range for {dev_type} code suggestions."
    
    # Return by index if no type specified
    if index < len(code_suggestions):
        return code_suggestions[index]["code"]
    else:
        return f"Index {index} out of range for code suggestions."
