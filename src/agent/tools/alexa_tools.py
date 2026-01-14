from langchain_core.tools import tool 
from src.services.alexa import get_alexa_service
from typing import Optional
import logging

logger = logging.getLogger(__name__)

@tool 
async def control_light(
    device_name: str,
    action: str, 
    brightness: Optional[int] = None, 
    color: Optional[str] = None 
) -> str: 
    """
    Control a smart home light connected to Alexa.
    
    Args:
        device_name: Name of the light (e.g., "Living Room Light", "Bedroom Lamp")
        action: "on" or "off"
        brightness: Optional brightness level 0-100
        color: Optional color name (e.g., "warm_white", "red", "blue", "daylight")
    
    Returns:
        Result message
    """
    service = await get_alexa_service()
    if not service:
        return "Alexa service not available. Check credentials and try again."
    
    power_on = action.lower() == "on"
    result = await service.set_light(device_name=device_name, power_on=power_on, brightness=brightness, color=color)
    
    if result["success"]:
        return result["message"]
    else:
        return result["error"]
    
@tool 
async def list_smart_devices() -> str:
    """
    List all smart home devices connected to Alexa.
    
    Returns:
        List of available Echo devices and smart home devices
    """
    service = await get_alexa_service()
    if not service:
        return "Alexa service not available. Check credentials and try again."
    
    devices = await service.list_devices()
    
    lines = ["**Echo Devices:**"]
    for d in devices["echo_devices"]:
        lines.append(f"  - {d}")
        
    lines.append("\n**Smart Home Devices:**")
    for d in devices["smart_home_devices"]:
        lines.append(f"  - {d}")
        
    return "\n".join(lines)

@tool
async def run_alexa_routine(routine_name: str) -> str:
    """
    Run an Alexa routine by name.
    
    Args:
        routine_name: Name of the routine (e.g., "Good Morning", "Bedtime")
    
    Returns:
        Result message
    """
    service = await get_alexa_service()
    if not service:
        return "Alexa service not available. Check credentials and try again."
    
    result = await service.run_routine(routine_name=routine_name)
    
    if result["success"]:
        return result["message"]
    
    else:
        msg = f"Failed: {result['error']}"
        if "available_routines" in result:
            msg += f"\n\nAvailable routines: {', '.join(result['available_routines'])}"
        return msg

@tool 
async def send_alexa_announcement(message: str, device_name: Optional[str] = None) -> str:
    """
    Send a voice announcement to Echo devices.
    
    Args:
        message: The message to announce
        device_name: Specific Echo device name, or leave empty for all devices
    
    Returns:
        Result message
    """
    
    service = await get_alexa_service()
    if not service:
        return "Alexa service not available. Check credentials and try again."
    
    result = await service.send_announcements(message, device_name=device_name)
    
    if result["success"]:
        return result["message"]
    else:
        return f"Failed: {result['error']}"

@tool 
async def send_tts(message: str, device_name: str) -> str:
    """
    Make an Echo device speak a message (text-to-speech).
    
    Args:
        message: The message to speak
        device_name: Name of the Echo device (e.g., "Living Room Echo", "Kitchen Echo")
    
    Returns:
        Result message
    """
    service = await get_alexa_service()
    if not service:
        return "Alexa service not available. Check credentials and try again"
    result = await service.send_tts(message, device_name)
    
    if result["success"]:
        return result["message"]
    else:
        msg = f"Failed: {result['error']}"
        if "available_devices" in result:
            msg += f"\n\nAvailable devices: {', '.join(result['available_devices'])}"
        return msg
    
@tool 
async def play_music(search_phrase: str, device_name: str, provider: str = "SPOTIFY") -> str:
    """
    Play music on an Echo device.
    
    Args:
        search_phrase: What to play (e.g., "jazz music", "Taylor Swift", "relaxing piano")
        device_name: Name of the Echo device
        provider: Music provider - AMAZON_MUSIC, SPOTIFY, APPLE_MUSIC (default: AMAZON_MUSIC)
    
    Returns:
        Result message
    """
    service = await get_alexa_service()
    if not service:
        return "Alexa service not available. Check credentials and try again"
    result = await service.play_music(search_phrase=search_phrase, device_name=device_name, provider=provider)
    
    if result["success"]:
        return result["message"]
    else:
        msg = f"Failed: {result['error']}"
        if "available_devices" in result:
            msg += f"\n\nAvailable devices: {', '.join(result['available_devices'])}"
        return msg