from flask import Flask, request, jsonify,render_template
from openai import OpenAI
import openai
import logging
import traceback
import time
import os

assistant_id="asst_D8x26bB9HstXP5EaqiI5ejaX"
client=OpenAI(api_key = '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')
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