"""
SAP Custom Development Analyzer
Module for analyzing SAP functional documents to identify BADIs, BAPIs, and enhancement points.
"""

import re
import logging
import json
import os
from collections import defaultdict
import nltk
from nltk.tokenize import sent_tokenize, word_tokenize
from nltk.corpus import stopwords
import PyPDF2
from docx import Document  # Using python-docx instead of docx

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Ensure NLTK resources are available
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt')
try:
    nltk.data.find('corpora/stopwords')
except LookupError:
    nltk.download('stopwords')

# SAP Development Objects Database
SAP_DEV_OBJECTS = {
    "BADIs": {
        "FI/CO": [
            {"name": "BADI_SAMPLE_CUSTOMER_CREDIT", "description": "Customer Credit Management", "interface": "IF_EX_CUSTOMER_CREDIT"},
            {"name": "FCOM_BADI_GL_DOCUMENT", "description": "G/L Document Processing", "interface": "IF_EX_GL_DOCUMENT"},
            {"name": "BADI_ACC_DOCUMENT", "description": "FI Document Processing", "interface": "IF_EX_AC_DOCUMENT"},
            {"name": "FAGL_BADI_GL_MSE", "description": "G/L Master Data Extension", "interface": "IF_FAGL_GL_MSE"}
        ],
        "MM": [
            {"name": "BADI_ME_PROCESS_PO_CUST", "description": "Purchase Order Processing", "interface": "IF_EX_ME_PROCESS_PO_CUST"},
            {"name": "BADI_ME_PROCESS_REQ_CUST", "description": "Purchase Requisition", "interface": "IF_EX_ME_PROCESS_REQ_CUST"},
            {"name": "BADI_MEPO_FIELDSELECTION", "description": "Field Selection in PO", "interface": "IF_EX_MEPO_FIELDSELECTION"}
        ],
        "SD": [
            {"name": "BADI_SD_SALESDOCUMENT", "description": "Sales Document Processing", "interface": "IF_EX_SALESDOCUMENT"},
            {"name": "SD_PRICING_BADI", "description": "Pricing Customization", "interface": "IF_EX_SD_PRICING"},
            {"name": "V50R_BILLING", "description": "Billing Document Processing", "interface": "IF_EX_V50R_BILLING"}
        ]
    },
    "BAPIs": {
        "FI/CO": [
            {"name": "BAPI_ACC_DOCUMENT_POST", "description": "Post Accounting Document", "parameters": ["DOCUMENTHEADER", "ACCOUNTGL", "ACCOUNTRECEIVABLE", "ACCOUNTPAYABLE"]},
            {"name": "BAPI_ACC_GL_POSTING_POST", "description": "Post G/L Account Document", "parameters": ["DOCUMENTHEADER", "ACCOUNTGL"]},
            {"name": "BAPI_ACC_DOCUMENT_CHECK", "description": "Check Accounting Document", "parameters": ["DOCUMENTHEADER", "ACCOUNTGL"]}
        ],
        "MM": [
            {"name": "BAPI_PO_CREATE1", "description": "Create Purchase Order", "parameters": ["POHEADER", "POITEM", "POSCHEDULE", "POPARTNER"]},
            {"name": "BAPI_GOODSMVT_CREATE", "description": "Create Goods Movement", "parameters": ["GOODSMVT_HEADER", "GOODSMVT_ITEM"]},
            {"name": "BAPI_MATERIAL_SAVEDATA", "description": "Create Material Master", "parameters": ["CLIENTDATA", "MATERIALDATA"]}
        ],
        "SD": [
            {"name": "BAPI_SALESORDER_CREATEFROMDAT2", "description": "Create Sales Order", "parameters": ["ORDER_HEADER_IN", "ORDER_ITEMS_IN"]},
            {"name": "BAPI_DELIVERY_CREATE", "description": "Create Delivery", "parameters": ["DELIVERY_HEADER_IN", "DELIVERY_ITEMS_IN"]},
            {"name": "BAPI_BILLINGDOC_CREATEMULTIPLE", "description": "Create Billing Document", "parameters": ["BILLING_HEADER_IN", "BILLING_ITEMS_IN"]}
        ]
    },
    "Enhancements": {
        "FI/CO": [
            {"name": "FIGL_FIELD_MODIFICATION", "type": "Enhancement Spot", "description": "G/L Field Modifications"},
            {"name": "FIAA_DEPRECIATION", "type": "Enhancement Spot", "description": "Asset Depreciation Calculation"}
        ],
        "MM": [
            {"name": "MM_PUR_PURCHREQ", "type": "Enhancement Spot", "description": "Purchase Requisition Processing"},
            {"name": "MM_IM_GOODS_RECEIPT", "type": "Enhancement Spot", "description": "Goods Receipt Processing"}
        ],
        "SD": [
            {"name": "SD_SOF_FUNCTIONS", "type": "Enhancement Spot", "description": "Sales Order Functions"},
            {"name": "SD_DELIVERY_PROCESSING", "type": "Enhancement Spot", "description": "Delivery Processing"}
        ]
    }
}

