import pyotp
from SmartApi import SmartConnect
import logging

logger = logging.getLogger(__name__)


API_KEY = config('API_KEY')
USERNAME = config('USERNAME')
PASSWORD = config('PASSWORD')
TOKEN = config('TOKEN')



def get_smartapi_session():
    """Initialize SmartAPI session."""
    try:
        totp = pyotp.TOTP(TOKEN).now()
        obj = SmartConnect(API_KEY)
        data = obj.generateSession(USERNAME, PASSWORD, totp)
        return {
            "obj": obj,
            "authToken": data['data']['jwtToken'],
            "refreshToken": data['data']['refreshToken'],
            "feedToken": obj.getfeedToken()
        }
    except Exception as e:
        logger.error(f"Error in SmartAPI session: {e}")
        return None
