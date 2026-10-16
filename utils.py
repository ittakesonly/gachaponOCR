import os
import re
import json
import hashlib
import logging
import aiohttp
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("UserBot.Utils")

# --- Hardcoded Branding (Non-Adjustable) ---
DISCORD_INVITE = "https://discord.gg/JajaAWcfB9"
BRAND_FOOTER = "\n\n*⚡ powered by **itonlytakes***"

# --- Environment Variables ---
USER_TOKEN = os.getenv("USER_TOKEN", "")
FARM_CHANNEL_ID = int(os.getenv("FARM_CHANNEL_ID", 0))
ADMIN_USER_ID = int(os.getenv("ADMIN_USER_ID", 0))

snipe_env = os.getenv("SNIPE_CHANNELS", "")
SNIPE_CHANNELS = {int(x.strip()) for x in snipe_env.split(",") if x.strip().isdigit()}

AZURE_ENDPOINT = os.getenv("AZURE_VISION_ENDPOINT", "").rstrip("/")
AZURE_KEY = os.getenv("AZURE_VISION_KEY", "")
AZURE_MAX_CALLS = int(os.getenv("AZURE_MAX_CALLS", 5000))
AZURE_FARM_RESERVE = int(os.getenv("AZURE_FARM_RESERVE", 500))
DAILY_SNIPE_LIMIT = int(os.getenv("DAILY_SNIPE_LIMIT", 125))

PRIORITY_FILEPATH = "data/priority_targets.json"
AZURE_USAGE_FILEPATH = "data/azure_usage.json"
EMOJIS_FILEPATH = "assets/emojis.json"

# --- Shared Runtime State ---
class BotState:
    claim_cooldown_expires: float = 0.0

state = BotState()

def load_safe_emojis(filepath=EMOJIS_FILEPATH) -> list[str]:
    """Loads the static emoji pool from emojis.json."""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            emojis = json.load(f)
            if isinstance(emojis, list) and emojis:
                return emojis
    except Exception as e:
        logger.warning(f"Could not load {filepath} ({e}). Using fallback emoji list.")
    return ["🍎", "🍋", "🍉", "🍇", "🍓", "🍒", "🍑", "🍍", "🥥", "🥝", "🔮", "💎", "⚡", "🎯"]

SAFE_EMOJIS = load_safe_emojis()

def generate_emoji_mapping(targets: dict) -> dict:
    """Generates a strictly unique emoji for every item, resolving hash collisions."""
    mapping = {}
    used_emojis = set()
    
    all_items = list(set(
        list(targets.get("characters", {}).keys()) + 
        list(targets.get("series", {}).keys())
    ))
    all_items.sort(key=lambda x: x.lower())
    
    for item in all_items:
        base_idx = int(hashlib.md5(item.lower().strip().encode()).hexdigest(), 16) % len(SAFE_EMOJIS)
        emoji = SAFE_EMOJIS[base_idx]
        
        offset = 0
        while emoji in used_emojis and offset < len(SAFE_EMOJIS):
            offset += 1
            emoji = SAFE_EMOJIS[(base_idx + offset) % len(SAFE_EMOJIS)]
            
        mapping[item] = emoji
        used_emojis.add(emoji)
        
    return mapping

def get_priority_targets(filepath=PRIORITY_FILEPATH) -> dict:
    if not os.path.exists(filepath):
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        default_data = {"series": {}, "characters": {}}
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(default_data, f, indent=4)
        return default_data
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        migrated = False
        for cat in ["characters", "series"]:
            if cat in data and isinstance(data[cat], list):
                data[cat] = {item: 1 for item in data[cat]}
                migrated = True
                
        if migrated:
            save_priority_targets(data, filepath)
            
        return data
    except Exception as e:
        logger.error(f"Failed to load priority targets: {e}")
        return {"series": {}, "characters": {}}

def save_priority_targets(targets: dict, filepath=PRIORITY_FILEPATH) -> bool:
    try:
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(targets, f, indent=4)
        logger.debug("Saved updated priority targets to disk.")
        return True
    except Exception as e:
        logger.error(f"Failed to save priority targets: {e}")
        return False

async def download_image(url: str) -> bytes:
    logger.debug(f"Downloading image from {url}")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10) as resp:
                if resp.status == 200:
                    return await resp.read()
                logger.error(f"Failed to download image, HTTP {resp.status}")
    except Exception as e:
        logger.error(f"Exception during image download: {e}")
    return b""

def extract_seconds(time_str: str) -> int:
    h = re.search(r"(\d+)h", time_str)
    m = re.search(r"(\d+)m", time_str)
    s = re.search(r"(\d+)s", time_str)
    hours = int(h.group(1)) if h else 0
    mins = int(m.group(1)) if m else 0
    secs = int(s.group(1)) if s else 0
    return (hours * 3600) + (mins * 60) + secs