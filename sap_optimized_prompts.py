"""
SAP Assistant Optimization Module
This module contains optimized prompts and techniques to make the SAP Assistant more efficient
with GPT-4o, specifically for SAP-related queries.
"""

import json
import os
import re
import hashlib
from datetime import datetime, timedelta

# SAP Modules dictionary with expanded information
SAP_MODULES = {
    'FI/CO': {
        'description': 'Financial Accounting and Controlling',
        'components': ['General Ledger', 'Accounts Payable', 'Accounts Receivable', 'Asset Accounting', 'Cost Center Accounting', 'Profit Center Accounting'],
        'keywords': ['financial accounting', 'controlling', 'general ledger', 'GL', 'AP', 'AR', 'assets', 'cost centers', 'profit centers', 'internal orders', 'CO-PA'],
        'tables': ['BKPF', 'BSEG', 'BSID', 'BSIK', 'BSAD', 'BSAK', 'SKB1', 'ANEK', 'COEP', 'COBK', 'FAGLFLEXA', 'FAGLFLEXT'],
        'transactions': ['FB01', 'FB50', 'F-02', 'F-28', 'F.01', 'F.02', 'F.03', 'KE30', 'KE24', 'FAGLB03', 'FAGLL03']
    },
    'MM': {
        'description': 'Materials Management',
        'components': ['Purchasing', 'Inventory Management', 'Invoice Verification', 'Material Master', 'Vendor Master'],
        'keywords': ['procurement', 'purchasing', 'materials', 'inventory', 'warehouse', 'vendor', 'supplier', 'goods receipt', 'invoice verification'],
        'tables': ['EKKO', 'EKPO', 'MARA', 'MARC', 'MARD', 'MKPF', 'MSEG', 'LFA1', 'MAKT', 'MCHB'],
        'transactions': ['ME21N', 'ME23N', 'MIGO', 'MB1A', 'MB1B', 'MB51', 'MM03', 'MMBE', 'XK01', 'MIGO_GR', 'MIRO']
    },
    'SD': {
        'description': 'Sales and Distribution',
        'components': ['Sales Order Management', 'Pricing', 'Shipping', 'Billing', 'Customer Master', 'Credit Management'],
        'keywords': ['sales', 'distribution', 'customer', 'order', 'delivery', 'shipping', 'billing', 'pricing', 'credit management'],
        'tables': ['VBAK', 'VBAP', 'VBFA', 'VBRK', 'VBRP', 'KNA1', 'KNVV', 'LIKP', 'LIPS', 'A004', 'KONV'],
        'transactions': ['VA01', 'VA02', 'VA03', 'VL01N', 'VL02N', 'VL03N', 'VF01', 'VF02', 'VF03', 'VKM1', 'FD32']
    },
    'PP': {
        'description': 'Production Planning',
        'components': ['Material Requirements Planning', 'Production Orders', 'Capacity Planning', 'Routings', 'BOM Management'],
        'keywords': ['production', 'manufacturing', 'MRP', 'capacity', 'BOM', 'routing', 'work center', 'shop floor'],
        'tables': ['AUFK', 'AFKO', 'AFVC', 'AFVV', 'RESB', 'STKO', 'STAS', 'PLAF', 'CRHD', 'MKAL', 'PLPO'],
        'transactions': ['MD01', 'MD02', 'CO01', 'CO02', 'CO03', 'CS01', 'CS02', 'CA01', 'CA02', 'CR01', 'CM01']
    },
    'HCM': {
        'description': 'Human Capital Management',
        'components': ['Personnel Administration', 'Organizational Management', 'Time Management', 'Payroll', 'Benefits'],
        'keywords': ['HR', 'human resources', 'personnel', 'employees', 'payroll', 'time management', 'organizational structure', 'benefits'],
        'tables': ['PA0001', 'PA0002', 'PA0003', 'PA0006', 'PA0008', 'HRPE', 'T001P', 'T549A', 'T559L', 'HRP1000', 'HRP1001'],
        'transactions': ['PA30', 'PA40', 'PA20', 'PPOME', 'PT60', 'PC00_M99_CALC', 'PC00_M99_CIPE', 'PC00_M99_UWTN', 'PC00_M99_UPES']
    },
    'EWM': {
        'description': 'Extended Warehouse Management',
        'components': ['Warehouse Structure', 'Inbound Processing', 'Outbound Processing', 'Internal Warehouse Movement', 'Physical Inventory'],
        'keywords': ['warehouse', 'logistics', 'storage', 'bin', 'picking', 'putaway', 'shipping', 'goods receipt', 'stock transfer'],
        'tables': ['/SCWM/ORDIM_C', '/SCWM/ORDIM_O', '/SCWM/AQUA', '/SCWM/LAGP', '/SCWM/TRTTY', '/SCWM/BIN_SEG', '/SCWM/WHO', '/SCWM/DOOR'],
        'transactions': ['/SCWM/MON', '/SCWM/PRDI', '/SCWM/PRDO', '/SCWM/PI', '/SCWM/WMF', '/SCWM/MIG', '/SCWM/RFUI']
    }
}

