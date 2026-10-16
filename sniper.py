import time
import random
import asyncio
import logging
import discord

from preference_engine import PreferenceEngine
from ocr_parser import extract_cards_from_image
from utils import (
    ADMIN_USER_ID,
    SNIPE_CHANNELS,
    BRAND_FOOTER,
    state,
    get_priority_targets,
    download_image,
)

logger = logging.getLogger("UserBot.Sniper")
ml_engine = PreferenceEngine()

async def trigger_claim(drop_msg: discord.Message, choice: int, instant: bool = False) -> bool:
    """Finds the target card button on the drop message and clicks it."""
    if instant:
        logger.info(f"[bold green]Priority target![/] Firing instant claim on Card {choice}...")
        await asyncio.sleep(random.uniform(0.05, 0.15))
    else:
        logger.info(f"Claiming Card {choice} with humanized reaction delay...")
        await asyncio.sleep(random.uniform(1.5, 2.5))
    
    if drop_msg and drop_msg.components:
        all_buttons = [
            component
            for action_row in drop_msg.components
            for component in action_row.children
        ]
        
        if len(all_buttons) >= choice:
            target_button = all_buttons[choice - 1]
            try:
                await target_button.click()
                logger.debug(f"Clicked Button {choice} via Discord API.")
                return True
            except Exception as e:
                logger.error(f"Discord API rejected Button {choice} click: {e}")
        else:
            logger.error(f"Could not find Button {choice} in the message payload.")

    logger.error(f"Failed to click Button {choice}.")
    return False

