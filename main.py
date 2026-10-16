import re
import time
import random
import asyncio
import discord

from console import setup_logging, print_boot_banner
from commands import handle_dm_command
from sniper import process_drop, check_and_dispatch_snipe
from utils import (
    USER_TOKEN,
    FARM_CHANNEL_ID,
    state,
    get_priority_targets,
    generate_emoji_mapping,
    extract_seconds,
)

logger = setup_logging()
client = discord.Client()

async def execute_autotag_cycle():
    """Iterates through all priorities, runs gautotag, and clicks confirmation."""
    channel = client.get_channel(FARM_CHANNEL_ID)
    if not channel:
        return
        
    targets = get_priority_targets()
    emoji_map = generate_emoji_mapping(targets)
    logger.info("Executing priority autotag sequence...")

    async def attempt_tag(command_str, item_name):
        await channel.send(command_str)
        
        def is_confirm_embed(m):
            return (
                m.channel.id == FARM_CHANNEL_ID 
                and m.author.id != client.user.id 
                and m.embeds 
                and m.embeds[0].title == "Confirm Tagging"
            )

        try:
            confirm_msg = await client.wait_for("message", timeout=5.0, check=is_confirm_embed)
            if confirm_msg.components:
                all_buttons = [comp for row in confirm_msg.components for comp in row.children]
                yes_button = next((b for b in all_buttons if getattr(b, "label", "") == "Yes"), None)
                
                await asyncio.sleep(random.uniform(0.5, 1.2))
                if yes_button:
                    await yes_button.click()
                    logger.debug(f"Confirmed autotag for {item_name}.")
                elif all_buttons:
                    await all_buttons[0].click()
        except asyncio.TimeoutError:
            logger.debug(f"No confirmation embed for {item_name} (0 cards matched).")

    for series_name in targets.get("series", {}).keys():
        emoji = emoji_map.get(series_name, "🏷️")
        await attempt_tag(f"gautotag {emoji} {series_name}", series_name)
        await asyncio.sleep(random.uniform(3.0, 5.0))

    for char_name in targets.get("characters", {}).keys():
        emoji = emoji_map.get(char_name, "🏷️")
        await attempt_tag(f"gautotag {emoji} {char_name} --c", char_name)
        await asyncio.sleep(random.uniform(3.0, 5.0))
        
    logger.info("[bold green]Autotag sequence complete.[/]")

async def background_autotag_loop():
    await client.wait_until_ready()
    await asyncio.sleep(60)
    while not client.is_closed():
        await execute_autotag_cycle()
        await asyncio.sleep(43200 + random.uniform(-900, 900))

async def main_farming_loop():
    await client.wait_until_ready()
    channel = client.get_channel(FARM_CHANNEL_ID)
    
    if not channel:
        logger.error(f"Could not locate FARM_CHANNEL_ID ({FARM_CHANNEL_ID}). Farming loop aborted.")
        return

    logger.info("Predictive Gachapon farming loop online.")

    while not client.is_closed():
        await channel.send("gcd")
        logger.debug("Sent gcd command to check status.")
        
        def is_gcd_response(m):
            if m.channel.id != FARM_CHANNEL_ID or m.author.id == client.user.id:
                return False
            text_to_check = m.content.lower()
            for embed in m.embeds:
                if embed.title:
                    text_to_check += f" {embed.title.lower()}"
                if embed.description:
                    text_to_check += f" {embed.description.lower()}"
            return "cooldown" in text_to_check
            
        try:
            gcd_msg = await client.wait_for("message", timeout=15.0, check=is_gcd_response)
            
            full_text = gcd_msg.content.lower()
            for embed in gcd_msg.embeds:
                if embed.title:
                    full_text += f" {embed.title.lower()}"
                if embed.description:
                    full_text += f" {embed.description.lower()}"
                for field in embed.fields:
                    full_text += f" {field.name.lower()} {field.value.lower()}"
            
            clean_text = full_text.replace("*", "").replace("`", "").replace("_", "")
            
            if "claim your daily coins now" in clean_text:
                logger.info("Daily coins ready. Executing [bold]gdaily[/]...")
                await channel.send("gdaily")
                await asyncio.sleep(random.uniform(2.5, 4.5))
            
            claim_sleep = 0
            if "claim a card again now" not in clean_text:
                claim_match = re.search(r"((?:\d+\s*[hms]\s*)+)left to claim a card again", clean_text)
                if claim_match:
                    claim_sleep = extract_seconds(claim_match.group(1))
                    state.claim_cooldown_expires = time.time() + claim_sleep
            else:
                state.claim_cooldown_expires = 0.0

            spawn_sleep = 0
            if "spawn a card again now" not in clean_text:
                spawn_match = re.search(r"((?:\d+\s*[hms]\s*)+)left to spawn", clean_text)
                if spawn_match:
                    spawn_sleep = extract_seconds(spawn_match.group(1))
                else:
                    logger.warning("Could not parse spawn cooldown. Defaulting to 5m wait.")
                    spawn_sleep = 5 * 60

            if spawn_sleep == 0 and claim_sleep == 0:
                logger.info("[bold green]Spawn & Claim ready![/] Executing [bold]ggacha[/].")
                await channel.send("ggacha")
                
                def is_gacha_drop(m):
                    return (
                        m.channel.id == FARM_CHANNEL_ID 
                        and m.author.id != client.user.id 
                        and (m.attachments or m.embeds)
                    )
                
                try:
                    drop_msg = await client.wait_for("message", timeout=25.0, check=is_gacha_drop)
                    logger.info("Drop banner detected. Sending to sniper pipeline...")
                    await process_drop(client, channel, drop_msg, is_snipe=False)
                    sleep_time = 20 * 60
                except asyncio.TimeoutError:
                    logger.warning("Sent ggacha but no drop image appeared. Sleeping 20m.")
                    sleep_time = 20 * 60
            else:
                sleep_time = max(spawn_sleep, claim_sleep)
                if claim_sleep > spawn_sleep:
                    logger.info(f"[yellow]Snipe Protection:[/] Spawn ready, but Claim on cooldown ({claim_sleep}s). Holding drop.")
                else:
                    hours, rem = divmod(spawn_sleep, 3600)
                    mins, secs = divmod(rem, 60)
                    logger.info(f"Spawn on cooldown. Sleeping for [bold]{hours}h {mins}m {secs}s[/].")

        except asyncio.TimeoutError:
            logger.warning("Timeout waiting for gcd response. Retrying in 2 minutes.")
            sleep_time = 2 * 60

        jitter = random.uniform(15, 90)
        total_sleep = sleep_time + jitter
        logger.info(f"Cycle complete. Hibernating for [cyan]{total_sleep / 60:.2f} minutes[/].")
        await asyncio.sleep(total_sleep)

@client.event
async def on_message(message: discord.Message):
    # 1. Route Admin DM Commands
    if await handle_dm_command(client, message, execute_autotag_cycle):
        return

    # 2. Dispatch Passive Sniping
    check_and_dispatch_snipe(client, message)

@client.event
async def on_ready():
    logger.info(f"Authenticated as [bold green]{client.user.name}[/] ({client.user.id})")
    client.loop.create_task(main_farming_loop())
    client.loop.create_task(background_autotag_loop())

if __name__ == "__main__":
    print_boot_banner()
    if not USER_TOKEN:
        logger.critical("USER_TOKEN is missing from your .env configuration.")
        raise SystemExit(1)
    
    logger.info("Booting itonlytakes bot engine...")
    try:
        client.run(USER_TOKEN)
    except Exception as e:
        logger.critical(f"Fatal execution error: {e}")