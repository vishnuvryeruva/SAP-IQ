import boto3
import subprocess
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash

from openai import OpenAI
import logging
import traceback
import time
import os
from collections import deque




client=OpenAI(api_key = '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')
app = Flask(__name__)
app.secret_key = 'key_key_key_key_key'

# Directory for uploaded files
UPLOAD_FOLDER = 'uploads'
HISTORY_FILE = 'conversation_history.txt'
CONVERSATION_LENGTH = 5  # Number of messages to keep in history
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)


# Initialize conversation history
conversation_history = deque(maxlen=CONVERSATION_LENGTH)

def save_conversation_to_file(history, filename):
    """Save the conversation history to a file."""
    with open(filename, 'w') as file:
        for message in history:
            file.write(f"{message['role']}: {message['content']}\n")

def load_conversation_from_file(filename):
    """Load the conversation history from a file."""
    if os.path.exists(filename):
        with open(filename, 'r') as file:
            lines = file.readlines()
        return [line.strip() for line in lines]
    return []
# User storage (for demonstration)
users = {
    'admin': 'password123',
    'user1': 'mypassword'
}
assistant_id="asst_D8x26bB9HstXP5EaqiI5ejaX"
@app.route('/')
def index():
    return render_template('index.html')
@app.route("/answer", methods=["GET", "POST"])
def answer():
        data = request.get_json()
        message = data["message"]
        conversation_history.append({'role': 'user', 'content': message})
        save_conversation_to_file(conversation_history, HISTORY_FILE)

        # Prepare system prompt with the last N messages
        system_prompt = "\n".join(
            [f"{entry['role']}: {entry['content']}" for entry in conversation_history]
        )
        def generate():
          try:  
            thread = client.beta.threads.create()
            thread_message = client.beta.threads.messages.create(
                thread_id=thread.id,
                role="user",
                content=system_prompt  # Send the conversation history as the system prompt
            )
            thread_message = client.beta.threads.messages.create(
                thread_id=thread.id,
                role="user",
                content=message
            )

            stream=client.beta.threads.runs.create(thread_id=thread.id, assistant_id=assistant_id, timeout=60,stream=True,max_completion_tokens=2000)
            final_text=""
            

        
            for event in stream:
                print(event.data.object)
                
                if(event.data.object=="thread.run.step.delta"):
                   print(event.data.delta) 
                if(event.data.object=="thread.message.delta"):
                    for content in event.data.delta.content:
                        
                        if(content.type=="text"):
                            final_text=final_text+content.text.value
                            """if(final_text==""):
                                print("EMPTY")
                            else:
                                print(final_text) """   
                            yield(content.text.value)
                            
          except Exception as e:
            raise e                  
        def generate_after_change():
            
                            my_assistants = client.beta.assistants.list(
                                                                order="desc",
                                                                limit="20",
                                                            )
                            for x in my_assistants:

                                if( x.id==assistant_id and x.model=="gpt-4-turbo"):
                                    new_model="gpt-4o"
                                else:
                                    new_model="gpt-4-turbo"
                            try:
                                client.beta.assistants.update(
                                assistant_id,
                                tools=[{"type":"file_search"},{"type":"code_interpreter"}],


                                model=new_model
                                )
                                print("MODEL SWITCHED",new_model)
                                thread = client.beta.threads.create()
                                thread_message = client.beta.threads.messages.create(
                                    thread_id=thread.id,
                                    role="user",
                                    content=message,
                                )

                                stream=client.beta.threads.runs.create(thread_id=thread.id, assistant_id=assistant_id, timeout=60,stream=True)
                                final_text=""
                                for event in stream:
                                    
                                    if(event.data.object=="thread.message.delta"):
                                        for content in event.data.delta.content:
                                            if(content.type=="text"):
                                                final_text=final_text+content.text.value
                                                """if(final_text==""):
                                                    print("EMPTY")
                                                else:
                                                    print(final_text) """   
                                                yield(content.text.value) 
                                                    
                            except Exception as e:
                                                    return(e)     
                               
                            
        try:
            return generate(), {"Content-Type": "text/plain"}
        except:
             return generate_after_change(), {"Content-Type": "text/plain"}