async def process_drop(
    client: discord.Client,
    channel: discord.TextChannel,
    drop_msg: discord.Message,
    is_snipe: bool = False
):
    """Evaluates a Gachapon drop via OCR, checks priority weights, and claims or prompts via DM."""
    image_url = None
    if drop_msg.attachments:
        image_url = drop_msg.attachments[0].url
    elif drop_msg.embeds and drop_msg.embeds[0].image:
        image_url = drop_msg.embeds[0].image.url

    if not image_url:
        return

    img_bytes = await download_image(image_url)
    if not img_bytes:
        return

    num_cards = 3 if "3 cards" in drop_msg.content.lower() else 2
    cards = extract_cards_from_image(img_bytes, num_cards, is_snipe)

    if not cards:
        return

    # --- 1. DYNAMIC PRIORITY OVERRIDE (WEIGHT BASED) ---
    targets = get_priority_targets()
    override_card = None
    highest_weight = -1

    for card in cards:
        card_char = card["character"].lower()
        card_series = card["series"].lower()
        card_score = -1

        for target_char, weight in targets.get("characters", {}).items():
            if target_char.lower() in card_char:
                card_score = weight
                break

        if card_score == -1:
            for target_series, weight in targets.get("series", {}).items():
                if target_series.lower() in card_series:
                    card_score = weight
                    break

        if card_score > highest_weight:
            highest_weight = card_score
            override_card = card

    if override_card:
        override_choice = override_card["slot"]
        char_name = override_card["character"]
        series_name = override_card["series"]
        
        logger.info(
            f"[bold green]🚨 PRIORITY TARGET DETECTED:[/] Slot {override_choice} "
            f"([bold]{char_name}[/] - {series_name}) [Weight: {highest_weight}]"
        )
        
        claim_success = await trigger_claim(drop_msg, override_choice, instant=True)
        
        if ADMIN_USER_ID:
            try:
                target_user = await client.fetch_user(ADMIN_USER_ID)
                if claim_success:
                    try:
                        def is_claim_confirmation(m):
                            return (
                                m.channel.id == channel.id 
                                and m.author.id == drop_msg.author.id 
                                and "claimed" in m.content.lower()
                            )
                        
                        confirm_msg = await client.wait_for("message", timeout=6.0, check=is_claim_confirmation)
                        
                        if (
                            str(client.user.id) in confirm_msg.content
                            or client.user in confirm_msg.mentions
                            or client.user.name.lower() in confirm_msg.content.lower()
                        ):
                            await target_user.send(
                                f"✅ **SUCCESSFUL SNIPE** ✅\n"
                                f"Claimed **{char_name}** ({series_name}) in <#{channel.id}>!"
                                f"{BRAND_FOOTER}"
                            )
                            state.claim_cooldown_expires = time.time() + 600
                            logger.info("[bold green]Snipe confirmed![/] Engaging 10m cooldown lock.")
                        else:
                            await target_user.send(
                                f"❌ **OUT-SNIPED** ❌\n"
                                f"Attempted to snipe **{char_name}**, but another user claimed it first in <#{channel.id}>."
                                f"{BRAND_FOOTER}"
                            )
                    except asyncio.TimeoutError:
                        await target_user.send(
                            f"⏳ **SNIPE FAILED / COOLDOWN** ⏳\n"
                            f"Clicked **{char_name}** in <#{channel.id}>, but received no confirmation."
                            f"{BRAND_FOOTER}"
                        )
                else:
                    await target_user.send(
                        f"❌ **CLICK FAILED** ❌\n"
                        f"Target detected (**{char_name}**), but button interaction failed in <#{channel.id}>."
                        f"{BRAND_FOOTER}"
                    )
            except Exception as e:
                logger.debug(f"Could not send snipe notification DM: {e}")
        return

    # --- 2. PASSIVE SNIPE FILTER ---
    if is_snipe:
        logger.debug(f"Ignored drop in snipe channel {channel.id} (no priority match).")
        return

    # --- 3. MAIN FARMING CHANNEL ML LOGIC ---
    rec_slot, scores = ml_engine.rank_cards(cards)
    target_user = None

    if ADMIN_USER_ID:
        try:
            target_user = await client.fetch_user(ADMIN_USER_ID)
            prompt_lines = [f"🎴 **Gachapon Drop Detected in <#{channel.id}>!**\n"]
            for i, card in enumerate(cards):
                prompt_lines.append(
                    f"• **Card {card['slot']}**: {card['character']} ({card['series']}) — Confidence: `{scores[i] * 100:.1f}%`"
                )
            prompt_lines.append(f"\n🧠 **AI Recommendation**: Card **{rec_slot}**")
            prompt_lines.append(f"Reply with `1` to `{num_cards}` within 25 seconds to override.{BRAND_FOOTER}")
            
            await target_user.send("\n".join(prompt_lines))
        except Exception as e:
            logger.error(f"Failed to send DM to admin user: {e}")
            target_user = None

    def is_decision(m):
        valid_choices = {str(i) for i in range(1, num_cards + 1)}
        return (
            m.author.id == ADMIN_USER_ID
            and isinstance(m.channel, discord.DMChannel)
            and m.content.strip() in valid_choices
        )

    is_human_choice = False
    try:
        decision_msg = await client.wait_for("message", timeout=25.0, check=is_decision)
        chosen_choice = int(decision_msg.content.strip())
        is_human_choice = True
        logger.info(f"Human override received: Selected Card {chosen_choice}")
    except asyncio.TimeoutError:
        chosen_choice = rec_slot
        logger.info(f"Decision timeout. Defaulting to AI recommendation: Card {chosen_choice}")
        if target_user:
            try:
                await target_user.send(f"⏱️ Timeout expired. Auto-selected Card **{chosen_choice}**.")
            except Exception:
                pass

    claim_success = await trigger_claim(drop_msg, chosen_choice)
    if claim_success:
        state.claim_cooldown_expires = time.time() + 600

    if is_human_choice:
        chosen_card = cards[chosen_choice - 1]
        rejected_cards = [c for c in cards if c["slot"] != chosen_choice]
        ml_engine.record_interaction(chosen_card, rejected_cards)
        
        if target_user:
            try:
                await target_user.send(f"✅ Claimed Card **{chosen_choice}**. ML preference weights updated.")
            except Exception:
                pass

def check_and_dispatch_snipe(client: discord.Client, message: discord.Message):
    """Checks incoming messages in monitored channels and dispatches passive snipe tasks."""
    if message.channel.id not in SNIPE_CHANNELS or message.author.id == client.user.id:
        return

    if time.time() < state.claim_cooldown_expires:
        return
        
    content_lower = message.content.lower()
    if (message.attachments or message.embeds) and (
        "is dropping 2 cards" in content_lower or "is dropping 3 cards" in content_lower
    ):
        logger.info(f"[bold magenta]Passive Snipe:[/] Drop detected in channel {message.channel.id}!")
        client.loop.create_task(process_drop(client, message.channel, message, is_snipe=True))