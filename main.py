import asyncio
import aiohttp
import time
import uuid
import json
from pathlib import Path
from typing import Dict, List, Optional
from loguru import logger
from colorama import Fore, Style, init
import sys
import logging
from dataclasses import dataclass, asdict
import random

# Disable unwanted logging
logging.disable(logging.ERROR)

# Initialize colorama
init(autoreset=True)

# Constants
PING_INTERVAL = 60
MAX_RETRIES = 3
CONCURRENT_LIMIT = 200
VERSION = '2.2.7'

# File paths
TOKEN_FILE = 'np_tokens.txt'
SESSION_FILE = 'sessions.json'
CONFIG_DIR = Path('config')
CONFIG_DIR.mkdir(exist_ok=True)

# API Configuration
DOMAIN_API = {
    "SESSION": "http://api.nodepay.ai/api/auth/session",
    "PING": [
        "http://13.215.134.222/api/network/ping",
        "http://18.139.20.49/api/network/ping",
        "http://18.142.29.174/api/network/ping",
        "http://18.142.214.13/api/network/ping",
        "http://52.74.31.107/api/network/ping",
        "http://52.74.35.173/api/network/ping",
        "http://52.77.10.116/api/network/ping",
        "http://3.1.154.253/api/network/ping"
    ]
}

PROXY_SOURCES = {
    'PROXYSCRAPE': 'https://api.proxyscrape.com/v4/free-proxy-list/get?request=display_proxies&proxy_format=protocolipport&format=text',
    'US PROXY': 'https://raw.githubusercontent.com/shahid0/super-duper-octo-winner/refs/heads/main/us_working_proxies.txt',
    'GITCHK 1': 'https://raw.githubusercontent.com/shahid0/super-duper-octo-winner/refs/heads/main/working_proxies.txt',
    'SERVER 1': 'https://files.ramanode.top/airdrop/grass/server_1.txt',
    'SERVER 2': 'https://files.ramanode.top/airdrop/grass/server_2.txt'
}

@dataclass
class SessionInfo:
    uid: str
    browser_id: str
    token: str
    proxy: str
    last_ping: float = 0.0
    
    def to_dict(self):
        return asdict(self)

