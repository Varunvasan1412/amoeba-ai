from typing import Optional, Any
from app.services.audit_service import log_event

class NavigationService:
    @staticmethod
    def log_navigation(
        user_id: str, 
        route: str, 
        module: Optional[str] = None,
        client_id: Optional[int] = None,
        ip_address: Optional[str] = None
    ):
        log_event(
            client_id=client_id,
            user_id=user_id,
            action="NAVIGATION",
            entity="App Navigation",
            record_id=route, # Assuming 'route' is the record_id, as 'path' is not defined in the original signature
            source="USER",
            status="SUCCESS",
            details={"route": route, "module": module}, # Keeping original details structure as 'path' and 'label' are not defined
            ip_address=ip_address
        )
