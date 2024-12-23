from fastapi import WebSocket
from typing import Dict, Set
import json

class ConnectionManager:
    def __init__(self):
        # quiz_code -> set of WebSocket connections
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        # websocket -> (quiz_code, user_info)
        self.connection_info: Dict[WebSocket, tuple[str, dict]] = {}

    async def connect(self, websocket: WebSocket, quiz_code: str, user_info: dict):
        if quiz_code not in self.active_connections:
            self.active_connections[quiz_code] = set()
        self.active_connections[quiz_code].add(websocket)
        self.connection_info[websocket] = (quiz_code, user_info)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.connection_info:
            quiz_code, _ = self.connection_info[websocket]
            if quiz_code in self.active_connections:
                self.active_connections[quiz_code].remove(websocket)
                if not self.active_connections[quiz_code]:
                    del self.active_connections[quiz_code]
            del self.connection_info[websocket]

manager = ConnectionManager()
