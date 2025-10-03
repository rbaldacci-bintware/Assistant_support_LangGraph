# app/internal_api_client.py
import os
import json
import logging
from typing import Optional, Dict, Any, List
import requests

class InternalApiClient:
    """Client per chiamare le API C# esistenti"""
    
    def __init__(self, config):
        self.config = config
        self.api_key = config.get("InternalStaticKey")
        if not self.api_key:
            raise ValueError("InternalStaticKey non configurata")
        
        self.logger = logging.getLogger(__name__)
        
        # URL base dalla configurazione
        self.base_url = config.get("RemoteApi", {}).get("BaseUrl", "http://localhost:5010")
        self.google_api_url = config.get("RemoteApi", {}).get("BaseUrlGoogleApi", "http://localhost:5020")
        self.file_service_url = config.get("RemoteApi", {}).get("BaseUrlFileService", "http://localhost:5019")
    
    def _get_headers(self):
        return {
            "X-Api-Key": self.api_key,
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
    
    def post_json(self, endpoint: str, data: Dict) -> Optional[Dict]:
        """POST JSON to endpoint"""
        try:
            response = requests.post(
                endpoint,
                json=data,
                headers=self._get_headers(),
                timeout=90
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                self.logger.error(f"API error: {response.status_code} - {response.text}")
                return None
        except Exception as e:
            self.logger.error(f"Exception calling API: {str(e)}")
            return None
    
    def get_bytes(self, endpoint: str) -> bytes:
        """GET bytes from endpoint"""
        headers = {
            "X-Api-Key": self.api_key,
            "Accept": "application/octet-stream"
        }
        
        response = requests.get(
            endpoint,
            headers=headers,
            timeout=120
        )
        response.raise_for_status()
        return response.content