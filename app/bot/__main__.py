"""Entry point for running the bot with python -m bot command."""

import sys
import asyncio
from pathlib import Path

# Add parent directory to path for proper imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Import the main function from the root bot.py
from bot import main

if __name__ == "__main__":
    asyncio.run(main()) 