@app.route('/login', methods=['POST','GET'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if username in users and users[username] == password:
            session['username'] = username
            # Return success message in JSON format
            return jsonify({'success': True, 'message': 'Login successful!'})
        else:
            # Return failure message in JSON format
            return jsonify({'success': False, 'message': 'Invalid username or password'})
    return render_template("login.html")    
@app.route('/upload', methods=['POST'])
def upload_file():
    x=os.listdir('uploads/')
    for z in x:
       os.remove(f"uploads/{z}")
    # Check if the user is logged in
    if 'username' not in session:
        flash('You must be logged in to upload files.', 'danger')
        return redirect(url_for('login'))

    # Get the prompt and file from the form
    #prompt = request.form.get('prompt')
    file = request.files.get('file')

    # Validate inputs
    if not file:
        flash('Prompt and file are required!', 'danger')
        return redirect(url_for('login'))

    # Save the file to the upload folder
    try:
        filename = file.filename
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        try:
             xoxo=file_management(filename)
             print(xoxo)
        except:
             pass     
        flash('File uploaded successfully!', 'success')
    except Exception as e:
        traceback.print_exc()
        flash(f'Error uploading file: {e}', 'danger')

    # Redirect to the home page after upload
    return redirect(url_for('index'))
@app.route('/logout')
def logout():
    session.pop('username', None)
    flash('You have successfully logged out.', 'info')
    return redirect(url_for('index'))
def file_management(filename):
  
  aws_access_key_id = 'AKIAS74TL54QO24WOPEC'
  aws_secret_access_key = '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'
  assistant_id="asst_D8x26bB9HstXP5EaqiI5ejaX"
  client=OpenAI(api_key = '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')
  files_id_list=[]
  non_vector_store_files=[]
  lista=client.files.list()
  for x in lista:
      print(x.filename)
      files_id_list.append(x.id) 
  vector_store_files = client.beta.vector_stores.files.list(
    vector_store_id="vs_wPopVll0WXdAaEEiBGEH1g4M"
  )
  vector_file_id_list=[]
  for x in vector_store_files:
    print(x.id)
    vector_file_id_list.append(x.id)
  for x in files_id_list:
            if x not in vector_file_id_list:
                non_vector_store_files.append(x)

      

  """vector_stores = client.beta.vector_stores.list()
  print(vector_stores)
  exit()

  vector_store = client.beta.vector_stores.create(
    name="Support FAQ"
  )"""
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
        
            for x in files_id_list:
                if x not in vector_file_id_list:
                    non_vector_store_files.append(x)
            non_vector_store_files.append(file_upl.id) 
            assistant = client.beta.assistants.update(
                assistant_id,
                
                tool_resources={"code_interpreter": {"file_ids":non_vector_store_files},"file_search": {"vector_store_ids": ["vs_wPopVll0WXdAaEEiBGEH1g4M"]}},

            )

      
        
        def upload_to_s3(filename):
                  
                  session = boto3.Session(
                      aws_access_key_id=aws_access_key_id,
                      aws_secret_access_key=aws_secret_access_key
                  )
                  s3 = session.client('s3')
                  try:
                          with open("uploads/"+filename, 'rb') as file_data:    
                              response = s3.put_object(
                                      Bucket="mygo-sapiq",
                                      Key=filename,
                                      Body=file_data
                                  )
                          status_s3="SUCCESS"
                          #print(status_s3)
                          return("SUCCESS")
                  except Exception as e: 
                              
                              status_s3=f"ERROR {e}" 
                              #print(status_s3)
                              return status_s3 
                  

        upload_to_s3(filename)         
        #os.remove(f"uploads/{file}")
    except:
      traceback.print_exc()
      pass  
  
  return "SUCCESS"
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))  # Get the PORT from environment or default to 5000
    app.run(host="0.0.0.0", port=port, debug=True)