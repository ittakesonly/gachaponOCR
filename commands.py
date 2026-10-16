import os
import time
import json
import logging
import discord
from utils import (
    ADMIN_USER_ID,
    FARM_CHANNEL_ID,
    AZURE_USAGE_FILEPATH,
    AZURE_MAX_CALLS,
    AZURE_FARM_RESERVE,
    DAILY_SNIPE_LIMIT,
    DISCORD_INVITE,
    BRAND_FOOTER,
    state,
    get_priority_targets,
    save_priority_targets,
    generate_emoji_mapping,
)

logger = logging.getLogger("UserBot.Commands")

async def handle_dm_command(client: discord.Client, message: discord.Message, autotag_coro) -> bool:
    """
    Processes admin commands exclusively within Direct Messages.
    Returns True if a command was handled, False otherwise.
    """
    if not isinstance(message.channel, discord.DMChannel):
        return False

    if message.author.id != ADMIN_USER_ID:
        return False

    content = message.content.strip()
    content_lower = content.lower()

    if not content_lower.startswith("!"):
        return False

    # --- COMMAND: !help ---
    if content_lower == "!help":
        help_msg = (
            "⚡ **itonlytakes // Command Interface** ⚡\n\n"
            "**Core Operations:**\n"
            "• `!stats` — View Azure quota metrics & claim cooldowns\n"
            "• `!autotag` — Trigger priority series/character tagging in farm channel\n"
            "• `!give <index>` — Gift a card index from this account to your main\n\n"
            "**Priority Sniping:**\n"
            "• `!prio list` — List active snipe targets, weights, and assigned emojis\n"
            "• `!prio add <char|series> <name>` — Add a new target (Default Weight: 1)\n"
            "• `!prio weight <char|series> <weight> <name>` — Update target priority weight\n"
            "• `!prio remove <char|series> <name>` — Remove a target from snipe list\n\n"
            "**Community & Info:**\n"
            "• `!discord` — Get the official **itonlytakes** Discord invite\n"
            "• `!credits` — View project architecture and author credits"
            f"{BRAND_FOOTER}"
        )
        await message.channel.send(help_msg)
        return True

    # --- COMMAND: !credits ---
    if content_lower == "!credits":
        credits_msg = (
            "🛠️ **itonlytakes // Underground Automation** 🛠️\n\n"
            "• **Lead Developer & Architecture:** `itonlytakes`\n"
            "• **Vision Engine:** Azure Cognitive Services (Spatial Coordinate Parser)\n"
            "• **Decision Engine:** Scikit-Learn TF-IDF & Logistic Regression\n"
            "• **Source:** Distributed officially via **itonlytakes** GitHub"
            f"{BRAND_FOOTER}"
        )
        await message.channel.send(credits_msg)
        return True

    # --- COMMAND: !discord ---
    if content_lower == "!discord":
        discord_msg = (
            "🌐 **itonlytakes Community** 🌐\n\n"
            f"👉 {DISCORD_INVITE}"
            f"{BRAND_FOOTER}"
        )
        await message.channel.send(discord_msg)
        return True

    # --- COMMAND: !autotag ---
    if content_lower == "!autotag":
        await message.channel.send(
            "🏷️ **Autotag sequence initiated.**\n"
            f"Tagging all priority series and characters in <#{FARM_CHANNEL_ID}>."
            f"{BRAND_FOOTER}"
        )
        client.loop.create_task(autotag_coro())
        return True

    # --- COMMAND: !stats ---
    if content_lower == "!stats":
        total_farm = 0
        total_snipe = 0
        daily_snipe = 0
        current_month = time.strftime("%Y-%m")
        current_date = time.strftime("%Y-%m-%d")

        if os.path.exists(AZURE_USAGE_FILEPATH):
            try:
                with open(AZURE_USAGE_FILEPATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if data.get("month", current_month) == current_month:
                        total_farm = data.get("lifetime_farm", 0)
                        total_snipe = data.get("lifetime_snipe", 0)
                    if data.get("date") == current_date:
                        daily_snipe = data.get("daily_snipe", 0)
            except Exception as e:
                logger.error(f"Failed to read Azure usage for stats: {e}")

        total_calls = total_farm + total_snipe
        remaining_calls = max(0, AZURE_MAX_CALLS - total_calls)
        reserve_threshold = AZURE_MAX_CALLS - AZURE_FARM_RESERVE

        cd_left = state.claim_cooldown_expires - time.time()
        if cd_left > 0:
            mins, secs = divmod(int(cd_left), 60)
            cd_text = f"⏳ `{mins}m {secs}s`"
        else:
            cd_text = "✅ `Ready`"

        reserve_status = "`Active (Farm Only)`" if total_calls >= reserve_threshold else "`Healthy`"

        stats_msg = (
            "📊 **itonlytakes // Telemetry & Quota** 📊\n\n"
            "**Azure Quota:**\n"
            f"• Monthly Calls: `{total_calls:,} / {AZURE_MAX_CALLS:,}`\n"
            f"• Remaining Quota: `{remaining_calls:,}`\n"
            f"• Breakdown: `{total_farm:,}` Farm | `{total_snipe:,}` Snipe\n\n"
            "**Sniping Pacing:**\n"
            f"• Daily Snipes: `{daily_snipe} / {DAILY_SNIPE_LIMIT}`\n"
            f"• Reserve Status: {reserve_status}\n\n"
            "**Game Status:**\n"
            f"• Claim Cooldown: {cd_text}"
            f"{BRAND_FOOTER}"
        )
        await message.channel.send(stats_msg)
        return True

    # --- COMMAND: !give ---
    if content_lower.startswith("!give"):
        parts = content_lower.split()
        if len(parts) == 2 and parts[1].isdigit():
            card_index = parts[1]
            farm_channel = client.get_channel(FARM_CHANNEL_ID)
            if farm_channel:
                await farm_channel.send(f"ggift <@{ADMIN_USER_ID}> {card_index}")
                await message.channel.send(
                    f"🎁 Executed transfer for card index **{card_index}** to <@{ADMIN_USER_ID}> in <#{FARM_CHANNEL_ID}>."
                    f"{BRAND_FOOTER}"
                )
            else:
                await message.channel.send(f"❌ **Error:** Could not locate farming channel.{BRAND_FOOTER}")
        else:
            await message.channel.send(f"❌ **Invalid Syntax.** Usage: `!give <card-index>`{BRAND_FOOTER}")
        return True

    # --- COMMAND: !prio ---
    if content_lower.startswith("!prio"):
        parts = content_lower.split()
        targets = get_priority_targets()
        emoji_map = generate_emoji_mapping(targets)

        if len(parts) >= 2 and parts[1] == "list":
            lines = ["🎯 **itonlytakes // Priority Targets**\n", "**Characters:**"]
            char_items = [
                f"• `{k}` (Weight: `{v}`) [{emoji_map.get(k, '🏷️')}]"
                for k, v in targets.get("characters", {}).items()
            ]
            lines.extend(char_items if char_items else ["• *None*"])
            lines.extend(["\n**Series:**"])
            series_items = [
                f"• `{k}` (Weight: `{v}`) [{emoji_map.get(k, '🏷️')}]"
                for k, v in targets.get("series", {}).items()
            ]
            lines.extend(series_items if series_items else ["• *None*"])
            lines.append(BRAND_FOOTER)

            current_chunk = ""
            for line in lines:
                if len(current_chunk) + len(line) + 1 > 1900:
                    await message.channel.send(current_chunk)
                    current_chunk = ""
                current_chunk += line + "\n"
            if current_chunk.strip():
                await message.channel.send(current_chunk)
            return True

        if len(parts) >= 4 and parts[1] in ["add", "remove"] and parts[2] in ["char", "series"]:
            action = parts[1]
            category = "characters" if parts[2] == "char" else "series"
            item_name = content_lower.split(maxsplit=3)[3]

            if action == "add":
                if item_name not in targets[category]:
                    targets[category][item_name] = 1
                    save_priority_targets(targets)
                    new_map = generate_emoji_mapping(targets)
                    await message.channel.send(
                        f"✅ Added **{item_name}** to `{category}` (Weight: `1` | Tag: {new_map.get(item_name, '🏷️')})."
                        f"{BRAND_FOOTER}"
                    )
                else:
                    await message.channel.send(f"⚠️ **{item_name}** is already in `{category}`.{BRAND_FOOTER}")
            elif action == "remove":
                if item_name in targets[category]:
                    del targets[category][item_name]
                    save_priority_targets(targets)
                    await message.channel.send(f"🗑️ Removed **{item_name}** from `{category}`.{BRAND_FOOTER}")
                else:
                    await message.channel.send(f"⚠️ **{item_name}** not found in `{category}`.{BRAND_FOOTER}")
            return True

        if len(parts) >= 5 and parts[1] == "weight" and parts[2] in ["char", "series"]:
            category = "characters" if parts[2] == "char" else "series"
            try:
                weight = int(parts[3])
                item_name = content_lower.split(maxsplit=4)[4]
                if item_name in targets[category]:
                    targets[category][item_name] = weight
                    save_priority_targets(targets)
                    await message.channel.send(
                        f"⚖️ Updated **{item_name}** weight to `{weight}`."
                        f"{BRAND_FOOTER}"
                    )
                else:
                    await message.channel.send(
                        f"⚠️ **{item_name}** not found. Add it first with `!prio add {parts[2]} {item_name}`."
                        f"{BRAND_FOOTER}"
                    )
            except ValueError:
                await message.channel.send(f"❌ **Invalid weight.** Must be an integer.{BRAND_FOOTER}")
            return True

        await message.channel.send(f"❌ **Invalid `!prio` syntax.** Type `!help` for command usage.{BRAND_FOOTER}")
        return True

    # Unknown command fallback
    await message.channel.send(f"❓ Unknown command. Type `!help` to view available commands.{BRAND_FOOTER}")
    return True