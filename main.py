import requests
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

def display_header():
    custom_ascii_art = f"""
{Fore.CYAN}
███╗   ██╗ ██████╗ ██████╗ ███████╗██████╗  █████╗ ██╗   ██╗  
████╗  ██║██╔═══██╗██╔══██╗██╔════╝██╔══██╗██╔══██╗╚██╗ ██╔╝  
██╔██╗ ██║██║   ██║██║  ██║█████╗  ██████╔╝███████║ ╚████╔╝   
██║╚██╗██║██║   ██║██║  ██║██╔══╝  ██╔═══╝ ██╔══██║  ╚██╔╝    
██║ ╚████║╚██████╔╝██████╔╝███████╗██║     ██║  ██║   ██║     
╚═╝  ╚═══╝ ╚═════╝ ╚═════╝ ╚══════╝╚═╝     ╚═╝  ╚═╝   ╚═╝     
                                                              
███╗   ██╗███████╗████████╗██╗    ██╗ ██████╗ ██████╗ ██╗  ██╗
████╗  ██║██╔════╝╚══██╔══╝██║    ██║██╔═══██╗██╔══██╗██║ ██╔╝
██╔██╗ ██║█████╗     ██║   ██║ █╗ ██║██║   ██║██████╔╝█████╔╝ 
██║╚██╗██║██╔══╝     ██║   ██║███╗██║██║   ██║██╔══██╗██╔═██╗ 
██║ ╚████║███████╗   ██║   ╚███╔███╔╝╚██████╔╝██║  ██║██║  ██╗
╚═╝  ╚═══╝╚══════╝   ╚═╝    ╚══╝╚══╝  ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝{Fore.RESET} 
"""
    print(custom_ascii_art)
    print(f"{Fore.YELLOW}NODEPAY NETWORK BOT{Fore.RESET}")
    print("WELCOME & ENJOY SIR!", Fore.RESET)
    print("AUTHOR : NOFAN RAMBE", Fore.RESET)

def show_warning():
    confirm = ""
    if confirm.strip() == "":
        print("Continuing...")
    else:
        print("Exiting...")
        exit()

# Constants
PING_INTERVAL = 15
RETRIES = 3

