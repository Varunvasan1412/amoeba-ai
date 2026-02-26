# Amoeba AI v1 FIXED — Do not extend without version bump

import time
from collections import defaultdict
from app.services.audit_service import log_audit

class RateLimiter:  
    def __init__(self):
        # Stores [timestamp, ...] for each client_id
        self._chat_limits = defaultdict(list)
        self._export_limits = defaultdict(list)
        
    def check_chat(self, client_id: int) -> bool:
        """Max 60 messages per minute"""
        now = time.time()
        timestamps = self._chat_limits[client_id]
        
        # Filter out old
        timestamps = [t for t in timestamps if now - t < 60]
        self._chat_limits[client_id] = timestamps
        
        if len(timestamps) >= 60:
            log_audit(client_id, "rate_limit_exceeded", {"type": "chat"})
            return False
            
        self._chat_limits[client_id].append(now)
        return True

    def check_export(self, client_id: int) -> bool:
        """Max 10 exports per hour"""
        now = time.time()
        timestamps = self._export_limits[client_id]
        
        # Filter out old (3600 seconds)
        timestamps = [t for t in timestamps if now - t < 3600]
        self._export_limits[client_id] = timestamps
        
        if len(timestamps) >= 10:
            log_audit(client_id, "rate_limit_exceeded", {"type": "export"})
            return False
            
        self._export_limits[client_id].append(now)
        return True

# Singleton
limiter = RateLimiter()
