const axios = require('axios');
const { HttpsProxyAgent } = require('https-proxy-agent');
const { SocksProxyAgent } = require('socks-proxy-agent');
const { v4: uuidv4 } = require('uuid');
const fs = require('fs/promises');

const config = {
    PING_INTERVAL: 15000,
    MAX_CONCURRENT_TASKS: 100,
    REQUEST_TIMEOUT: 30000,
    API: {
        SESSION: 'https://api.nodepay.ai/api/auth/session',
        PING: ['https://nw.nodepay.org/api/network/ping']
    },
    HEADERS: {
        'Accept-Language': 'en-US,en;q=0.9',
        Referer: 'https://app.nodepay.ai/',
        Accept: 'application/json, text/plain, */*',
        'Content-Type': 'application/json',
        Origin: 'chrome-extension://lgmpfmgeabnnlemejacfljbmonaomfmm',
        'Sec-Ch-Ua': '"Chromium";v="130", "Google Chrome";v="130", "Not?A_Brand";v="99"',
        'Sec-Ch-Ua-Mobile': '?0',
        'Sec-Ch-Ua-Platform': '"Windows"',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36'
    }
};

let activeConnections = 0;

class Account {
    constructor(token, proxy, label) {
        this.token = token;
        this.proxy = proxy;
        this.label = label;
        this.browserId = uuidv4();
        this.accountInfo = {};
        this.lastPingTime = null;
        this.retries = 0;
        this.successfulPings = 0;
        this.active = true;
        this.axiosInstance = this._createAxiosInstance();
    }

    _createProxyAgent(proxy) {
        const isSocks = proxy.toLowerCase().startsWith('socks');
        const formattedProxy = isSocks
            ? proxy.replace(/^socks4?:\/\//, 'socks4://').replace(/^socks5?:\/\//, 'socks5://')
            : proxy.startsWith('http') ? proxy : `http://${proxy}`;
        return isSocks ? new SocksProxyAgent(formattedProxy) : new HttpsProxyAgent(formattedProxy);
    }

    _createAxiosInstance() {
        const agent = this.proxy ? this._createProxyAgent(this.proxy) : null;
        return axios.create({
            timeout: config.REQUEST_TIMEOUT,
            headers: config.HEADERS,
            httpsAgent: agent
        });
    }

    async makeRequest(url, data) {
        try {
            activeConnections++;
            const response = await this.axiosInstance.post(url, data, {
                headers: { Authorization: `Bearer ${this.token}` }
            });
            return response.data;
        } catch (err) {
            console.error(`[${this.label}] Request error: ${err.message}`);
            throw err;
        } finally {
            activeConnections--;
        }
    }

    truncateToken() {
        return `${this.token.slice(0, 5)}...${this.token.slice(-5)}`;
    }
}

async function performPing(account) {
    const currentTime = Date.now();
    if (account.lastPingTime && currentTime - account.lastPingTime < config.PING_INTERVAL) return;

    account.lastPingTime = currentTime;

    for (const url of config.API.PING) {
        try {
            const data = {
                id: account.accountInfo.uid,
                browser_id: account.browserId,
                timestamp: Math.floor(Date.now() / 1000),
                version: '2.2.7'
            };
            const response = await account.makeRequest(url, data);
            if (response.code === 0) {
                account.successfulPings++;
                console.log(`[${account.label}] Ping successful. Network Quality: ${response.data?.ip_score || 'N/A'}`);
                return;
            }
        } catch (err) {
            account.retries++;
            if (account.retries >= 3) {
                account.active = false;
                console.error(`[${account.label}] Deactivated due to repeated failures.`);
                return;
            }
        }
    }
}

async function processAccount(account) {
    try {
        console.log(`[${account.label}] Initializing.`);
        const response = await account.makeRequest(config.API.SESSION, {});
        if (response.code === 0) {
            account.accountInfo = response.data;
            while (account.active) {
                await performPing(account);
                await new Promise(resolve => setTimeout(resolve, config.PING_INTERVAL));
            }
        } else {
            console.error(`[${account.label}] Initialization failed.`);
        }
    } catch (err) {
        console.error(`[${account.label}] Error: ${err.message}`);
    }
}

function isValidProxy(proxy) {
    try {
        const urlPattern = /^(https?|socks4?|socks5):\/\/[^\s:]+(:\d+)?$/;
        return urlPattern.test(proxy);
    } catch {
        return false;
    }
}

async function loadTokens(filename) {
    try {
        const content = await fs.readFile(filename, 'utf8');
        return content
            .split('\n')
            .map(line => line.trim())
            .filter(line => line); // No validation for tokens
    } catch (err) {
        console.error(`Failed to read tokens from ${filename}: ${err.message}`);
        process.exit(1);
    }
}

async function loadProxies(filename) {
    try {
        const content = await fs.readFile(filename, 'utf8');
        const validProxies = content
            .split('\n')
            .map(line => line.trim())
            .filter(line => line && isValidProxy(line)); // Apply proxy validation
        const invalidProxies = content
            .split('\n')
            .map(line => line.trim())
            .filter(line => line && !isValidProxy(line));
        if (invalidProxies.length > 0) {
            console.warn(`Invalid proxies found:`, invalidProxies);
        }
        return validProxies;
    } catch (err) {
        console.error(`Failed to read proxies from ${filename}: ${err.message}`);
        process.exit(1);
    }
}


async function main() {
    const tokens = await loadTokens('np_tokens.txt');
    if (!tokens.length) {
        console.error('No tokens found in np_tokens.txt');
        return;
    }

    const proxies = await loadProxies('proxies.txt');
    if (!proxies.length) {
        console.error('No proxies found in proxies.txt');
        return;
    }

    console.log('Starting NodePay Network Bot');
    console.log(`Loaded ${tokens.length} tokens and ${proxies.length} proxies`);

    // Use Account class correctly
    const accounts = proxies.map((proxy, i) => 
        new Account(tokens[0], proxy, `Proxy-${i + 1}`) // Adjust token assignment as needed
    );

    await Promise.all(accounts.map(processAccount)); // Ensure processAccount is correctly used
}


process.on('SIGINT', () => {
    console.log('Terminating process.');
    process.exit(0);
});

main().catch(err => console.error('Main process error:', err));