DOMAIN_API = {
    "SESSION": "https://api.nodepay.ai/api/auth/session",
    "PING": "http://52.77.10.116/api/network/ping"
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

def format_proxy(proxy):
    """Format proxy string into the correct format based on type"""
    if proxy.startswith('socks'):
        return proxy
    else:
        if not proxy.startswith('http'):
            return f'http://{proxy}'
        return proxy

def get_proxy_dict(proxy):
    """Convert proxy string to dictionary format for requests"""
    formatted_proxy = format_proxy(proxy)
    return {
        "http": formatted_proxy,
        "https": formatted_proxy
    }

def valid_resp(resp):
    if not resp or "code" not in resp or resp["code"] < 0:
        raise ValueError("Invalid response")
    return resp

def load_proxies(proxy_file):
    try:
        with open(proxy_file, 'r') as file:
            proxies = file.read().splitlines()
        return proxies
    except Exception as e:
        logger.error(f"Failed to load proxies: {e}")
        raise SystemExit("Exiting due to failure in loading proxies")

def load_accounts(file_name):
    accounts = []
    try:
        with open(file_name, 'r') as file:
            for line in file:
                token = line.strip()
                if token:
                    accounts.append(token)
    except Exception as e:
        logger.error(f"Failed to load accounts: {e}")
        raise SystemExit("Exiting due to failure in loading accounts")
    return accounts

async def call_api(url, data, proxy, token):
    user_agent = UserAgent(os=['windows', 'macos', 'linux'], browsers='chrome')
    random_user_agent = user_agent.random
    headers = {
        "Authorization": f"Bearer {token}",
        "User-Agent": random_user_agent,
        "Content-Type": "application/json",
        "Origin": "chrome-extension://lgmpfmgeabnnlemejacfljbmonaomfmm",
        "Accept": "application/json",
        "Accept-Language": "en-US,en;q=0.5",
    }

    try:
        scraper = cloudscraper.create_scraper()
        proxy_dict = get_proxy_dict(proxy)
        
        response = scraper.post(
            url, 
            json=data, 
            headers=headers, 
            proxies=proxy_dict,
            timeout=15
        )
        response.raise_for_status()
        return valid_resp(response.json())
    except Exception as e:
        logger.error(f"Error during API call: {e}")
        raise ValueError(f"Failed API call to {url}")

async def render_profile_info(proxy_label, proxy, token):
    global browser_id, account_info

    try:
        browser_id = uuidv4()
        response = await call_api(DOMAIN_API["SESSION"], {}, proxy, token)
        valid_resp(response)
        account_info = response["data"]
        
        if account_info.get("uid"):
            save_session_info(proxy, account_info)
            await start_ping(proxy_label, proxy, token)
        else:
            handle_logout(proxy)
            
    except Exception as e:
        logger.error(f"[{proxy_label}] Error in render_profile_info for proxy {proxy}: {e}")
        raise e

async def ping(proxy_label, proxy, token):
    global last_ping_time, RETRIES, status_connect

    current_time = time.time()
    if proxy in last_ping_time and (current_time - last_ping_time[proxy]) < PING_INTERVAL:
        logger.info(f"[{proxy_label}] Skipping ping for proxy {proxy}, not enough time elapsed")
        return

    last_ping_time[proxy] = current_time

    try:
        data = {
            "id": account_info.get("uid"),
            "browser_id": browser_id,
            "timestamp": int(time.time()),
            "version": "2.2.7"
        }

        response = await call_api(DOMAIN_API["PING"], data, proxy, token)
        proxy_type = "SOCKS" if proxy.startswith('socks') else "HTTP"
        if response["code"] == 0:
            logger.info(f"[{proxy_label}] Ping successful via {proxy_type} proxy {proxy}: {response}")
            RETRIES = 0
            status_connect = CONNECTION_STATES["CONNECTED"]
        else:
            handle_ping_fail(proxy, response)
    except Exception as e:
        logger.error(f"[{proxy_label}] Ping failed via proxy {proxy}: {e}")
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
    logger.info(f"Logged out and cleared session info for proxy {proxy}")

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

async def start_ping(proxy_label, proxy, token):
    try:
        while True:
            await ping(proxy_label, proxy, token)
            await asyncio.sleep(PING_INTERVAL)
    except asyncio.CancelledError:
        logger.info(f"[{proxy_label}] Ping task for proxy {proxy} was cancelled")
    except Exception as e:
        logger.error(f"[{proxy_label}] Error in start_ping for proxy {proxy}: {e}")

async def handle_single_proxy(proxy_label, proxy, token):
    try:
        proxy_type = "SOCKS" if proxy.startswith('socks') else "HTTP"
        logger.info(f"[{proxy_label}] Attempting connection with {proxy_type} proxy: {proxy}")
        await render_profile_info(proxy_label, proxy, token)
        logger.success(f"[{proxy_label}] Successfully connected using {proxy_type} proxy {proxy}")
    except Exception as e:
        logger.error(f"[{proxy_label}] Failed to connect using proxy {proxy}: {e}")

async def main():
    # Load the single token from file
    tokens = load_accounts("np_tokens.txt")
    if not tokens:
        print("No token found in np_tokens.txt. Exiting the program.")
        exit()
    token = tokens[0]  # Use the first (and only) token
    
    # Load proxies
    all_proxies = load_proxies('proxies.txt')
    if not all_proxies:
        print("No proxies found in proxies.txt. Exiting the program.")
        exit()

    # Create tasks for each proxy using the same token
    tasks = []
    for i, proxy in enumerate(all_proxies):
        proxy_label = f"Proxy-{i+1}"
        task = handle_single_proxy(proxy_label, proxy, token)
        tasks.append(task)
    
    # Run all proxy tasks concurrently
    try:
        await asyncio.gather(*tasks)
    except Exception as e:
        logger.error(f"Error in main process: {e}")
        
    # Keep the program running
    while True:
        await asyncio.sleep(60)

if __name__ == '__main__':
    display_header()
    show_warning()
    print("\nUsing token from np_tokens.txt")
    print("Make sure to install required packages:")
    print("pip install requests asyncio aiohttp cloudscraper pyfiglet colorama loguru fake-useragent requests[socks] PySocks")
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Program terminated by user.")