# Enhanced System Messages for each SAP module
ENHANCED_SYSTEM_MESSAGES = {
    "base": """You are an advanced SAP Assistant created by Mygo Consulting, developed by Vishnu Yeruva.
You specialize in SAP systems, particularly in modules like FI/CO, MM, SD, PP, HCM, and EWM.

Your primary goal is to provide accurate, concise answers to SAP questions while following these guidelines:

1. PRIORITIZE CONCISENESS in your responses - be direct and to the point, avoiding unnecessary words
2. For code examples, provide only essential, working ABAP code snippets
3. Structure your answers in a clear and logical manner, using bullet points when appropriate
4. When explaining SAP concepts, focus on practical implementation details rather than theory
5. Include direct references to relevant SAP transactions, tables, or function modules
6. When discussing customizations, highlight potential impact on standard SAP processes
7. For performance-related questions, emphasize SAP best practices for optimization

About Mygo Consulting:
- SAP Silver Partner specializing in implementations and support
- Strong focus on customer satisfaction and quality delivery
- Expertise in manufacturing, retail, and healthcare industries

Remember to maintain a professional yet approachable tone, and always prioritize SAP best practices.""",

    "fico": """You are now specialized in SAP Financial Accounting and Controlling (FI/CO).

For FI/CO specific questions:
- Frame answers around key financial processes (Record-to-Report, Order-to-Cash, Procure-to-Pay)
- Reference specific GL accounts, profit centers, and cost centers when relevant
- For journal entry questions, provide precise posting examples with account numbers
- When discussing fiscal year configurations, highlight year-end closing implications
- For reporting questions, mention SAP standard reports by transaction code

Common FI/CO transactions to reference: FB01, FB50, F-02, F-28, FAGLB03, KE30, KE24
Important tables: BKPF, BSEG, BSID, BSIK, FAGLFLEXA, COEP

For New G/L specific questions, always clarify if you're discussing Classic G/L or New G/L functionality.""",

    "mm": """You are now specialized in SAP Materials Management (MM).

For MM specific questions:
- Focus on the procurement cycle (PR to PO to GR to IR)
- Reference specific material types, movement types, and account determination
- For purchasing questions, provide examples with document structure
- When discussing inventory management, emphasize stock types and valuation
- For master data questions, highlight different views and their significance

Common MM transactions to reference: ME21N, ME23N, MIGO, MB51, MM03, MIRO
Important tables: EKKO, EKPO, MARA, MARC, MARD, MKPF, MSEG

Always distinguish between classic MM and S/4HANA simplified logistics where appropriate.""",

    "sd": """You are now specialized in SAP Sales and Distribution (SD).

For SD specific questions:
- Structure answers around the order-to-cash process
- Reference specific sales document types, item categories, and schedule line categories
- For pricing questions, highlight condition technique components
- When discussing delivery processing, emphasize picking, packing, and goods issue
- For billing questions, clarify invoice types and billing plan options

Common SD transactions to reference: VA01, VA02, VA03, VL01N, VL02N, VF01, VF03
Important tables: VBAK, VBAP, VBFA, VBRK, VBRP, KNA1, KNVV

Always mention integration points with other modules (MM, FI) when relevant.""",

    "pp": """You are now specialized in SAP Production Planning (PP).

For PP specific questions:
- Focus on the production planning and execution process
- Reference specific production order types, BOM types, and routing operations
- For MRP questions, highlight planning strategies and lot-sizing procedures
- When discussing capacity planning, emphasize work center concepts
- For production execution, clarify confirmation strategies and backflushing

Common PP transactions to reference: MD01, MD02, CO01, CO02, CO03, CS01, CA01
Important tables: AUFK, AFKO, AFVC, RESB, STKO, PLAF, CRHD

Always distinguish between discrete, repetitive, and process manufacturing where appropriate.""",

    "hcm": """You are now specialized in SAP Human Capital Management (HCM).

For HCM specific questions:
- Structure answers around the employee lifecycle
- Reference specific infotypes and their numbers (e.g., Basic Pay - Infotype 0008)
- For organizational management, highlight position vs. job concepts
- When discussing time management, clarify time evaluation rules
- For payroll questions, explain processing classes and wage types

Common HCM transactions to reference: PA30, PA40, PA20, PPOME, PT60
Important tables: PA0001, PA0002, PA0003, PA0006, HRP1000, HRP1001

Always distinguish between on-premise HCM and SuccessFactors where appropriate.""",

    "ewm": """You are now specialized in SAP Extended Warehouse Management (EWM).

For EWM specific questions:
- Focus on the warehouse processes and structure
- Reference specific storage types, sections, and bin types
- For inbound processing, highlight putaway strategies
- When discussing outbound processing, emphasize wave management
- For physical inventory, clarify counting procedures

Common EWM transactions to reference: /SCWM/MON, /SCWM/PRDI, /SCWM/PRDO, /SCWM/PI
Important tables: /SCWM/ORDIM_C, /SCWM/ORDIM_O, /SCWM/AQUA, /SCWM/LAGP

Always distinguish between EWM and WM (Warehouse Management) functionality."""
}