class NodePayClient:
    def __init__(self):
        self.sessions: Dict[str, SessionInfo] = {}
        self.active_tasks = set()
        self.load_sessions()
        
        # Configure logger
        logger.remove()
        logger.add(
            sys.stdout,
            format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{message}</level>",
            colorize=True,
            level="INFO"
        )
        logger.level("INFO", color=f"{Fore.GREEN}")
        logger.level("ERROR", color=f"{Fore.RED}")
        logger.level("WARNING", color=f"{Fore.YELLOW}")

    def load_sessions(self):
        """Load saved sessions from file"""
        try:
            if Path(SESSION_FILE).exists():
                with open(SESSION_FILE, 'r') as f:
                    data = json.load(f)
                    self.sessions = {
                        k: SessionInfo(**v) for k, v in data.items()
                    }
                logger.info(f"Loaded {len(self.sessions)} saved sessions")
        except Exception as e:
            logger.error(f"Error loading sessions: {e}")

    def save_sessions(self):
        """Save current sessions to file"""
        try:
            with open(SESSION_FILE, 'w') as f:
                json.dump({k: v.to_dict() for k, v in self.sessions.items()}, f)
            logger.info("Sessions saved successfully")
        except Exception as e:
            logger.error(f"Error saving sessions: {e}")

    async def call_api(self, url: str, data: dict, session_info: SessionInfo) -> Optional[dict]:
        """Make API call with retry logic"""
        headers = {
            "Authorization": f"Bearer {session_info.token}",
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            "Accept": "application/json",
            "Accept-Language": "en-US,en;q=0.5",
            "Referer": "https://app.nodepay.ai",
        }

        for attempt in range(MAX_RETRIES):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        url,
                        json=data,
                        headers=headers,
                        proxy=session_info.proxy,
                        timeout=30
                    ) as response:
                        if response.status == 403:
                            return None
                        response.raise_for_status()
                        result = await response.json()
                        if result.get("code", -1) >= 0:
                            return result
            except Exception as e:
                if attempt == MAX_RETRIES - 1:
                    logger.error(f"API call failed after {MAX_RETRIES} attempts: {e}")
                await asyncio.sleep(2 ** attempt)
        return None

    async def authenticate(self, proxy: str, token: str) -> Optional[SessionInfo]:
        """Authenticate and create session"""
        try:
            browser_id = str(uuid.uuid4())
            response = await self.call_api(
                DOMAIN_API["SESSION"],
                {},
                SessionInfo(uid="", browser_id=browser_id, token=token, proxy=proxy)
            )
            
            if response and response.get("data", {}).get("uid"):
                uid = response["data"]["uid"]
                session_info = SessionInfo(
                    uid=uid,
                    browser_id=browser_id,
                    token=token,
                    proxy=proxy
                )
                self.sessions[proxy] = session_info
                self.save_sessions()
                logger.info(f"Authentication successful for proxy {proxy}")
                return session_info
        except Exception as e:
            logger.error(f"Authentication failed for proxy {proxy}: {e}")
        return None

    async def ping(self, session_info: SessionInfo):
        """Send ping request"""
        current_time = time.time()
        if current_time - session_info.last_ping < PING_INTERVAL:
            return True

        data = {
            "id": session_info.uid,
            "browser_id": session_info.browser_id,
            "timestamp": int(current_time),
            "version": VERSION
        }

        # Try each ping endpoint randomly
        ping_urls = random.sample(DOMAIN_API["PING"], len(DOMAIN_API["PING"]))
        for url in ping_urls:
            response = await self.call_api(url, data, session_info)
            if response and response.get("code") == 0:
                session_info.last_ping = current_time
                logger.info(f"Ping successful via proxy {session_info.proxy}")
                return True
            elif response and response.get("code") == 403:
                return False
        
        logger.warning(f"All ping attempts failed for proxy {session_info.proxy}")
        return False

    async def handle_session(self, proxy: str, token: str):
        """Main session handler"""
        try:
            session_info = self.sessions.get(proxy)
            if not session_info:
                session_info = await self.authenticate(proxy, token)
                if not session_info:
                    return

            while True:
                if not await self.ping(session_info):
                    logger.warning(f"Session invalid for proxy {proxy}, re-authenticating...")
                    self.sessions.pop(proxy, None)
                    return

                await asyncio.sleep(PING_INTERVAL)

        except Exception as e:
            logger.error(f"Session handler error for proxy {proxy}: {e}")
        finally:
            self.save_sessions()

    async def fetch_proxies(self) -> List[str]:
        """Fetch proxies from multiple sources"""
        all_proxies = set()
        async with aiohttp.ClientSession() as session:
            for source_name, url in PROXY_SOURCES.items():
                try:
                    async with session.get(url, timeout=10) as response:
                        if response.status == 200:
                            content = await response.text()
                            proxies = content.strip().split('\n')
                            all_proxies.update(proxies)
                            logger.info(f"Fetched {len(proxies)} proxies from {source_name}")
                except Exception as e:
                    logger.error(f"Failed to fetch proxies from {source_name}: {e}")

        return list(all_proxies)

    def load_tokens(self) -> List[str]:
        """Load tokens from file"""
        try:
            with open(TOKEN_FILE, 'r') as f:
                return [line.strip() for line in f if line.strip()]
        except Exception as e:
            logger.error(f"Failed to load tokens: {e}")
            return []

    async def run(self):
        """Main run loop"""
        logger.info("Starting NodePay client...")
        
        proxies = await self.fetch_proxies()
        
        while True:
            try:
                tokens = self.load_tokens()
                if not tokens:
                    logger.error("No tokens found. Please add tokens to token.txt")
                    return

                # proxies = await self.fetch_proxies()
                if not proxies:
                    logger.error("No proxies available. Retrying in 60 seconds...")
                    await asyncio.sleep(60)
                    continue

                logger.info(f"Running with {len(tokens)} tokens and {len(proxies)} proxies")

                tasks = set()
                for token in tokens:
                    for proxy in proxies:
                        if len(tasks) >= CONCURRENT_LIMIT:
                            done, tasks = await asyncio.wait(
                                tasks, 
                                return_when=asyncio.FIRST_COMPLETED
                            )
                        
                        task = asyncio.create_task(
                            self.handle_session(proxy, token)
                        )
                        tasks.add(task)

                await asyncio.gather(*tasks)
                await asyncio.sleep(10)

            except Exception as e:
                logger.error(f"Error in main loop: {e}")
                await asyncio.sleep(10)

async def main():
    client = NodePayClient()
    try:
        await client.run()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        client.save_sessions()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nProgram terminated by user.")
