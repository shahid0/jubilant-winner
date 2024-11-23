import asyncio
import aiohttp
import time
import requests
import uuid
from loguru import logger
from colorama import Fore, Style, init
import sys
import logging
logging.disable(logging.ERROR)
from utils.banner import banner
from utils.config import DOMAIN_API

# Initialize colorama
init(autoreset=True)

# Customize loguru to use color for different log levels
logger.remove()
logger.add(sys.stdout, format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{message}</level>", colorize=True)
logger.level("INFO", color=f"{Fore.GREEN}")
logger.level("DEBUG", color=f"{Fore.CYAN}")
logger.level("WARNING", color=f"{Fore.YELLOW}")
logger.level("ERROR", color=f"{Fore.RED}")
logger.level("CRITICAL", color=f"{Style.BRIGHT}{Fore.RED}")

def show_copyright():
    print(Fore.MAGENTA + Style.BRIGHT + banner + Style.RESET_ALL)

PING_INTERVAL = 60
RETRIES = 120
TOKEN_FILE = 'np_tokens.txt'

PROXY_SOURCES = {
    'PROXYSCRAPE': 'https://api.proxyscrape.com/v4/free-proxy-list/get?request=display_proxies&proxy_format=protocolipport&format=text',
    'US PROXY': 'https://raw.githubusercontent.com/shahid0/super-duper-octo-winner/refs/heads/main/us_working_proxies.txt',
    'GITCHK 1': 'https://raw.githubusercontent.com/shahid0/super-duper-octo-winner/refs/heads/main/working_proxies.txt',
    'SERVER 1': 'https://files.ramanode.top/airdrop/grass/server_1.txt',
    'SERVER 2': 'https://files.ramanode.top/airdrop/grass/server_2.txt',
    'SERVER 3': 'https://raw.githubusercontent.com/Vauth/proxy/refs/heads/main/proxy.txt',
    'SERVER 4': 'https://proxyspace.pro/socks5.txt',
    'SERVER 5': 'https://raw.githubusercontent.com/MyZest/update-live-socks5/refs/heads/master/liveSocks5.txt',
    'SERVER 6': 'https://raw.githubusercontent.com/elliottophellia/proxylist/refs/heads/master/results/pmix_checked.txt',
    'SERVER 7': 'https://raw.githubusercontent.com/vakhov/fresh-proxy-list/refs/heads/master/socks5.txt'
}

CONNECTION_STATES = {
    "CONNECTED": 1,
    "DISCONNECTED": 2,
    "NONE_CONNECTION": 3
}

status_connect = CONNECTION_STATES["NONE_CONNECTION"]
browser_id = None
account_info = {}
last_ping_time = {}

def uuidv4():
    return str(uuid.uuid4())

def valid_resp(resp):
    if not resp or "code" not in resp or resp["code"] < 0:
        raise ValueError("Invalid response")
    return resp

proxy_auth_status = {}

async def render_profile_info(proxy, token):
    global browser_id, account_info

    try:
        np_session_info = load_session_info(proxy)
        
        if not proxy_auth_status.get(proxy):
            browser_id = uuidv4()
            response = await call_api(DOMAIN_API["SESSION"], {}, proxy, token)
            if response is None:
                return
            valid_resp(response)
            account_info = response["data"]
            
            if account_info.get("uid"):
                proxy_auth_status[proxy] = True
                save_session_info(proxy, account_info)
                logger.info(f"Authentication successful for proxy {proxy} account: {account_info}")
            else:
                handle_logout(proxy)
                return
        
        if proxy_auth_status[proxy]:
            await start_ping(proxy, token)

    except Exception as e:
        logger.error(f"Error in render_profile_info for proxy {proxy}: {e}")

async def call_api(url, data, proxy, token, max_retries=3):
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.212 Safari/537.36",
        "Accept": "application/json",
        "Accept-Language": "en-US,en;q=0.5",
        "Referer": "https://app.nodepay.ai",
    }

    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=True)) as session:
        for attempt in range(max_retries):
            try:
                async with session.post(url, json=data, headers=headers, proxy=proxy, timeout=10) as response:
                    response.raise_for_status()
                    resp_json = await response.json()
                    return valid_resp(resp_json)
            except aiohttp.ClientResponseError as e:
                if e.status == 403:                    
                    return None
            except aiohttp.ClientConnectionError:
                pass
            except Exception:
                pass
            await asyncio.sleep(2 ** attempt)

    return None