# Few-shot learning examples for common SAP queries
FEW_SHOT_EXAMPLES = {
    "fico": [
        {
            "query": "How do I post a customer invoice in SAP?",
            "response": """To post a customer invoice:

1. Transaction: FB70 or VF01
2. Enter document header data (posting date, document type DR)
3. Enter customer account (Accounting tab)
4. Enter GL account for revenue (e.g., 400000)
5. Enter amount and tax code
6. Save (Posting simulated in FBV0 first if needed)

Example document:
- Header: Document Type DR, Company Code 1000, Posting Date today
- Line 1: Customer account 1100001, 1,000 EUR, D
- Line 2: Revenue account 400000, 1,000 EUR, C

Note: Use proper document type per your configuration."""
        },
        {
            "query": "How to create a cost center in SAP?",
            "response": """Create a cost center via KS01:

1. Transaction: KS01
2. Enter:
   - Controlling Area (e.g., 1000)
   - Cost Center ID (e.g., 1000100)
   - Valid from date
3. In Basic Data tab:
   - Description
   - Hierarchy Area
   - Person Responsible
   - Cost Center Category
4. In Control Data tab:
   - Profit Center assignment
   - Functional Area
5. Save

Key fields for integration:
- Profit Center (for financial reporting)
- Functional Area (for financial statements)
- Cost Center Category (for reporting)

Tables: CSKS (basic data), CSKT (descriptions)"""
        }
    ],
    "mm": [
        {
            "query": "How to create a purchase order in SAP?",
            "response": """Create a purchase order:

1. Transaction: ME21N
2. Header data:
   - Vendor (e.g., 100123)
   - Purchase Organization
   - Purchasing Group
   - Company Code
3. Item data:
   - Material or service
   - Quantity
   - Delivery date
   - Plant
   - Storage location
4. Pricing conditions
5. Save

Key tables: EKKO (header), EKPO (items)
Related: Material master (MM03), Vendor master (XK03)

Tips:
- Use ME31L to create with reference to a PR
- Use ME21N with "Create with Reference" for contract references"""
        },
        {
            "query": "How to perform a goods receipt against a purchase order?",
            "response": """Goods receipt against PO:

1. Transaction: MIGO
2. Select "Goods Receipt" and "Purchase Order"
3. Enter PO number
4. System displays PO items
5. Enter/adjust:
   - Quantity received
   - Storage location
   - Movement type (101 for standard GR)
6. Check "Item OK" and Post

Key points:
- Movement type 101 = GR into unrestricted stock
- Document posted: Material Document (MIGO_GR)
- Tables updated: MKPF (header), MSEG (items), MARD (stock)
- Creates accounting document (if enabled)

Tip: Use "Hold Document" to save as draft before posting"""
        }
    ]
}

# Create advanced system message with module context
def get_enhanced_system_message(module_name=None):
    """
    Generate an enhanced system message with SAP-specific context.
    
    Args:
        module_name: The SAP module to focus on (e.g., 'fico', 'mm')
        
    Returns:
        str: The enhanced system message
    """
    base_message = ENHANCED_SYSTEM_MESSAGES["base"]
    
    if module_name and module_name.lower() in ENHANCED_SYSTEM_MESSAGES:
        module_message = ENHANCED_SYSTEM_MESSAGES[module_name.lower()]
        # Combine base message with module-specific guidance
        return f"{base_message}\n\n{module_message}"
    
    return base_message

# Simple in-memory cache for common queries
# In production, this should be replaced with Redis or another caching system
response_cache = {}
cache_expiry = {}
CACHE_LIFETIME = timedelta(hours=24)  # Cache responses for 24 hours

