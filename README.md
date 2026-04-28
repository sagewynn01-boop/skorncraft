# Skorncraft
Welcome to Skörn Craft
A profession bot intended to maximize crafting experiences for guildies
Have fun and happy crafting

## Setup
1. Clone this repository.
2. Install dependencies: `pip install -r requirements.txt`
3. Create a `.env` file with your bot token and channel IDs (see `.env.example` if available).
4. Run the bot: `python skorncraft_main.py`

## Deployment on Railway
1. Sign up for a Railway account at [railway.app](https://railway.app).
2. Connect your GitHub repository to Railway.
3. In the Railway dashboard:
   - Set the start command to: `python skorncraft_main.py`
   - Add environment variables:
     - `DISCORD_TOKEN`: Your bot's token
     - `BLACKSMITH_CHANNEL`: Channel ID for blacksmith requests
     - `TAILOR_CHANNEL`: Channel ID for tailor requests
     - `ALCHEMIST_CHANNEL`: Channel ID for alchemist requests
     - `ENCHANTER_CHANNEL`: Channel ID for enchanter requests
     - `LEATHERWORKER_CHANNEL`: Channel ID for leatherworker requests
     - `ENGINEER_CHANNEL`: Channel ID for engineer requests
     - `JEWELCRAFTER_CHANNEL`: Channel ID for jewelcrafter requests
     - `INSCRIPTIONIST_CHANNEL`: Channel ID for inscriptionist requests
4. Deploy! Railway will automatically install dependencies from `requirements.txt`.

## Features
- Interactive crafting request system via slash commands and DMs.
- Automatic cleanup of old messages (30+ days).
- Role-based claiming and completion tracking.