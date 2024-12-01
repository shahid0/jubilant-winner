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

# [Previous display functions and constants remain the same...]

async def handle_single_proxy(proxy_label, proxy, token):
    """Handle connection and ping for a single proxy"""
    try:
        await render_profile_info(proxy_label, proxy, token)
        logger.success(f"[{proxy_label}] Successfully connected using proxy {proxy}")
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
    proxy_choice = "2"  # Default to file mode
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
    show_warning()
    print("\nUsing token from np_tokens.txt")
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Program terminated by user.")
