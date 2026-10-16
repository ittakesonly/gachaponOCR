import os
import io
import time
import json
import logging
import requests
from PIL import Image
from utils import (
    AZURE_ENDPOINT,
    AZURE_KEY,
    AZURE_MAX_CALLS,
    AZURE_FARM_RESERVE,
    DAILY_SNIPE_LIMIT,
    AZURE_USAGE_FILEPATH,
)

logger = logging.getLogger("UserBot.OCR")

ANALYZE_URL = f"{AZURE_ENDPOINT}/computervision/imageanalysis:analyze?api-version=2024-02-01&features=read"

class AzureUsageTracker:
    def __init__(self, filepath=AZURE_USAGE_FILEPATH):
        self.filepath = filepath
        self.load_data()
        
    def load_data(self):
        self.current_date = time.strftime("%Y-%m-%d")
        self.current_month = time.strftime("%Y-%m")
        
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    
                    # Reset monthly counters if a new billing month started
                    if data.get("month", self.current_month) == self.current_month:
                        self.lifetime_farm = data.get("lifetime_farm", 0)
                        self.lifetime_snipe = data.get("lifetime_snipe", 0)
                    else:
                        self.lifetime_farm = 0
                        self.lifetime_snipe = 0
                    
                    if data.get("date") == self.current_date:
                        self.daily_snipe = data.get("daily_snipe", 0)
                    else:
                        self.daily_snipe = 0
            except Exception:
                self._set_defaults()
        else:
            self._set_defaults()

    def _set_defaults(self):
        self.lifetime_farm = 0
        self.lifetime_snipe = 0
        self.daily_snipe = 0
            
    def save_data(self):
        os.makedirs(os.path.dirname(self.filepath), exist_ok=True)
        try:
            with open(self.filepath, "w", encoding="utf-8") as f:
                json.dump({
                    "month": self.current_month,
                    "date": self.current_date,
                    "lifetime_farm": self.lifetime_farm,
                    "lifetime_snipe": self.lifetime_snipe,
                    "daily_snipe": self.daily_snipe
                }, f, indent=4)
        except Exception as e:
            logger.error(f"Could not save tracker data: {e}")
            
    def should_allow(self, is_snipe: bool) -> bool:
        self._check_rollover()
        total_calls = self.lifetime_farm + self.lifetime_snipe
        reserve_cutoff = max(0, AZURE_MAX_CALLS - AZURE_FARM_RESERVE)
        
        # 1. Hard Monthly Cap (Prevent F0 Exhaustion / Billing)
        if total_calls >= AZURE_MAX_CALLS:
            logger.error(f"[bold red]Quota Limit:[/] Monthly cap reached ({total_calls}/{AZURE_MAX_CALLS}). OCR halted.")
            return False
            
        # 2. Farming Reserve (Save final calls exclusively for active ggacha)
        if is_snipe and total_calls >= reserve_cutoff:
            logger.warning(f"[yellow]Quota Reserve:[/] Approaching monthly cap ({total_calls}/{AZURE_MAX_CALLS}). Snipes paused.")
            return False
            
        # 3. Daily Snipe Pacing
        if is_snipe and self.daily_snipe >= DAILY_SNIPE_LIMIT:
            logger.warning(f"[yellow]Daily Cap:[/] Snipe limit hit ({self.daily_snipe}/{DAILY_SNIPE_LIMIT}). Pausing snipes until tomorrow.")
            return False
            
        return True

    def _check_rollover(self):
        new_date = time.strftime("%Y-%m-%d")
        new_month = time.strftime("%Y-%m")
        changed = False

        if new_month != self.current_month:
            self.current_month = new_month
            self.lifetime_farm = 0
            self.lifetime_snipe = 0
            changed = True

        if new_date != self.current_date:
            self.current_date = new_date
            self.daily_snipe = 0
            changed = True

        if changed:
            self.save_data()
        
    def record_call(self, is_snipe: bool):
        self._check_rollover()
        if is_snipe:
            self.lifetime_snipe += 1
            self.daily_snipe += 1
        else:
            self.lifetime_farm += 1
            
        self.save_data()

usage_tracker = AzureUsageTracker()

def extract_cards_from_image(image_bytes: bytes, num_cards: int = 2, is_snipe: bool = False) -> list[dict]:
    """Sends the raw banner to Azure Vision and uses spatial coordinates to map text to cards."""
    if not AZURE_ENDPOINT or not AZURE_KEY:
        logger.error("Missing Azure credentials in .env file.")
        return []

    if not usage_tracker.should_allow(is_snipe):
        return []

    logger.debug("Transmitting raw image buffer to Azure Cloud Vision API...")
    
    headers = {
        "Ocp-Apim-Subscription-Key": AZURE_KEY,
        "Content-Type": "application/octet-stream"
    }
    
    try:
        start_time = time.time()
        response = requests.post(ANALYZE_URL, headers=headers, data=image_bytes, timeout=5)
        response.raise_for_status()
        
        usage_tracker.record_call(is_snipe)
        
        data = response.json()
        logger.debug(f"Azure OCR returned in {time.time() - start_time:.2f}s.")
    except Exception as e:
        logger.error(f"Azure API request failed: {e}")
        return [{"slot": i, "character": "API Error", "series": "API Error"} for i in range(1, num_cards + 1)]

    total_width = data.get("metadata", {}).get("width")
    total_height = data.get("metadata", {}).get("height")
    
    if not total_width or not total_height:
        try:
            img = Image.open(io.BytesIO(image_bytes))
            total_width, total_height = img.size
        except Exception:
            total_width, total_height = 1000, 1000
            
    card_width = total_width / num_cards
    slot_texts = {i: [] for i in range(1, num_cards + 1)}
    
    read_data = data.get("readResult", {})
    blocks = read_data.get("blocks", [])
    
    for block in blocks:
        for line in block.get("lines", []):
            text = line.get("text", "").strip()
            polygon = line.get("boundingPolygon", [])
            
            if not text or len(polygon) != 4:
                continue
                
            avg_x = sum(pt.get("x", 0) for pt in polygon) / 4
            avg_y = sum(pt.get("y", 0) for pt in polygon) / 4
            
            if avg_y < (total_height * 0.55) or avg_y > (total_height * 0.98):
                continue
            
            slot = int(avg_x // card_width) + 1
            if 1 <= slot <= num_cards:
                slot_texts[slot].append({"text": text, "y": avg_y})

    cards = []
    for idx in range(1, num_cards + 1):
        lines = sorted(slot_texts[idx], key=lambda item: item["y"])
        valid_lines = [item["text"] for item in lines if len(item["text"]) > 1]
        
        if not valid_lines:
            character = "Unknown Character"
            series = "Unknown Franchise"
            logger.warning(f"Azure returned empty text for slot {idx}.")
        else:
            character = valid_lines[0]
            series = " ".join(valid_lines[1:]) if len(valid_lines) >= 2 else "Unknown Franchise"
            logger.debug(f"OCR Slot {idx}: {character} | {series}")
            
        cards.append({
            "slot": idx,
            "character": character,
            "series": series
        })

    return cards