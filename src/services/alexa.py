import logging 
import os 
from typing import Optional, Dict, Any, List 
from pathlib import Path
from alexapy import AlexaLogin, AlexaAPI, hide_email
from src.config import Config   

logger = logging.getLogger(__name__)

class AlexaService:
    def __init__(self):
        self._login: Optional[AlexaLogin] = None 
        self._devices: Dict[str, Any] = {}
        self._smart_home_devices: List[Dict] = []
        
    async def initialize(self) -> bool:
        if not Config.AMAZON_EMAIL or not Config.AMAZON_PASSWORD:
            logger.error("Amazon creditals are not configured")
            return False
        
        try:
            self._login = AlexaLogin(
                url=Config.AMAZON_URL,
                email=Config.AMAZON_EMAIL,
                password=Config.AMAZON_PASSWORD,
                outputpath=str(Config.ALEXA_DATA_DIR),
                debug=False
            )
            
            if await self._login.login_with_cookie():
                logger.info(f"Alexa loggin successful for {hide_email(Config.AMAZON_EMAIL)}")
                await self._load_devices()
                return True
            
            if await self._login.login():
                logger.info(f"Alexa loggin successful for {hide_email(Config.AMAZON_EMAIL)}")
                await self._load_devices()
                return True
            
            logger.error("Alexa login failed")
            return False
            
        except Exception as e: 
            logger.error(f"Alexa initialization error: {e}")
            return False
    
    async def _load_devices(self):
        try:
            devices = await AlexaAPI.get_devices(self._login)
            self._devices = {d["accountName"]: d for d in devices.get("devices", [])}
            logger.info(f"Lodaded {len(self._devices)} Echo devices")
            
            self._smart_home_devices = await AlexaAPI.get_smart_home_devices(self._login)
            logger.info(f"Loaded {len(self._smart_home_devices)} smart home devices.")
            
        except Exception as e:
            logger.error(f"Error loading devices: {e}")
            
    async def list_devices(self) -> Dict[str, List[str]]:
        return {
            "echo_devices": list(self._devices.keys()),
            "smart_home_devices": [d.get("name", "Unknown") for d in self._smart_home_devices]
        }
        
    async def set_light(
        self, 
        device_name: str,
        power_on: bool,
        brightness: Optional[int] = None,
        color: Optional[str] = None
    ) -> Dict[str, Any]:
        if not self._login:
            return {"success": False, "error": "Not logged into Alexa."}
        
        device = self._find_smart_home_device(device_name)
        if not device:
            return {"success": False, "error": f"Device {device_name} not found"}
        
        try:
            entity_id = device.get("entityId") or device.get("id")
            
            result = await AlexaAPI.set_light_state(
                login=self._login,
                entity_id=entity_id,
                power_on=power_on,
                brightness=brightness,
                color_name=color
            )
            
            action = "on" if power_on else "off"
            msg = f"Turned {device_name} {action}"
            if brightness is not None:
                msg += f" at {brightness}% brightness"
            if color:
                msg += f" with color {color}"
                
            return {"success": True, "message": msg, "result": result}
            
        except Exception as e:
            logger.error(f"Error controlling light: {e}")
            return {"success": False, "error": str(e)}
    
    
    async def run_routine(self, routine_name: str) -> Dict[str, Any]:
        if not self._login:
            return {"success": False, "error": "Not logged in to Alexa"}
        try:
            routines = await AlexaAPI.get_routines(self._login)
            
            routine = None 
            for r in routines:
                if routine_name.lower() in r.get("name", "").lower():
                    routine = r
                    break
            
            if not routine: 
                available = [r.get("name") for r in routines]
                return {
                    "success": False, 
                    "error": f"Routine '{routine_name}' not found",
                    "available_routines": available
                }
            
            await AlexaAPI.run_routine(self._login, routine)
            return {
                    "success": True, 
                    "error": f"Routine '{routine_name}' executed",
                }
        
        except Exception as e:
            logger.error(f"Error running routine: {e}")
            return {"success": False, "error": str(e)}
    
    async def send_announcements(self, message: str, device_name: Optional[str] = None) -> Dict[str, Any]:
        if not self._login:
            return {"success": False, "error": "Not logged into Alexa."}
        
        try:
            if device_name:
                device = self._devices.get(device_name)
                if not device:
                    return {"success": False, "error": f"Device '{device_name}' not found."}
                
                api = AlexaAPI(device, self._login)
                await api.send_announcement(message)
            else:
                for _, device in self._devices.items():
                    api = AlexaAPI(device, self._login)
                    await api.send_announcement(message)
            
            return {"success": True, "message": f"Announcement sent: {message}"}
    
        except Exception as e:
            logger.error(f"Error sending announcement: {e}")
            return {"success": False, "error": str(e)}
        
    async def send_tts(self, message: str, device_name: str) -> Dict[str, Any]:
        if not self._login:
            return {"success": False, "error": "Not logged into Alexa."}
        
        try: 
            device = self._devices.get(device_name)
            if not device:
                return {
                    "success": False, 
                    "error": f"Device '{device_name}' not found.",
                    "available_devices": list(self._devices.keys())
                }
            api = AlexaAPI(device, self._login)
            await api.send_tts(message)
            return {"success": True, "message": f"Spoke '{message}' on {device_name}"}
        except Exception as e:
            logger.error(f"Error sending TTS: {e}")
            return {"success": False, "error": str(e)}
    
    async def play_music(self, search_phrase: str, device_name: str, provider: str = "SPOTIFY") -> Dict[str, Any]:
        if not self._login:
            return {"success": False, "error": "Not logged into Alexa."}
        
        try:
            device = self._devices.get(device_name)
            if not device:
                return {
                    "success": False, 
                    "error": f"Device '{device_name}' not found.",
                    "available_devices": list(self._devices.keys())
                }
            api = AlexaAPI(device, self._login)
            await api.play_music(provider, search_phrase)
            return {"success": True, "message": f"Playing '{search_phrase}' on {device_name}"}
            
        except Exception as e:
            logger.error(f"Error playing music: {e}")
            return {"success": False, "error": str(e)}
            
        
    
    def _find_smart_home_device(self, name: str) -> Optional[Dict]:
        name_lower = name.lower()
        for device in self._smart_home_devices:
            device_name = device.get("name", "").lower()
            if name_lower in device_name or device_name in name_lower:
                return device
        return None

_alexa_service: Optional[AlexaService] = None

async def get_alexa_service() -> Optional[AlexaService]:
    global _alexa_service
    
    if _alexa_service is None:
        _alexa_service = AlexaService()
        
        if not await _alexa_service.initialize():
            logger.warning("Failed to initialize Alexa service")
            return None
    return _alexa_service


        
            
            
        
        
    