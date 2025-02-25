
import gzip
import json
import requests

def match_micr_opensearch(listowa):
        query = {
                
                "query": {
                    "simple_query_string":{
                    
                        
                        "query":" ".join(listowa),
                        
                        "minimum_should_match":"40%",
                        
                        
                        
                    
                    }
                }
            
            
            } 
            
        



        headers = {"Content-Type": "application/json", "Content-Encoding": "gzip"}

        # Convert the query to JSON and gzip compress it
        query_data = json.dumps(query).encode('utf-8')
        compressed_query = gzip.compress(query_data)

        # Set up the Elasticsearch endpoint and authentication
        # here check for error 
        url = "https://opensearch.bluealgo.com/cheque_data/_search"
        auth = ("admin", r"p^q-P8W$xVFaj%i")

        # Set the headers for the request
        headers = {"Content-Type": "application/json" ,"Content-Encoding":"gzip"}

        # Send the GET request with the query
        response = requests.get(url, data=compressed_query, auth=auth, headers=headers)
        print(response.json()["hits"])
match_micr_opensearch("262002999")        