# ABAP Code Templates for different customization types
ABAP_TEMPLATES = {
    "BADI": """*&---------------------------------------------------------------------*
*& Implementation of BADI {badi_name}
*&---------------------------------------------------------------------*
CLASS zcl_{badi_class_name} DEFINITION
  PUBLIC
  FINAL
  CREATE PUBLIC .

  PUBLIC SECTION.
    INTERFACES {interface} .
  PROTECTED SECTION.
  PRIVATE SECTION.
ENDCLASS.

CLASS zcl_{badi_class_name} IMPLEMENTATION.
  METHOD {interface}~{method_name}.
    " {implementation_comment}
    {implementation_code}
  ENDMETHOD.
ENDCLASS.""",

    "BAPI": """*&---------------------------------------------------------------------*
*& BAPI Enhancement: {bapi_name}
*&---------------------------------------------------------------------*
FUNCTION z_{function_name}.
*"----------------------------------------------------------------------
*"*"Local Interface:
{parameter_declarations}
*"----------------------------------------------------------------------

  " {implementation_comment}
  {implementation_code}

ENDFUNCTION.""",

    "ENHANCEMENT": """*&---------------------------------------------------------------------*
*& Enhancement Implementation: {enhancement_name}
*&---------------------------------------------------------------------*
ENHANCEMENT {enhancement_id} {enhancement_name}.
  " {implementation_comment}
  {implementation_code}
ENDENHANCEMENT."""
}

