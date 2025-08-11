from web3 import Web3
import json
import time
import asyncio
import aiohttp
from concurrent.futures import ThreadPoolExecutor
import threading
from queue import Queue

class OptimizedWalletChecker:
    def __init__(self):
        # Use multiple RPC endpoints for load balancing
        self.rpc_urls = [
            'https://bsc-dataseed.binance.org/',
            'https://bsc-dataseed1.defibit.io/',
            'https://bsc-dataseed1.ninicoin.io/',
            'https://bsc-dataseed2.defibit.io/',
            'https://bsc-dataseed3.defibit.io/',
            'https://bsc-dataseed4.defibit.io/'
        ]
        
        # Initialize multiple Web3 instances
        self.web3_instances = [Web3(Web3.HTTPProvider(url)) for url in self.rpc_urls]
        self.current_web3_index = 0
        
        # BEP-20 Token Contract Addresses on BSC
        self.token_contracts = {
            'USDT': '0x55d398326f99059fF775485246999027B3197955',
            'BTC': '0x7130d2A12B9BCbFAe4f2634d864A1Ee1Ce3Ead9c',
            'XRP': '0x1D2F0da169ceB9fC7B3144628dB156f3F6c60dBE',
            'TRX': '0xCE7de646e7208a4Ef112cb6ed5038FA6cC6b12e3',
            'TON': '0x76A797A59Ba2C17726896976B7B3747BfD1d220f'
        }
        
        # Minimal ABI for ERC-20 balanceOf function
        self.token_abi = [
            {
                "constant": True,
                "inputs": [{"name": "_owner", "type": "address"}],
                "name": "balanceOf",
                "outputs": [{"name": "balance", "type": "uint256"}],
                "type": "function"
            }
        ]
        
        # Thread-safe storage
        self.wallets_with_balance = []
        self.lock = threading.Lock()
        
    def get_web3_instance(self):
        """Round-robin Web3 instance selection"""
        instance = self.web3_instances[self.current_web3_index]
        self.current_web3_index = (self.current_web3_index + 1) % len(self.web3_instances)
        return instance
    
    def check_single_wallet(self, private_key_int):
        """Check balance for a single wallet"""
        try:
            private_key = f"{private_key_int:064x}"
            web3 = self.get_web3_instance()
            
            # Derive address from private key
            account = web3.eth.account.from_key('0x' + private_key)
            address = account.address
            
            # Batch all balance checks
            balances = self.batch_balance_check(web3, address)
            
            # Check if any balances are greater than 0
            has_balance = any(balance > 0 for balance in balances.values())
            
            if has_balance:
                wallet_data = {
                    "private_key": private_key,
                    "address": address,
                    "balances": balances
                }
                
                with self.lock:
                    self.wallets_with_balance.append(wallet_data)
                    print(f"Found wallet with balance: {address}")
                    
                    # Save to JSON file
                    with open('wallets_with_balance.json', 'w') as f:
                        json.dump(self.wallets_with_balance, f, indent=4)
            
            return private_key_int
            
        except Exception as e:
            print(f"Error checking key {private_key_int:064x}: {str(e)}")
            return None
    
    def batch_balance_check(self, web3, address):
        """Optimized batch balance checking"""
        balances = {}
        
        try:
            # Check BNB balance
            balance_wei = web3.eth.get_balance(address)
            balances["BNB"] = float(web3.from_wei(balance_wei, 'ether'))
            
            # Batch token balance checks
            for token, contract_address in self.token_contracts.items():
                try:
                    contract = web3.eth.contract(address=contract_address, abi=self.token_abi)
                    balance = contract.functions.balanceOf(address).call()
                    balance_readable = float(web3.from_wei(balance, 'ether'))
                    balances[token] = balance_readable
                except:
                    balances[token] = 0.0
                    
        except Exception as e:
            print(f"Error in batch balance check for {address}: {str(e)}")
            # Return zero balances on error
            balances = {"BNB": 0.0}
            balances.update({token: 0.0 for token in self.token_contracts.keys()})
        
        return balances
    
    def check_balance_from_private_key_parallel(self, max_workers=20, batch_size=100):
        """Parallel version with batching and optimizations"""
        starting_key = int("0723cb2c987b52b409e5b4f72d4eb5a0c015637e532ebb7f81b7b95a870a87eb", 16)
        ending_key = int("09850ee620a36e3b62879c003f2a433eaac72f1dffe85a7f28f4f7235ea3afe3", 16)
        
        print(f"Checking range: {starting_key:064x} to {ending_key:064x}")
        print(f"Total keys to check: {ending_key - starting_key + 1:,}")
        
        current_key = starting_key
        
        try:
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                while current_key <= ending_key:
                    # Create batch of keys to process
                    batch_keys = []
                    for i in range(min(batch_size, ending_key - current_key + 1)):
                        batch_keys.append(current_key + i)
                    
                    # Submit batch to thread pool
                    futures = [executor.submit(self.check_single_wallet, key) for key in batch_keys]
                    
                    # Wait for batch completion with progress tracking
                    completed = 0
                    for future in futures:
                        try:
                            result = future.result(timeout=30)  # 30 second timeout per wallet
                            completed += 1
                            if completed % 10 == 0:
                                progress = ((current_key + completed - starting_key) / (ending_key - starting_key + 1)) * 100
                                print(f"Progress: {progress:.2f}% - Checked: {current_key + completed - starting_key:,} wallets")
                        except Exception as e:
                            print(f"Future error: {str(e)}")
                    
                    current_key += len(batch_keys)
                    
                    # Small delay between batches to prevent overwhelming the RPC
                    time.sleep(0.01)
                    
        except KeyboardInterrupt:
            print("Process interrupted by user")
        except Exception as e:
            print(f"Error in parallel processing: {str(e)}")
        finally:
            # Final save
            if self.wallets_with_balance:
                with open('wallets_with_balance.json', 'w') as f:
                    json.dump(self.wallets_with_balance, f, indent=4)
                print(f"Found {len(self.wallets_with_balance)} wallets with balance")

def check_balance_from_private_key():
    """Original function maintained for compatibility"""
    checker = OptimizedWalletChecker()
    checker.check_balance_from_private_key_parallel(max_workers=15, batch_size=50)

if __name__ == "__main__":
    # You can adjust these parameters for optimal performance:
    # max_workers: Number of parallel threads (15-30 recommended)
    # batch_size: Number of wallets per batch (50-200 recommended)
    
    checker = OptimizedWalletChecker()
    checker.check_balance_from_private_key_parallel(max_workers=20, batch_size=100)