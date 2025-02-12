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
for x in lista:
    if x.filename.endswith(".csv"):

      client.files.delete(x.id)
    print(x.filename)
    files_id_list.append(x.id) 

"""vector_store_files = client.beta.vector_stores.files.list(
  vector_store_id="vs_wPopVll0WXdAaEEiBGEH1g4M"
)
vector_file_id_list=[]
for x in vector_store_files:
    print(x.id)
    vector_file_id_list.append(x.id)
for x in files_id_list:
            if x not in vector_file_id_list:
                non_vector_store_files.append(x)
    

"""
vector_stores = client.beta.vector_stores.list()
print(vector_stores)
exit()

vector_store = client.beta.vector_stores.create(
  name="Support FAQ"
)
"""
#upload all files in file_vault folder one by one
files_list=os.listdir("uploads")
#files_id_list=[]
for i,file in enumerate(files_list):
  

  try:
     
      file_upl=client.files.create(
        file=open(f"uploads/{file}", "rb"),
        purpose='assistants'
      )
        
      if(file.endswith(".docx") or file.endswith(".doc") or file.endswith(".pdf") or file.endswith(".txt") or file.endswith(".pptx")):
          vector_file_id_list.append(file_upl.id)
          vector_store_file_batch = client.beta.vector_stores.file_batches.create(
          vector_store_id="vs_wPopVll0WXdAaEEiBGEH1g4M",
          file_ids=vector_file_id_list,
            ) 
          client.beta.assistants.update(
            assistant_id,
            
            tool_resources={"code_interpreter": {"file_ids":non_vector_store_files},"file_search": {"vector_store_ids": ["vs_wPopVll0WXdAaEEiBGEH1g4M"]}},

        )         
          
      else:
        
        
        non_vector_store_files.append(file_upl.id) 
        assistant = client.beta.assistants.update(
            assistant_id,
            
            tool_resources={"code_interpreter": {"file_ids":non_vector_store_files},"file_search": {"vector_store_ids": ["vs_wPopVll0WXdAaEEiBGEH1g4M"]}},

        )

    
      
      #os.remove(f"uploads/{file}")
  except:
    traceback.print_exc()
    pass  
  




"""