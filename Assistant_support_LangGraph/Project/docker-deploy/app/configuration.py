# configuration.py - VERSIONE FINALE FUNZIONANTE
import os
import json
import base64
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend

class Configuration:
    def __init__(self, config_path: str = "config.json"):
        self._data = {}
        self.config_path = config_path
        self.load_encrypted_environment_file()
    
    def __getitem__(self, key: str) -> str:
        if key not in self._data:
            raise InvalidOperationException(f"La chiave '{key}' non è configurata.")
        return self._data[key]
    
    def get(self, key: str, default=None) -> str:
        return self._data.get(key, default)
    
    def load_encrypted_environment_file(self):
        """Replica LoadEncryptedEnvironmentFile dal C#"""
        with open(self.config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        directory = config.get("EnvFileSettings", {}).get("Directory", "")
        filename = config.get("EnvFileSettings", {}).get("FileName", "")
        
        if not directory or not filename:
            raise InvalidOperationException("Il file di configurazione ambiente non è corretto.")
        
        file_path = os.path.join(directory, filename)
        #print(f"[Program] Percorso file .env criptato: {file_path}")
        
        # Ottieni chiave di cifratura - È GIÀ IN BASE64!
        encryption_key = os.environ.get('CHIAVE_CIFRATURA')
        if not encryption_key:
            raise InvalidOperationException("CHIAVE_CIFRATURA environment variable is not set.")
        
        #print(f"[KEY] CHIAVE_CIFRATURA: {len(encryption_key)} caratteri")
        
        # La chiave È GIÀ Base64 - usala direttamente
        if len(encryption_key) == 32:
            key_base64 = encryption_key  # USA DIRETTAMENTE, NON CONVERTIRE!
            #print(f"[KEY] Usando chiave Base64 direttamente")
        else:
            raise InvalidOperationException(f"La chiave deve essere di 32 caratteri, trovati: {len(encryption_key)}")
        
        # Carica e decripta il file
        variables = self.load_encrypted_env_file(file_path, key_base64)
        
        # Aggiungi alla configurazione
        for key, value in variables.items():
            self._data[key] = value
            os.environ[key] = value
        
        print(f"[Program] File .env decriptato con successo - {len(self._data)} variabili")
    
    def load_encrypted_env_file(self, file_path: str, key_base64: str) -> dict:
        """Replica EnvFileReader.LoadEncryptedEnvFile"""
        variables = {}
        
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Il file .env non esiste: {file_path}")
        
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                
                if not line or line.startswith('#'):
                    continue
                
                if '=' in line:
                    parts = line.split('=', 1)
                    if len(parts) == 2:
                        key = parts[0].strip()
                        encrypted_value = parts[1].strip()
                        
                        try:
                            # Passa key_base64 DIRETTAMENTE al decrypt
                            decrypted_value = self.decrypt(encrypted_value, key_base64)
                            variables[key] = decrypted_value
                            
                            if key == "InternalStaticKey":
                                print(f"[SUCCESS] InternalStaticKey: ")
                        except Exception as e:
                            print(f"[ERROR] Errore decrittando {key}: {str(e)}")
                            continue
        
        return variables
    
    def decrypt(self, encrypted_text: str, key_base64: str) -> str:
        """Replica ESATTA di EncryptionHelper.Decrypt dal C#"""
        encrypted_text = encrypted_text.strip('"\'')
        
        # ESATTAMENTE come il C# - key_base64 È GIÀ Base64!
        key = base64.b64decode(key_base64)  # Convert.FromBase64String(keyBase64)
        encrypted_bytes = base64.b64decode(encrypted_text)  # Convert.FromBase64String(encryptedText)
        
        # Crea AES
        iv = encrypted_bytes[:16]  # Array.Copy(encryptedBytes, iv, iv.Length)
        ciphertext = encrypted_bytes[16:]
        
        # Decrittazione AES-CBC
        cipher = Cipher(
            algorithms.AES(key),
            modes.CBC(iv),
            backend=default_backend()
        )
        
        decryptor = cipher.decryptor()
        decrypted_padded = decryptor.update(ciphertext) + decryptor.finalize()
        
        # Rimuovi padding PKCS7
        padding_length = decrypted_padded[-1]
        
        # Verifica che il padding sia valido (tutti i byte di padding devono essere uguali)
        if padding_length > 0 and padding_length <= 16:
            valid_padding = True
            for i in range(padding_length):
                if decrypted_padded[-(i+1)] != padding_length:
                    valid_padding = False
                    break
            
            if valid_padding:
                # Rimuovi il padding
                decrypted = decrypted_padded[:-padding_length]
            else:
                # Padding non valido, usa tutto
                decrypted = decrypted_padded
        else:
            # Nessun padding o valore non valido
            decrypted = decrypted_padded
        
        return decrypted.decode('utf-8')

class InvalidOperationException(Exception):
    pass

def initialize_configuration(config_path: str = "config.json"):
    return Configuration(config_path)