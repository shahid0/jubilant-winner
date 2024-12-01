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

display_header()

def show_warning():
    confirm = ""

    if confirm.strip() == "":
        print("Continuing...")
    else:
        print("Exiting...")
        exit()

# Constants
PING_INTERVAL = 15  # Reduced ping interval for faster monitoring
RETRIES = 3  # Limit retries to avoid delays

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

async def render_profile_info(account_label, proxy, token):
    global browser_id, account_info

    try:
        np_session_info = load_session_info(proxy)

        if not np_session_info:
            # Generate new browser_id
            browser_id = uuidv4()
            response = await call_api(DOMAIN_API["SESSION"], {}, proxy, token)
            valid_resp(response)
            account_info = response["data"]
            if account_info.get("uid"):
                save_session_info(proxy, account_info)
                await start_ping(account_label, proxy, token)
            else:
                handle_logout(proxy)
        else:
            account_info = np_session_info
            await start_ping(account_label, proxy, token)
    except Exception as e:
        logger.error(f"[{account_label}] Error in render_profile_info for proxy {proxy}: {e}")
        return proxy

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
        response = scraper.post(url, json=data, headers=headers, proxies={
                                "http": proxy, "https": proxy}, timeout=15)
        response.raise_for_status()
        return valid_resp(response.json())
    except Exception as e:
        logger.error(f"Error during API call: {e}")
        raise ValueError(f"Failed API call to {url}")

async def start_ping(account_label, proxy, token):
    try:
        while True:
            await ping(account_label, proxy, token)
            await asyncio.sleep(PING_INTERVAL)
    except asyncio.CancelledError:
        logger.info(f"[{account_label}] Ping task for proxy {proxy} was cancelled")
    except Exception as e:
        logger.error(f"[{account_label}] Error in start_ping for proxy {proxy}: {e}")

async def ping(account_label, proxy, token):
    global last_ping_time, RETRIES, status_connect

    current_time = time.time()

    if proxy in last_ping_time and (current_time - last_ping_time[proxy]) < PING_INTERVAL:
        logger.info(f"[{account_label}] Skipping ping for proxy {proxy}, not enough time elapsed")
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
        if response["code"] == 0:
            logger.info(f"[{account_label}] Ping successful via proxy {proxy}: {response}")
            RETRIES = 0
            status_connect = CONNECTION_STATES["CONNECTED"]
        else:
            handle_ping_fail(proxy, response)
    except Exception as e:
        logger.error(f"[{account_label}] Ping failed via proxy {proxy}: {e}")
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

def is_valid_proxy(proxy):
    return True  

def remove_proxy_from_list(proxy):
    pass  

async def main():
    mode_choice = "2"
    if mode_choice == "1":
        token = input("Enter Nodepay token: ").strip()
        if not token:
            print("Token cannot be empty. Exiting the program.")
            exit()
        tokens = [token]
    elif mode_choice == "2":
        tokens = load_accounts("np_tokens.txt")
        if not tokens:
            print("No accounts found in data.txt. Exiting the program.")
            exit()
    else:
        print("Invalid choice. Exiting.")
        return

    proxy_choice = "2"

    if proxy_choice == "1":
        r = requests.get("https://api.proxyscrape.com/v4/free-proxy-list/get?request=display_proxies&proxy_format=protocolipport&format=text", stream=True)
        if r.status_code == 200:
            with open('auto_proxies.txt', 'wb') as f:
                for chunk in r:
                    f.write(chunk)
        all_proxies = load_proxies('auto_proxies.txt')
    elif proxy_choice == "2":
        all_proxies = load_proxies('proxies.txt')
    else:
        print("Invalid choice. Exiting.")
        return

    proxy_index = 0
    loop = asyncio.get_event_loop()

    with ThreadPoolExecutor(max_workers=5) as executor:
        while True:
            tasks = []
            for i, token in enumerate(tokens):
                proxy = all_proxies[proxy_index % len(all_proxies)]
                account_label = f"Account-{i+1}"
                logger.info(f"Starting {account_label} with proxy {proxy}")

                tasks.append(loop.run_in_executor(executor, asyncio.run, render_profile_info(account_label, proxy, token)))
                proxy_index += 1
            
            await asyncio.gather(*tasks)
            await asyncio.sleep(3)

if __name__ == '__main__':
    show_warning()
    print("\nInsert your Nodepay Token")
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Program terminated by user.")
