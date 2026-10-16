# itonlytakes // Gachapon OCR Sniper & Predictive Farmer

- **IF YOU NEED HELP OR UPDATES JOIN:** https://discord.gg/JajaAWcfB9
- **Star if this got you good drops <3**
- **Every 5 stars is 1 update** ⭐

A fast, autonomous Discord bot engineered for farming and sniping Gachapon cards. Built on spatial OCR coordinate mapping (Azure Computer Vision) and a local Machine Learning preference engine (TF-IDF + Logistic Regression) that learns what franchises you claim and auto-picks for you when AFK.

> ⚠️ **DISCLAIMER:** **Run this on an alt account** and use the built-in `!give` command to transfer cards to your main. `itonlytakes` is not responsible for terminated accounts.

---

## Requirements

- **Python 3.11+** (or **Docker** for containerized deployment)
- **Discord Alt Account Token**
- **Azure Computer Vision Resource** (100% Free using the `F0` tier)

---

## Setup

### 1. Native Setup (Standard)
1. Clone the repository and install dependencies:
   ```bash
   git clone [https://github.com/itonlytakes/gachabot.git](https://github.com/itonlytakes/gachabot.git)
   cd gachabot
   pip install -r requirements.txt
   ```
2. Copy `.env.example` and rename it to `.env`:
   ```bash
   cp .env.example .env
   ```
3. Fill in your `.env` values (see the configuration guide below).
4. Start the engine:
   ```bash
   python main.py
   ```

### 2. Docker Setup (Optional Bonus)
If you want to run the bot 24/7 in the background via Docker, Portainer, or Dokploy:
1. Configure your `.env` file in the root directory.
2. Build and detach the container:
   ```bash
   docker-compose up -d --build
   ```

---

## Configuration (`.env` Guide)

Open your `.env` file in any text editor and fill out the fields. Do not wrap your values in quotes or spaces.

```ini
# --- DISCORD CONFIGURATION ---
USER_TOKEN=your_alt_account_token_here
ADMIN_USER_ID=your_main_discord_id_here
FARM_CHANNEL_ID=123456789012345678
SNIPE_CHANNELS=channel_id_1,channel_id_2

# --- AZURE FREE TIER (F0) CONFIGURATION ---
AZURE_VISION_ENDPOINT=[https://your-resource.cognitiveservices.azure.com/](https://your-resource.cognitiveservices.azure.com/)
AZURE_VISION_KEY=your_azure_vision_key_here
AZURE_MAX_CALLS=5000
AZURE_FARM_RESERVE=500
DAILY_SNIPE_LIMIT=125
```

### Environment Variables Breakdown

| Variable | Required | Default | Description |
| :--- | :---: | :---: | :--- |
| `USER_TOKEN` | **Yes** | — | The Discord token of the **alt account** running the bot. |
| `ADMIN_USER_ID` | **Yes** | — | Your **main account's** Discord User ID. The bot will only accept DM commands from this ID, send drop alerts/prompts to this ID, and gift cards to this ID. |
| `FARM_CHANNEL_ID` | **Yes** | — | The Channel ID where the bot will actively run `gcd`, `gdaily`, `ggacha`, and `gautotag`. |
| `SNIPE_CHANNELS` | No | — | Comma-separated list of Channel IDs to passively monitor and snipe drops from other users. |
| `AZURE_VISION_ENDPOINT` | **Yes** | — | Your Azure Computer Vision endpoint URL (e.g., `https://name.cognitiveservices.azure.com/`). |
| `AZURE_VISION_KEY` | **Yes** | — | Your `KEY 1` from the Azure Computer Vision Keys & Endpoint tab. |
| `AZURE_MAX_CALLS` | No | `5000` | Hard monthly OCR cutoff to ensure you never exceed the Azure Free Tier (`F0`) limit. |
| `AZURE_FARM_RESERVE` | No | `500` | Reserves the final 500 calls of the month strictly for your own `ggacha` drops, pausing passive sniping when total calls hit `4500`. |
| `DAILY_SNIPE_LIMIT` | No | `125` | Maximum passive snipe OCR calls per day so your free quota paces evenly across the entire month. |

---

## How to Get Azure Computer Vision (100% Free)

You do **not** need a paid plan or student credit to run this bot 24/7. Azure's permanent **Free Tier (`F0`)** gives you **5,000 free OCR calls every month**.

1. Go to [portal.azure.com](https://portal.azure.com/) and sign in (create a free Azure account if you don't have one).
2. In the top search bar, search for **"Computer Vision"** (under Azure AI services) and click **Create**.
3. Fill in the resource details:
   - **Subscription:** Your Azure subscription.
   - **Resource Group:** Click *Create new* and name it anything (e.g., `gacha-rg`).
   - **Region:** Pick the region closest to you (e.g., `East US`).
   - **Name:** Give it a unique name.
   - **Pricing Tier:** Select **Free F0 (20 Calls per minute, 5K Calls per month)**.
4. Check the responsible AI notice box, click **Review + create**, and then click **Create**.
5. Once deployment finishes, click **Go to resource**.
6. In the left sidebar under *Resource Management*, click **Keys and Endpoint**.
7. Copy **KEY 1** into `AZURE_VISION_KEY` and **Endpoint** into `AZURE_VISION_ENDPOINT` inside your `.env` file.

### Why 5,000 Free Calls is More Than Enough (The Math)
Gachapon enforces a **20-minute drop cooldown** (`ggacha`) and a **10-minute claim cooldown**:
- **24/7 Active Farming:** With a 20-minute spawn cooldown, the maximum number of drops a single account can trigger is $3 \text{ drops/hour} \times 24 \text{ hours} = 72 \text{ calls/day}$. Over a 30-day month, non-stop 24/7 farming only uses **2,160 calls/month**—less than half of the 5,000 free quota.
- **Cooldown-Aware Snipe Blocking:** Whenever the bot claims a card, it locks out passive sniping for the duration of the **10-minute claim cooldown**. You never waste Azure OCR calls scanning drops in `SNIPE_CHANNELS` while your claim is on cooldown.
- **Built-in Smart Pacing:** That leaves **2,840 free calls every month** purely for passive sniping. With `DAILY_SNIPE_LIMIT=125` and `AZURE_FARM_RESERVE=500`, the bot paces your snipes automatically and guarantees you never run out of calls or get billed (well, on the Free Tier you can't even get billed!).

---

## Commands (DM Only)

For stealth, **the bot ignores all commands typed in public server channels**. Send these commands via **Direct Message (DM)** to the alt account from your `ADMIN_USER_ID` account:

- `!help` — Display the full command menu.
- `!stats` — View monthly Azure quota usage, daily snipe pacing, and current claim cooldown timer.
- `!autotag` — Manually trigger the `gautotag` sequence in your farm channel using deterministic safe emojis from `assets/emojis.json`.
- `!give <index>` — Execute `ggift` in the farm channel to transfer a card index to your main account.
- `!prio list` — List all priority characters and series, their weights, and their assigned tags.
- `!prio add <char|series> <name>` — Add a character or series to the instant-snipe override list.
- `!prio weight <char|series> <weight> <name>` — Set custom priority weight (higher weight wins if two priority targets drop together).
- `!prio remove <char|series> <name>` — Remove a character or series from the priority list.
- `!discord` — Get the official **itonlytakes** Discord link.
- `!credits` — View project architecture and credits.

---
*⚡ powered by **itonlytakes***