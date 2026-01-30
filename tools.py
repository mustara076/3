# tools.py
import datetime

def get_current_time(timezone: str = "UTC") -> str:
    """Diye gaye timezone ke liye current time aur date batata hai."""
    try:
        # Abhi ke liye simple UTC time return kar raha hai
        # Kyunki external libraries (pytz) avoid karni hain taaki error na aaye
        tz = datetime.timezone.utc
        now_utc = datetime.datetime.now(tz)
        return f"Current time is {now_utc.strftime('%H:%M:%S')} on {now_utc.strftime('%Y-%m-%d')} (UTC)."
    except Exception as e:
        return f"Error getting time: {e}"