def get_cache_key(module, query):
    """Generate a unique cache key for a query in a specific module"""
    # Normalize the query to increase cache hits
    normalized_query = query.lower().strip()
    
    # Remove common filler words/phrases that don't change the meaning
    filler_words = [
        "please", "could you", "can you", "tell me", "i want to know", 
        "how do i", "how to", "what is", "explain", "help with"
    ]
    for word in filler_words:
        normalized_query = normalized_query.replace(word, "").strip()
    
    # Create a hash for the cache key
    key = f"{module.lower()}:{normalized_query}"
    return hashlib.md5(key.encode()).hexdigest()

def get_cached_response(module, query):
    """Get a cached response if available and not expired"""
    cache_key = get_cache_key(module, query)
    
    if cache_key in response_cache:
        # Check if the cache entry has expired
        if datetime.now() < cache_expiry.get(cache_key, datetime.min):
            return response_cache[cache_key]
        else:
            # Clean up expired entry
            del response_cache[cache_key]
            del cache_expiry[cache_key]
    
    return None

def cache_response(module, query, response):
    """Cache a response for future use"""
    cache_key = get_cache_key(module, query)
    response_cache[cache_key] = response
    cache_expiry[cache_key] = datetime.now() + CACHE_LIFETIME
    
    # Simple cache size management - remove oldest entries if cache grows too large
    if len(response_cache) > 1000:  # Arbitrary limit
        oldest_key = min(cache_expiry.items(), key=lambda x: x[1])[0]
        del response_cache[oldest_key]
        del cache_expiry[oldest_key]

# Function to extract relevant SAP knowledge based on query
def extract_sap_context(query, module):
    """
    Extract relevant SAP knowledge and context based on user query and selected module.
    This enhances the prompt with domain-specific knowledge.
    """
    # Lowercase the query for easier matching
    query_lower = query.lower()
    
    # Default to an empty context
    extracted_context = []
    
    # 1. Check if module is valid and get module info
    module_lower = module.lower()
    if module_lower == 'fico':
        module_data = SAP_MODULES['FI/CO']
    elif module_lower in ['mm', 'sd', 'pp', 'hcm', 'ewm']:
        module_data = SAP_MODULES[module_lower.upper()]
    else:
        # If no specific module, return minimal context
        return ""
    
    # 2. Check for keywords in the query
    relevant_keywords = [kw for kw in module_data.get('keywords', []) if kw in query_lower]
    
    # 3. Check for transactions in the query
    transactions_pattern = r'\b[A-Z]{2}\d{2}[A-Z]?\b|/[A-Z]{4}/[A-Z0-9_]+'
    mentioned_transactions = re.findall(transactions_pattern, query.upper())
    relevant_transactions = [t for t in mentioned_transactions if t in module_data.get('transactions', [])]
    
    # 4. Check for tables in the query
    tables_pattern = r'\b[A-Z]{4}\b|/[A-Z]{4}/[A-Z0-9_]+'
    mentioned_tables = re.findall(tables_pattern, query.upper())
    relevant_tables = [t for t in mentioned_tables if t in module_data.get('tables', [])]
    
    # 5. Build the context based on what was found
    if relevant_keywords:
        extracted_context.append(f"Related SAP concepts: {', '.join(relevant_keywords)}")
    
    if relevant_transactions:
        extracted_context.append(f"SAP Transactions mentioned: {', '.join(relevant_transactions)}")
        
        # Add transaction descriptions for context
        for tx in relevant_transactions:
            # In a real system, you'd look up the transaction description from a database
            extracted_context.append(f"Transaction {tx} is relevant to {module_data['description']}")
    
    if relevant_tables:
        extracted_context.append(f"SAP Tables mentioned: {', '.join(relevant_tables)}")
        
        # Add table descriptions for context
        for table in relevant_tables:
            # In a real system, you'd look up the table description from a database
            extracted_context.append(f"Table {table} is used in {module_data['description']}")
    
    # 6. Add few-shot examples if available for this module
    if module_lower in FEW_SHOT_EXAMPLES:
        examples = FEW_SHOT_EXAMPLES[module_lower]
        
        # Find most relevant example based on keyword matching
        best_example = None
        best_match_score = 0
        
        for example in examples:
            example_query = example['query'].lower()
            match_score = sum(1 for kw in relevant_keywords if kw in example_query)
            
            if match_score > best_match_score:
                best_match_score = match_score
                best_example = example
        
        if best_example and best_match_score > 0:
            extracted_context.append(f"\nExample Q&A for reference:\n")
            extracted_context.append(f"Question: {best_example['query']}")
            extracted_context.append(f"Answer: {best_example['response']}")
    
    return "\n".join(extracted_context)