class SAPDevelopmentAnalyzer:
    """Analyzes SAP functional documents to identify custom development needs"""
    
    def __init__(self):
        """Initialize the analyzer with SAP development knowledge"""
        self.dev_objects = SAP_DEV_OBJECTS
        self.stop_words = set(stopwords.words('english'))
        
        # Keywords that might indicate custom development needs
        self.dev_keywords = {
            "BADI": ["badi", "business add-in", "add-in", "exit", "extension", "customization point"],
            "BAPI": ["bapi", "business api", "interface", "function module", "rfc"],
            "Enhancement": ["enhancement", "user exit", "customer exit", "modification", "custom code"]
        }
        
        # Module-specific keywords
        self.module_keywords = {
            "FI/CO": ["finance", "controlling", "general ledger", "accounts payable", "accounts receivable", 
                     "asset accounting", "cost center", "profit center", "posting", "journal entry"],
            "MM": ["materials management", "purchasing", "inventory", "warehouse", "goods receipt", 
                  "purchase order", "material master", "vendor", "procurement"],
            "SD": ["sales", "distribution", "customer", "order", "delivery", "billing", 
                  "pricing", "shipping", "credit"]
        }
    
    def read_document(self, file_path):
        """Extract text from various document formats"""
        try:
            file_ext = os.path.splitext(file_path)[1].lower()
            
            if file_ext == '.pdf':
                return self._read_pdf(file_path)
            elif file_ext == '.docx':
                return self._read_docx(file_path)
            elif file_ext in ['.txt', '.md']:
                with open(file_path, 'r', encoding='utf-8') as f:
                    return f.read()
            else:
                logger.error(f"Unsupported file type: {file_ext}")
                return None
        except Exception as e:
            logger.error(f"Error reading document: {str(e)}")
            return None
    
    def _read_pdf(self, file_path):
        """Extract text from PDF"""
        text = ""
        with open(file_path, 'rb') as file:
            reader = PyPDF2.PdfReader(file)
            for page_num in range(len(reader.pages)):
                text += reader.pages[page_num].extract_text() + "\n"
        return text
    
    def _read_docx(self, file_path):
        """Extract text from DOCX"""
        doc = Document(file_path)
        return " ".join([paragraph.text for paragraph in doc.paragraphs])
    
    def analyze_document(self, doc_text):
        """
        Analyze document text to identify potential BADIs, BAPIs, and enhancements
        
        Args:
            doc_text: The document text to analyze
            
        Returns:
            dict: Results containing identified development objects and recommendations
        """
        if not doc_text:
            return {"error": "No document text provided"}
        
        # Preprocess text
        sentences = sent_tokenize(doc_text)
        
        # Results structure
        results = {
            "identified_module": self._identify_sap_module(doc_text),
            "potential_development_objects": {
                "BADIs": [],
                "BAPIs": [],
                "Enhancements": []
            },
            "requirements": [],
            "code_suggestions": []
        }
        
        # Process each sentence for potential development needs
        for sentence in sentences:
            sentence_lower = sentence.lower()
            
            # Check for development keywords
            for dev_type, keywords in self.dev_keywords.items():
                if any(keyword in sentence_lower for keyword in keywords):
                    # Identified potential customization point
                    if dev_type == "BADI":
                        badi = self._identify_badi(sentence, results["identified_module"])
                        if badi and badi not in results["potential_development_objects"]["BADIs"]:
                            results["potential_development_objects"]["BADIs"].append(badi)
                            # Generate code suggestion
                            code = self._generate_badi_code(badi, sentence)
                            if code:
                                results["code_suggestions"].append(code)
                    
                    elif dev_type == "BAPI":
                        bapi = self._identify_bapi(sentence, results["identified_module"])
                        if bapi and bapi not in results["potential_development_objects"]["BAPIs"]:
                            results["potential_development_objects"]["BAPIs"].append(bapi)
                            # Generate code suggestion
                            code = self._generate_bapi_code(bapi, sentence)
                            if code:
                                results["code_suggestions"].append(code)
                    
                    elif dev_type == "Enhancement":
                        enhancement = self._identify_enhancement(sentence, results["identified_module"])
                        if enhancement and enhancement not in results["potential_development_objects"]["Enhancements"]:
                            results["potential_development_objects"]["Enhancements"].append(enhancement)
                            # Generate code suggestion
                            code = self._generate_enhancement_code(enhancement, sentence)
                            if code:
                                results["code_suggestions"].append(code)
            
            # Extract potential requirements
            if self._is_requirement_statement(sentence):
                results["requirements"].append(sentence)
        
        return results
    
    def _identify_sap_module(self, text):
        """Identify the most relevant SAP module from text"""
        module_scores = {module: 0 for module in self.module_keywords.keys()}
        
        for module, keywords in self.module_keywords.items():
            for keyword in keywords:
                matches = re.findall(r'\b' + re.escape(keyword) + r'\b', text.lower())
                module_scores[module] += len(matches)
        
        # Return the module with the highest score, or "General" if no clear match
        max_score = max(module_scores.values())
        if max_score > 0:
            for module, score in module_scores.items():
                if score == max_score:
                    return module
        
        return "General"
    
    def _identify_badi(self, sentence, module):
        """Identify potential BADI from sentence"""
        if module in self.dev_objects["BADIs"]:
            for badi in self.dev_objects["BADIs"][module]:
                if badi["name"].lower() in sentence.lower() or badi["description"].lower() in sentence.lower():
                    return badi
        
        # If no exact match, look for descriptive matches
        key_phrases = ["document processing", "pricing", "validation", "determination", "check", "master data"]
        for phrase in key_phrases:
            if phrase in sentence.lower():
                # Find BADIs with similar functionality
                for mod in self.dev_objects["BADIs"]:
                    for badi in self.dev_objects["BADIs"][mod]:
                        if phrase in badi["description"].lower():
                            return badi
        
        return None
    
    def _identify_bapi(self, sentence, module):
        """Identify potential BAPI from sentence"""
        if module in self.dev_objects["BAPIs"]:
            for bapi in self.dev_objects["BAPIs"][module]:
                if bapi["name"].lower() in sentence.lower() or bapi["description"].lower() in sentence.lower():
                    return bapi
        
        # If no exact match, check for common operations
        operations = {
            "create": ["create", "generate", "new"],
            "change": ["change", "modify", "update"],
            "display": ["display", "show", "view", "get"],
            "post": ["post", "release", "submit"]
        }
        
        for op_type, keywords in operations.items():
            if any(keyword in sentence.lower() for keyword in keywords):
                # Find BAPIs for the operation type
                for mod in self.dev_objects["BAPIs"]:
                    for bapi in self.dev_objects["BAPIs"][mod]:
                        if op_type in bapi["name"].lower() or op_type in bapi["description"].lower():
                            return bapi
        
        return None
    
    def _identify_enhancement(self, sentence, module):
        """Identify potential enhancement from sentence"""
        if module in self.dev_objects["Enhancements"]:
            for enhancement in self.dev_objects["Enhancements"][module]:
                if enhancement["name"].lower() in sentence.lower() or enhancement["description"].lower() in sentence.lower():
                    return enhancement
        
        # Generic matching based on functionality
        if module == "FI/CO" and any(term in sentence.lower() for term in ["field", "validation", "display"]):
            return self.dev_objects["Enhancements"]["FI/CO"][0]  # Field modification enhancement
        
        if module == "MM" and any(term in sentence.lower() for term in ["requisition", "approval"]):
            return self.dev_objects["Enhancements"]["MM"][0]  # Purchase requisition enhancement
        
        if module == "SD" and any(term in sentence.lower() for term in ["order", "processing"]):
            return self.dev_objects["Enhancements"]["SD"][0]  # Sales order enhancement
        
        return None
    
    def _is_requirement_statement(self, sentence):
        """Check if a sentence describes a business requirement"""
        requirement_indicators = ["must", "should", "need", "has to", "require", "mandatory", "implement", "add", "enhance"]
        return any(indicator in sentence.lower() for indicator in requirement_indicators)
    
    def _generate_badi_code(self, badi, context_sentence):
        """Generate ABAP code template for BADI implementation"""
        if not badi:
            return None
        
        # Extract method name from interface (typically the one after ~)
        interface = badi["interface"]
        method_match = re.search(r'IF_EX_(\w+)', interface)
        method_name = f"handle_{method_match.group(1).lower()}" if method_match else "handle_process"
        
        # Generate a class name based on BADI name
        badi_class_name = badi["name"].lower().replace('badi_', '')
        
        # Generate appropriate implementation code based on context
        if "validation" in context_sentence.lower():
            implementation_comment = "Implement validation logic here"
            implementation_code = """* Example validation code
IF iv_value IS INITIAL.
  " Set error message
  MESSAGE 'Value cannot be empty' TYPE 'E'.
ENDIF."""
        elif "calculation" in context_sentence.lower():
            implementation_comment = "Implement calculation logic here"
            implementation_code = """* Example calculation code
lv_result = iv_value1 * iv_value2.
cv_total = cv_total + lv_result."""
        else:
            implementation_comment = "Implement your custom logic here"
            implementation_code = """* Add your custom implementation
* Access data using importing parameters
* Modify data using changing/exporting parameters
BREAK-POINT."""
        
        # Fill the template
        code = ABAP_TEMPLATES["BADI"].format(
            badi_name=badi["name"],
            badi_class_name=badi_class_name,
            interface=interface,
            method_name=method_name,
            implementation_comment=implementation_comment,
            implementation_code=implementation_code
        )
        
        return {
            "type": "BADI",
            "name": badi["name"],
            "description": badi["description"],
            "code": code
        }
    
    def _generate_bapi_code(self, bapi, context_sentence):
        """Generate ABAP code for BAPI enhancement/wrapper"""
        if not bapi:
            return None
        
        # Generate function name based on BAPI
        function_name = f"enhance_{bapi['name'].lower().replace('bapi_', '')}"
        
        # Generate parameter declarations based on BAPI parameters
        if "parameters" in bapi:
            param_declarations = []
            for param in bapi["parameters"]:
                param_declarations.append(f'*"  IMPORTING\n*"     VALUE({param.lower()}) TYPE REF TO data')
            parameter_declarations = "\n".join(param_declarations)
        else:
            parameter_declarations = '*"  No specific parameters defined'
        
        # Different implementations based on context
        if "validation" in context_sentence.lower():
            implementation_comment = "Implement pre-BAPI validation logic"
            implementation_code = """* Example validation before BAPI call
DATA: ls_header TYPE bapi_header.

* Copy from import parameter to local structure
* ls_header = ...

* Validate header data
IF ls_header-doc_type IS INITIAL.
  MESSAGE 'Document type is required' TYPE 'E'.
ENDIF.

* Call the standard BAPI
CALL FUNCTION 'BAPI_TRANSACTION_COMMIT'
  EXPORTING
    wait = 'X'."""
        elif "extend" in context_sentence.lower():
            implementation_comment = "Extend BAPI with additional functionality"
            implementation_code = """* Call original BAPI first
CALL FUNCTION '{0}'
  EXPORTING
    parameter1 = value1
    parameter2 = value2
  IMPORTING
    result     = lv_result.

* Add your extension logic here
* For example, additional logging
WRITE: / 'BAPI {0} executed with result:', lv_result.""".format(bapi["name"])
        else:
            implementation_comment = "Custom wrapper for BAPI"
            implementation_code = """* Your custom logic before standard BAPI call
* ...

* Call standard BAPI
CALL FUNCTION '{0}'
  EXPORTING
    parameter1 = value1
    parameter2 = value2
  IMPORTING
    return     = lt_return.

* Your custom logic after standard BAPI call
* Process return messages, etc.
LOOP AT lt_return INTO ls_return WHERE type = 'E'.
  MESSAGE ID ls_return-id TYPE 'E' NUMBER ls_return-number
          WITH ls_return-message_v1 ls_return-message_v2
               ls_return-message_v3 ls_return-message_v4.
ENDLOOP.""".format(bapi["name"])
        
        # Fill the template
        code = ABAP_TEMPLATES["BAPI"].format(
            bapi_name=bapi["name"],
            function_name=function_name,
            parameter_declarations=parameter_declarations,
            implementation_comment=implementation_comment,
            implementation_code=implementation_code
        )
        
        return {
            "type": "BAPI Enhancement",
            "name": bapi["name"],
            "description": bapi["description"],
            "code": code
        }
    
    def _generate_enhancement_code(self, enhancement, context_sentence):
        """Generate ABAP code for enhancement implementation"""
        if not enhancement:
            return None
        
        # Generate enhancement ID based on name
        enhancement_id = f"ZE_{enhancement['name']}"
        
        # Different implementations based on context
        if "add field" in context_sentence.lower():
            implementation_comment = "Add custom field implementation"
            implementation_code = """* Example code to handle custom field
DATA: lv_custom_value TYPE char50.

* Get custom value from business data
lv_custom_value = 'CUSTOM_' && sy-datum.

* Process custom field
WRITE: / 'Custom Field Value:', lv_custom_value."""
        elif "validation" in context_sentence.lower():
            implementation_comment = "Add custom validation logic"
            implementation_code = """* Example validation code
IF <field> IS INITIAL AND <condition>.
  MESSAGE 'Custom validation failed' TYPE 'E'.
ENDIF."""
        else:
            implementation_comment = "Custom enhancement implementation"
            implementation_code = """* Standard implementation would be here
* Your custom code starts here
DATA: lv_custom_flag TYPE abap_bool.

* Implement your custom logic
IF sy-tcode = 'YOUR_TCODE'.
  lv_custom_flag = abap_true.
  * Do something special for this transaction
ENDIF."""
        
        # Fill the template
        code = ABAP_TEMPLATES["ENHANCEMENT"].format(
            enhancement_name=enhancement["name"],
            enhancement_id=enhancement_id,
            implementation_comment=implementation_comment,
            implementation_code=implementation_code
        )
        
        return {
            "type": "Enhancement",
            "name": enhancement["name"],
            "description": enhancement["description"],
            "code": code
        }
    
    def suggest_development_approach(self, requirements):
        """Suggest the best development approach based on requirements"""
        approaches = {
            "BADI": 0,
            "BAPI": 0,
            "Enhancement": 0,
            "Custom Report": 0,
            "Custom Transaction": 0
        }
        
        for req in requirements:
            req_lower = req.lower()
            
            # Score different approaches based on requirement keywords
            if any(word in req_lower for word in ["extend", "enhance", "customize", "override"]):
                approaches["BADI"] += 2
                approaches["Enhancement"] += 1
            
            if any(word in req_lower for word in ["interface", "integrate", "external", "third-party"]):
                approaches["BAPI"] += 2
            
            if any(word in req_lower for word in ["report", "output", "display", "list"]):
                approaches["Custom Report"] += 2
            
            if any(word in req_lower for word in ["transaction", "screen", "dialog", "user interface"]):
                approaches["Custom Transaction"] += 2
            
            if any(word in req_lower for word in ["standard", "sap", "existing functionality"]):
                approaches["Enhancement"] += 1
        
        # Find the approach with the highest score
        best_approach = max(approaches.items(), key=lambda x: x[1])
        
        if best_approach[1] == 0:
            return {
                "approach": "Undetermined",
                "explanation": "Insufficient information to determine the best approach. Please provide more specific requirements."
            }
        
        # Provide explanation based on the chosen approach
        explanations = {
            "BADI": "Business Add-In (BADI) is recommended as the requirements indicate a need to extend or customize standard SAP functionality without modifying the standard code.",
            "BAPI": "Business API (BAPI) approach is recommended as the requirements involve integration with external systems or standard SAP interfaces.",
            "Enhancement": "Enhancement Framework is recommended as the requirements involve extending standard SAP functionality at predefined enhancement spots.",
            "Custom Report": "Custom Report development is recommended as the requirements focus on data retrieval and presentation.",
            "Custom Transaction": "Custom Transaction development is recommended as the requirements involve creating new user interfaces or screens."
        }
        
        return {
            "approach": best_approach[0],
            "score": best_approach[1],
            "explanation": explanations.get(best_approach[0], "Approach determined based on requirement analysis.")
        }

# Function to analyze an uploaded SAP functional document
def analyze_sap_functional_document(file_path):
    """
    Analyze an SAP functional document to identify potential BADIs, BAPIs, and enhancement points.
    
    Args:
        file_path: Path to the document file
        
    Returns:
        dict: Analysis results
    """
    try:
        analyzer = SAPDevelopmentAnalyzer()
        doc_text = analyzer.read_document(file_path)
        
        if doc_text:
            results = analyzer.analyze_document(doc_text)
            
            # Add development approach suggestion
            if results["requirements"]:
                results["suggested_approach"] = analyzer.suggest_development_approach(results["requirements"])
            
            return results
        else:
            return {"error": "Failed to extract text from document"}
    
    except Exception as e:
        logger.error(f"Error analyzing document: {str(e)}")
        return {"error": str(e)}
