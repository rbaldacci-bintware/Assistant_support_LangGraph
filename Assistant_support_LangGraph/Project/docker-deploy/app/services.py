# app/services.py
import os
import logging
from typing import Optional, List

import requests
from .models import SaveConvRequest, SaveReconstructionResponse, ReconstructionResponse
from .internal_api_client import InternalApiClient

class PersistenceClient:
    """Client per salvare nel database"""
    
    def __init__(self, api_client: InternalApiClient):
        self.api_client = api_client
        self.logger = logging.getLogger(__name__)
        self.base_url = api_client.base_url
    
    def save_conversation(self, conversation_id: str, transcript: str, type: str) -> Optional[SaveReconstructionResponse]:
        """Salva la conversazione nel database"""
        endpoint = f"{self.base_url}/api/internal/InternalRgConvTrs"
        
        payload = {
            "convName": conversation_id,
            "transcribe": transcript,
            "type":type
        }
        
        result = self.api_client.post_json(endpoint, payload)
        
        if result:
            return SaveReconstructionResponse(**result)
        else:
            return SaveReconstructionResponse(status="ERROR", id=None)

class AudioTools:
    """Tools per gestione audio"""
    
    def __init__(self, api_client: InternalApiClient):
        self.api_client = api_client
        self.logger = logging.getLogger(__name__)
    
    def reconstruct_from_storage(
        self,
        location: str,
        inbound_filename: str,
        outbound_filename: str,
        project_name: str
    ) -> ReconstructionResponse:
        """Scarica file e ricostruisce conversazione"""
        
        # URL dei file
        file_service_url = self.api_client.file_service_url
        url_in = f"{file_service_url}/api/files/{location}/{inbound_filename}"
        url_out = f"{file_service_url}/api/files/{location}/{outbound_filename}"
        
        # Scarica i byte
        inbound_bytes = self.api_client.get_bytes(url_in)
        outbound_bytes = self.api_client.get_bytes(url_out)
        
        # Prepara multipart form
        files = [
            ('files', (inbound_filename, inbound_bytes, 'audio/mpeg')),
            ('files', (outbound_filename, outbound_bytes, 'audio/mpeg'))
        ]
        
        # Chiama API reconstruct
        google_api_url = self.api_client.google_api_url
        endpoint = f"{google_api_url}/api/Audio/reconstruct"
        params = {"project_name": project_name}
        
        response = requests.post(
            endpoint,
            files=files,
            params=params,
            headers={"X-Api-Key": self.api_client.api_key},
            timeout=120
        )
        
        if response.status_code == 200:
            data = response.json()
            return ReconstructionResponse(**data)
        else:
            return ReconstructionResponse()