async def start_ping(proxy, token):
    try:
        while True:
            await ping(proxy, token)
            await asyncio.sleep(PING_INTERVAL)
    except asyncio.CancelledError:
        logger.info(f"{Fore.YELLOW}Ping task for proxy {proxy} was cancelled")
    except Exception as e:
        logger.error(f"{Fore.RED}Error in start_ping for proxy {proxy}: {e}")

async def ping(proxy, token):
    global last_ping_time, RETRIES, status_connect

    current_time = time.time()
    if proxy in last_ping_time and (current_time - last_ping_time[proxy]) < PING_INTERVAL:
        return

    last_ping_time[proxy] = current_time
    ping_urls = DOMAIN_API["PING"]

    for url in ping_urls:
        try:
            data = {
                "id": account_info.get("uid"),
                "browser_id": browser_id,
                "timestamp": int(time.time()),
                "version": '2.2.7'
            }
            logger.warning(f"Starting ping task for proxy {proxy} Data: {data}")
            response = await call_api(url, data, proxy, token)
            if response["code"] == 0:
                logger.info(f"{Fore.CYAN}Ping successful via proxy {proxy} - {response}")
                RETRIES = 0
                status_connect = CONNECTION_STATES["CONNECTED"]
                return 
            else:
                logger.error(f"{Fore.RED}Ping failed via proxy {proxy} - {response}")
                handle_ping_fail(proxy, response)
        except Exception as e:
            logger.error(f"{Fore.RED}Ping error via proxy {proxy}: {e}")

    handle_ping_fail(proxy, None)  

def handle_ping_fail(proxy, response):
    global RETRIES, status_connect

    RETRIES += 1
    if response and response.get("code") == 403:
        handle_logout(proxy)
    elif RETRIES < 2:
        status_connect = CONNECTION_STATES["DISCONNECTED"]
    else:
        status_connect = CONNECTION_STATES["DISCONNECTED"]

def handle_logout(proxy):
    global status_connect, account_info

    status_connect = CONNECTION_STATES["NONE_CONNECTION"]
    account_info = {}
    save_status(proxy, None)
    logger.info(f"{Fore.YELLOW}Logged out and cleared session info for proxy {proxy}")

async def fetch_proxies(session, url, source_name):
    try:
        async with session.get(url, timeout=10) as response:
            if response.status == 200:
                content = await response.text()
                proxies = content.strip().split('\n')
                logger.info(f"Successfully fetched {len(proxies)} proxies from {source_name}")
                return proxies
            else:
                logger.error(f"Failed to fetch proxies from {source_name}: Status {response.status}")
                return []
    except Exception as e:
        logger.error(f"Error fetching proxies from {source_name}: {e}")
        return []

async def load_proxies_from_sources():
    all_proxies = set()
    async with aiohttp.ClientSession() as session:
        tasks = []
        for source_name, url in PROXY_SOURCES.items():
            tasks.append(fetch_proxies(session, url, source_name))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for proxy_list in results:
            if isinstance(proxy_list, list):
                all_proxies.update(proxy_list)
    
    logger.info(f"Total unique proxies loaded: {len(all_proxies)}")
    return list(all_proxies)

def save_status(proxy, status):
    pass

def save_session_info(proxy, data):
    data_to_save = {
        "uid": data.get("uid"),
        "browser_id": browser_id
    }
    pass

def load_session_info(proxy):
    return {}

def load_tokens_from_file(filename):
    try:
        with open(filename, 'r') as file:
            tokens = file.read().splitlines()
        return tokens
    except Exception as e:
        logger.error(f"Failed to load tokens: {e}")
        raise SystemExit("Exiting due to failure in loading tokens")

async def main():
    show_copyright()
    print("Welcome to the main program!")
        
    tokens = load_tokens_from_file(TOKEN_FILE)

    all_proxies = await load_proxies_from_sources()
    while True:
                
        for token in tokens:
            tasks = {asyncio.create_task(render_profile_info(proxy, token)): proxy for proxy in all_proxies}

            done, pending = await asyncio.wait(tasks.keys(), return_when=asyncio.FIRST_COMPLETED)
            for task in done:
                tasks.pop(task)

            for proxy in set(all_proxies) - set(tasks.values()):
                new_task = asyncio.create_task(render_profile_info(proxy, token))
                tasks[new_task] = proxy

            await asyncio.sleep(3)
        await asyncio.sleep(10)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Program terminated by user.")