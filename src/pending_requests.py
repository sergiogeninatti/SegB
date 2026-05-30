# pending_requests.py
import json
from pathlib import Path
from datetime import datetime

class PendingRequestsManager:
    """Gestiona solicitudes de registro pendientes de aprobación"""
    
    def __init__(self, data_dir: str = '/app/debug'):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.requests_file = self.data_dir / "pending_requests.json"
        self._requests = self._load()
    
    def _load(self) -> dict:
        try:
            if self.requests_file.exists():
                with open(self.requests_file, 'r') as f:
                    return json.load(f)
        except Exception:
            pass
        return {"pending": {}, "last_updated": datetime.now().isoformat()}
    
    def _save(self) -> bool:
        try:
            self._requests['last_updated'] = datetime.now().isoformat()
            with open(self.requests_file, 'w') as f:
                json.dump(self._requests, f, indent=2)
            return True
        except Exception:
            return False
    
    def add_request(self, user_id: str, user_data: dict) -> bool:
        """Añadir solicitud pendiente"""
        self._requests['pending'][user_id] = {
            **user_data,
            "requested_at": datetime.now().isoformat(),
            "status": "pending"
        }
        return self._save()
    
    def get_pending(self, user_id: str) -> dict:
        return self._requests['pending'].get(user_id, {})
    
    def approve(self, user_id: str) -> bool:
        """Aprobar usuario (eliminar de pendientes)"""
        if user_id in self._requests['pending']:
            del self._requests['pending'][user_id]
            return self._save()
        return False
    
    def reject(self, user_id: str) -> bool:
        """Rechazar usuario (eliminar de pendientes)"""
        if user_id in self._requests['pending']:
            del self._requests['pending'][user_id]
            return self._save()
        return False
    
    def list_pending(self) -> dict:
        return self._requests['pending'].copy()