# Function to optimize user messages before sending to GPT
def optimize_user_message(user_message, module=None):
    """
    Optimize the user message by adding instructions and context
    to help the model provide more efficient responses.
    """
    # Extract any relevant SAP context
    sap_context = extract_sap_context(user_message, module) if module else ""
    
    # Create an optimized user message with specific instruction to be concise
    optimized_message = f"""
{user_message}

Instructions:
1. Focus only on SAP {module.upper() if module else 'knowledge'} in your response
2. Be concise and direct - limit explanations to essential points
3. Provide specific transaction codes, table names, and field names where relevant
4. Include ABAP code only if specifically requested
5. Separate your response into clear sections with headings if applicable

{sap_context}
"""
    return optimized_message

# Create AI messages with optimized context
def create_optimized_messages(module, query, conversation_history):
    """
    Create an optimized message array for the OpenAI API call.
    
    Args:
        module: The SAP module context (e.g., 'fico', 'mm')
        query: The user's query text
        conversation_history: The previous conversation messages
        
    Returns:
        list: List of message objects for the API call
    """
    # Get the cached response if available
    cached_response = get_cached_response(module, query)
    if cached_response:
        return cached_response
    
    # Get enhanced system message
    system_message = get_enhanced_system_message(module)
    
    # Start with the system message
    messages = [
        {"role": "system", "content": system_message}
    ]
    
    # Add conversation history (limited to last few exchanges to reduce tokens)
    # Use at most the last 5 exchanges (10 messages) to keep context window small
    recent_history = list(conversation_history)[-10:] if conversation_history else []
    messages.extend(recent_history)
    
    # Optimize user query and add to messages
    optimized_query = optimize_user_message(query, module)
    messages.append({"role": "user", "content": optimized_query})
    
    return messages

# Optimization flags for the OpenAI client call
def get_optimized_parameters(module=None):
    """
    Get optimized parameters for the OpenAI API call based on the module.
    Different modules might benefit from different temperature settings.
    
    Args:
        module: The SAP module (e.g., 'fico', 'mm')
        
    Returns:
        dict: Parameters for the API call
    """
    # Base parameters
    parameters = {
        "temperature": 0.2,  # Lower temperature for more deterministic responses
        "top_p": 0.85,       # Focus on more likely tokens
        "frequency_penalty": 0.0,
        "presence_penalty": 0.0,
        "timeout": 30,       # 30-second timeout to prevent long waits
    }
    
    # Module-specific adjustments
    if module:
        module = module.lower()
        if module in ['fico', 'mm', 'ewm']:  # More technical modules
            parameters["temperature"] = 0.1  # Even more precise
        elif module in ['sd', 'pp']:         # Moderate technical complexity
            parameters["temperature"] = 0.2
        elif module in ['hcm']:              # More conceptual
            parameters["temperature"] = 0.3
    
    return parameters

# Process user message and prepare optimized GPT-4o request
def process_message_for_gpt(module, user_message, conversation_history):
    """
    Process a user message and prepare an optimized request for GPT-4o.
    
    Args:
        module: The SAP module (e.g., 'fico', 'mm')
        user_message: The user's message text
        conversation_history: The previous conversation messages
        
    Returns:
        tuple: (messages, parameters) for the OpenAI API call
    """
    # Prepare optimized messages
    messages = create_optimized_messages(module, user_message, conversation_history)
    
    # Get optimized parameters
    parameters = get_optimized_parameters(module)
    
    return messages, parameters

# Function to save usage stats for analysis
def log_usage_stats(module, query, tokens_input, tokens_output, response_time):
    """Log API usage statistics for later analysis and optimization"""
    stats = {
        "timestamp": datetime.now().isoformat(),
        "module": module,
        "query_length": len(query),
        "tokens_input": tokens_input,
        "tokens_output": tokens_output,
        "response_time": response_time,
    }
    
    # In a real implementation, save stats to a database or log file
    # For simplicity, we'll append to a JSON file
    log_file = "sap_assistant_usage_stats.json"
    
    try:
        # Create or append to log file
        if os.path.exists(log_file):
            with open(log_file, 'r') as f:
                log_data = json.load(f)
        else:
            log_data = []
        
        log_data.append(stats)
        
        with open(log_file, 'w') as f:
            json.dump(log_data, f, indent=2)
    except Exception as e:
        print(f"Error logging usage stats: {e}")
