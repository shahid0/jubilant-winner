const axios = require('axios');
const { HttpsProxyAgent } = require('https-proxy-agent');
const { SocksProxyAgent } = require('socks-proxy-agent');
const chalk = require('chalk');
const { v4: uuidv4 } = require('uuid');
const fs = require('fs/promises');
const figlet = require('figlet');
const UserAgent = require('user-agents');

const PING_INTERVAL = 15000; // in milliseconds
const MAX_CONCURRENT_TASKS = 100;
let activeConnections = 0;

const DOMAIN_API = {
    SESSION: 'https://api.nodepay.ai/api/auth/session',
    PING: ['https://nw.nodepay.org/api/network/ping']
};

class AccountData {
    constructor(token, proxy, proxyLabel) {
        this.token = token;
        this.proxy = proxy;
        this.proxyLabel = proxyLabel;
        this.browserId = uuidv4();
        this.accountInfo = {};
        this.lastPingTime = null;
        this.retries = 0;
        this.successfulPings = 0;
        this.pingCount = 0;
        this.active = true;
        this.axiosInstance = this.createAxiosInstance();
    }

    createProxyAgent(proxyUrl) {
        // Parse proxy URL to determine type
        const isSocks = proxyUrl.toLowerCase().startsWith('socks');
        
        if (isSocks) {
            // Ensure proper SOCKS URL format
            const formattedUrl = proxyUrl.replace(/^socks:\/\//, 'socks://').replace(/^socks4:\/\//, 'socks4://').replace(/^socks5:\/\//, 'socks5://');
            return new SocksProxyAgent(formattedUrl);
        } else {
            // Format HTTP proxy URL
            const formattedUrl = proxyUrl.startsWith('http') ? proxyUrl : `http://${proxyUrl}`;
            return new HttpsProxyAgent(formattedUrl);
        }
    }

    createAxiosInstance() {
        const config = {
            timeout: 30000,
            headers: {
                'Accept-Language': 'en-US,en;q=0.9',
                'Referer': 'https://app.nodepay.ai/',
                'Accept': 'application/json, text/plain, */*',
                'Content-Type': 'application/json',
                'Origin': 'chrome-extension://lgmpfmgeabnnlemejacfljbmonaomfmm',
                'Sec-Ch-Ua': '"Chromium";v="130", "Google Chrome";v="130", "Not?A_Brand";v="99"',
                'Sec-Ch-Ua-Mobile': '?0',
                'Sec-Ch-Ua-Platform': '"Windows"'
            }
        };

        if (this.proxy) {
            try {
                config.httpsAgent = this.createProxyAgent(this.proxy);
                // Log proxy type for debugging
                const proxyType = this.proxy.toLowerCase().startsWith('socks') ? 'SOCKS' : 'HTTP';
                console.log(chalk.cyan(`[${this.proxyLabel}] Using ${proxyType} proxy: ${this.proxy}`));
            } catch (error) {
                console.error(chalk.red(`Failed to create proxy agent for ${this.proxy}: ${error.message}`));
                throw error;
            }
        }

        return axios.create(config);
    }

    truncateToken() {
        return `${this.token.slice(0, 5)}...${this.token.slice(-5)}`;
    }
}

async function executeRequest(url, data, account) {
    if (activeConnections >= MAX_CONCURRENT_TASKS) {
        await new Promise(resolve => setTimeout(resolve, 1000));
    }
    
    activeConnections++;
    try {
        const userAgent = new UserAgent({ deviceCategory: 'desktop' });
        const response = await account.axiosInstance({
            method: 'POST',
            url,
            data,
            headers: {
                'Authorization': `Bearer ${account.token}`,
                'User-Agent': userAgent.toString()
            }
        });
        return response.data;
    } catch (error) {
        const proxyType = account.proxy.toLowerCase().startsWith('socks') ? 'SOCKS' : 'HTTP';
        console.error(chalk.red(`Error during API call for token ${account.truncateToken()} with ${proxyType} proxy ${account.proxy}: ${error.message}`));
        throw new Error(`Failed API call to ${url}`);
    } finally {
        activeConnections--;
    }
}

async function performPing(account) {
    if (!account.active) return;

    const currentTime = Date.now();
    if (account.lastPingTime && (currentTime - account.lastPingTime) < PING_INTERVAL) return;

    account.lastPingTime = currentTime;
    console.log(chalk.cyan(`[${new Date().toLocaleTimeString()}][${account.proxyLabel}]`), 
        `Attempting ping from ${chalk.cyan(account.truncateToken())}`);

    for (const url of DOMAIN_API.PING) {
        try {
            const data = {
                id: account.accountInfo.uid,
                browser_id: account.browserId,
                timestamp: Math.floor(Date.now() / 1000),
                version: '2.2.7'
            };

            const response = await executeRequest(url, data, account);

            if (response.code === 0) {
                account.successfulPings++;
                const networkQuality = response.data?.ip_score ?? 'N/A';
                console.log(
                    chalk.cyan(`[${new Date().toLocaleTimeString()}][${account.proxyLabel}]`),
                    `Ping ${chalk.green('success')} from ${chalk.cyan(account.truncateToken())}`,
                    `Network Quality: ${chalk.green(networkQuality)}`
                );
                account.retries = 0;
                return;
            } else {
                console.warn(chalk.red(`Ping failed for token ${account.truncateToken()} using proxy ${account.proxy}`));
                account.retries++;
            }
        } catch (error) {
            console.error(chalk.red(`Ping failed for token ${account.truncateToken()} using URL ${url}: ${error.message}`));
            account.retries++;
            if (account.retries >= 3) {
                account.active = false;
                console.error(chalk.red(`Deactivating proxy ${account.proxy} due to multiple failures`));
                return;
            }
        }
    }
}

async function runAccount(account) {
    try {
        console.log(chalk.cyan(`[${account.proxyLabel}]`), `Initializing account with proxy: ${account.proxy}`);
        const response = await executeRequest(DOMAIN_API.SESSION, {}, account);

        if (response.code === 0) {
            account.accountInfo = response.data;
            if (account.accountInfo.uid) {
                while (account.active) {
                    await performPing(account);
                    await new Promise(resolve => setTimeout(resolve, PING_INTERVAL));
                }
            } else {
                console.error(`No UID found for token ${account.truncateToken()}`);
            }
        } else {
            console.error(`Session initialization failed for token ${account.truncateToken()}`);
        }
    } catch (error) {
        console.error(`Failed to initialize account for token ${account.truncateToken()}: ${error.message}`);
    }
}

async function loadData(filename) {
    try {
        const data = await fs.readFile(filename, 'utf8');
        return data.split('\n').filter(line => line.trim());
    } catch (error) {
        console.error(`Failed to load data from ${filename}: ${error.message}`);
        process.exit(1);
    }
}

function displayHeader() {
    console.log(chalk.cyan(figlet.textSync('NODEPAY\nNETWORK', { font: 'Standard' })));
    console.log(chalk.yellow('NODEPAY NETWORK BOT'));
    console.log('WELCOME & ENJOY SIR!');
    console.log('AUTHOR : NOFAN RAMBE');
}

async function main() {
    const tokens = await loadData('np_tokens.txt');
    if (!tokens.length) {
        console.error('No tokens found in np_tokens.txt');
        return;
    }

    const token = tokens[0]; // Use first token
    const proxies = await loadData('proxies.txt');
    if (!proxies.length) {
        console.error('No proxies found in proxies.txt');
        return;
    }

    const accounts = proxies.map((proxy, i) => 
        new AccountData(token, proxy, `Proxy-${i + 1}`)
    );

    await Promise.all(accounts.map(runAccount));
}

process.on('SIGINT', () => {
    console.log('Program terminated by user.');
    process.exit(0);
});

displayHeader();
console.log('\nUsing token from np_tokens.txt');
console.log('Required packages: axios https-proxy-agent socks-proxy-agent chalk uuid figlet user-agents');

main().catch(error => {
    console.error('Error in main process:', error);
    process.exit(1);
});
