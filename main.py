import asyncio
import aiohttp
import time
import uuid
import cloudscraper
import pyfiglet
from colorama import Fore
from loguru import logger
from fake_useragent import UserAgent
from concurrent.futures import ThreadPoolExecutor

# [Previous display_header function and constants remain the same]
def display_header():
    
    print(f"{Fore.YELLOW}NODEPAY NETWORK BOT{Fore.RESET}")
    print("WELCOME & ENJOY SIR!", Fore.RESET)
    print("AUTHOR : NOFAN RAMBE", Fore.RESET)

PING_INTERVAL = 15
RETRIES = 10

DOMAIN_API = {
    "SESSION": "https://api.nodepay.ai/api/auth/session",
    "PING": [
        "https://nw.nodepay.org/api/network/ping"
    ]
}

class AccountData:
    def __init__(self, token, proxy, proxy_label):
        self.token = token
        self.proxy = proxy
        self.proxy_label = proxy_label
        self.browser_id = {
            'ping_count': 0,
            'successful_pings': 0,
            'score': 0,
            'start_time': time.time(),
            'last_ping_time': None
        }
        self.account_info = {}
        self.last_ping_time = None
        self.retries = 0
        self.successful_pings = 0
        self.ping_count = 0

def format_proxy(proxy):
    if proxy.startswith('socks'):
        return proxy
    return f'http://{proxy}' if not proxy.startswith('http') else proxy

def get_proxy_dict(proxy):
    formatted_proxy = format_proxy(proxy)
    return {
        "http": formatted_proxy,
        "https": formatted_proxy
    }

def truncate_token(token):
    return f"{token[:5]}...{token[-5:]}"

async def execute_request(url, data, account):
    headers = {
        "Authorization": f"Bearer {account.token}",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://app.nodepay.ai/",
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json",
        "Origin": "chrome-extension://lgmpfmgeabnnlemejacfljbmonaomfmm",
        "Sec-Ch-Ua": '"Chromium";v="130", "Google Chrome";v="130", "Not?A_Brand";v="99"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"Windows"',
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "cors-site"
    }

    proxy_config = get_proxy_dict(account.proxy) if account.proxy else None
    
    try:
        scraper = cloudscraper.create_scraper(
            browser={
                'browser': 'chrome',
                'platform': 'windows',
                'desktop': True
            }
        )
        response = scraper.post(url, json=data, headers=headers, proxies=proxy_config, timeout=60)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"{Fore.RED}Error during API call for token {truncate_token(account.token)} with proxy {account.proxy}: {e}{Fore.RESET}")
        raise ValueError(f"Failed API call to {url}")

async def perform_ping(account):
    current_time = time.time()
    if account.last_ping_time and (current_time - account.last_ping_time) < PING_INTERVAL:
        return

    account.last_ping_time = current_time
    logger.info(f"{Fore.CYAN}[{time.strftime('%H:%M:%S')}][{account.proxy_label}]{Fore.RESET} Attempting ping from {Fore.CYAN}{truncate_token(account.token)}{Fore.RESET} with {Fore.YELLOW}{account.proxy if account.proxy else 'no proxy'}{Fore.RESET}")

    for url in DOMAIN_API["PING"]:
        try:
            data = {
                "id": account.account_info.get("uid"),
                "browser_id": account.browser_id,
                "timestamp": int(time.time())
            }
            
            response = await execute_request(url, data, account)
            
            if response["code"] == 0:
                account.successful_pings += 1
                account.browser_id['successful_pings'] += 1
                account.browser_id['ping_count'] += 1
                network_quality = response.get("data", {}).get("ip_score", "N/A")
                logger.info(f"{Fore.CYAN}[{time.strftime('%H:%M:%S')}][{account.proxy_label}]{Fore.RESET} Ping {Fore.GREEN}success{Fore.RESET} from {Fore.CYAN}{truncate_token(account.token)}{Fore.RESET}, Network Quality: {Fore.GREEN}{network_quality}{Fore.RESET}")
                account.retries = 0
                return
            else:
                logger.warning(f"{Fore.RED}Ping failed{Fore.RESET} for token {truncate_token(account.token)} using proxy {account.proxy}")
                account.retries += 1

        except Exception as e:
            logger.error(f"{Fore.RED}Ping failed for token {truncate_token(account.token)} using URL {url}: {e}{Fore.RESET}")
            account.retries += 1

async def start_ping(account):
    try:
        while True:
            await perform_ping(account)
            await asyncio.sleep(PING_INTERVAL)
    except asyncio.CancelledError:
        logger.info(f"Ping task cancelled for token {truncate_token(account.token)}")
    except Exception as e:
        logger.error(f"Error in start_ping for token {truncate_token(account.token)}: {e}")

async def initialize_account(account):
    try:
        logger.info(f"{Fore.CYAN}[{account.proxy_label}]{Fore.RESET} Initializing account with proxy: {account.proxy}")
        
        # First get the session info
        response = await execute_request(DOMAIN_API["SESSION"], {}, account)
        
        if response.get("code") == 0:
            account.account_info = response["data"]
            if account.account_info.get("uid"):
                logger.info(f"{Fore.GREEN}Successfully initialized session for {truncate_token(account.token)}{Fore.RESET}")
                await start_ping(account)
            else:
                logger.error(f"No UID found for token {truncate_token(account.token)}")
        else:
            logger.error(f"Session initialization failed for token {truncate_token(account.token)}")
            
    except Exception as e:
        logger.error(f"Failed to initialize account for token {truncate_token(account.token)}: {e}")

def load_data(filename):
    try:
        with open(filename, 'r') as file:
            return [line.strip() for line in file if line.strip()]
    except Exception as e:
        logger.error(f"Failed to load data from {filename}: {e}")
        raise SystemExit(f"Failed to load {filename}")

async def main():
    tokens = load_data("np_tokens.txt")
    if not tokens:
        logger.error("No tokens found in np_tokens.txt")
        return

    token = tokens[0]  # Use first token
    proxies = load_data("proxies.txt")
    if not proxies:
        logger.error("No proxies found in proxies.txt")
        return

    tasks = []
    for i, proxy in enumerate(proxies):
        account = AccountData(token, proxy, f"Proxy-{i+1}")
        tasks.append(initialize_account(account))

    try:
        await asyncio.gather(*tasks)
    except Exception as e:
        logger.error(f"Error in main process: {e}")

    while True:
        await asyncio.sleep(60)

if __name__ == '__main__':
    # display_header()
    print("\nUsing token from np_tokens.txt")
    print("Required packages: requests asyncio aiohttp cloudscraper pyfiglet colorama loguru fake-useragent requests[socks] PySocks")
    
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Program terminated by user.")
        tasks = asyncio.all_tasks()
        for task in tasks:
            task.cancel()
        asyncio.get_event_loop().run_until_complete(asyncio.gather(*tasks, return_exceptions=True))
        asyncio.get_event_loop().close()
