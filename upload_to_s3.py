from flask import Flask, request, jsonify, render_template
from openai import OpenAI
import openai
import logging
import traceback
import time
import os

# Import centralized configuration
from config import *

# Use configuration variables
client = OpenAI(api_key=OPENAI_API_KEY)
files_id_list=[]
non_vector_store_files=[]
lista=client.files.list()
"""for x in lista:
    client.files.delete(x.id)
lista=client.files.list()
for x in lista:
    print(x.id)    
vector_stores = client.beta.vector_stores.list()
vector_ids=[]
for x in vector_stores:
    try:
        client.beta.vector_stores.delete(x.id)
    except:
        pass """   
new_vec=client.beta.vector_stores.create(name="Files for assistant")
print(new_vec.id)