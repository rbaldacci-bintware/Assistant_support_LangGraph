# test_script.py
import requests
import json

def test_local_files():
    url = "http://localhost:8000/transcribe-conversation-from-paths/"
    
    # USA PERCORSI REALI dei tuoi file MP3
    data = {
        "file1": "C:/Users/rikka/Downloads/72aaba06-4267-443f-bf87-f50141e97734_inbound.mp3",  # Windows
        "file2": "C:/Users/rikka/Downloads/72aaba06-4267-443f-bf87-f50141e97734_outbound.mp3"
        # Linux/Mac: "/home/user/test_inbound.mp3"
    }
    
    response = requests.post(url, json=data)
    print(json.dumps(response.json(), indent=2))

def test_complete_workflow():
    url = "http://localhost:8000/api/graph/run"
    
    # Usa file REALI che esistono nel tuo FileService
    payload = {
        "input": "",
        "state": {
            # Questi file devono esistere nel tuo FileService C#
            "location": "conversations-audio",
            "inbound": "72aaba06-4267-443f-bf87-f50141e97734_inbound.mp3",  # File reale
            "outbound": "72aaba06-4267-443f-bf87-f50141e97734_outbound.mp3",
            
            "tenant_key": "COESO_INTERV",
            "conversationId": "test-conv-001",
            
            "co_code": "TEST",
            "orgn_code": "TST", 
            "user_id": "test.user",
            "caller_id": "+39123456789",
            
            "scope": ["MAIL_RT"]
        }
    }
    
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        result = response.json()
        
        print("=== RISULTATO WORKFLOW ===")
        print(f"Status: {response.status_code}")
        
        if 'state' in result:
            print(f"Trascrizione: {result['state'].get('transcript', 'N/A')[:200]}...")
            print(f"Persistenza: {result['state'].get('persistence_result', 'N/A')}")
            print(f"Analisi clusters: {result['state'].get('analysis', {}).get('clusters', 'N/A')}")
            print(f"Suggerimenti: {result['state'].get('suggestions', 'N/A')}")
        else:
            print("Risultato:", json.dumps(result, indent=2))
            
    except requests.exceptions.RequestException as e:
        print(f"Errore nella richiesta: {e}")
        if hasattr(e.response, 'text'):
            print(f"Dettagli: {e.response.text}")

if __name__ == "__main__":
    # Scegli quale test eseguire
    print("1. Test con file locali")
    test_local_files()
    
    print("\n2. Test workflow completo")
    test_complete_workflow()