from web3 import Web3
import json
import time

# Initialize Web3 and the Binance Smart Chain RPC URL
web3 = Web3(Web3.HTTPProvider('https://bsc-dataseed.binance.org/'))

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

def check_balance_from_private_key():
    starting_key = int("0e47966130f6a51043cb63f07a0f2a4e452a66bd5a0d3925776ed2b51be65fd6", 16)
    ending_key = int("10a8da1ab921c05d9f6d4af1df0c63cf3adc326d07ca6904beab70b9d27f87ce", 16)
    
    wallets_with_balance = []
    current_key = starting_key
    
    try:
        while current_key <= ending_key:
            private_key = f"{current_key:064x}"  # Format as 64-char hex string
            print(f"Checking Private Key: {private_key}")
            
            current_key += 1
            
            # Derive address from private key
            account = web3.eth.account.from_key('0x' + private_key)
            address = account.address
            
            # Check BNB balance
            balance_wei = web3.eth.get_balance(address)
            balance_bnb = float(web3.from_wei(balance_wei, 'ether'))
            
            # Object to store all balances
            balances = {"BNB": balance_bnb}
            
            # Check token balances
            for token, contract_address in token_contracts.items():
                contract = web3.eth.contract(address=contract_address, abi=token_abi)
                balance = contract.functions.balanceOf(address).call()
                # Convert balance to human-readable format (assuming 18 decimals)
                balance_readable = float(web3.from_wei(balance, 'ether'))
                balances[token] = balance_readable
            
            # Check if any balances are greater than 0
            has_balance = any(balance > 0 for balance in balances.values())
            
            if has_balance:
                wallet_data = {
                    "private_key": private_key,
                    "address": address,
                    "balances": balances
                }
                wallets_with_balance.append(wallet_data)
                print(f"Found wallet with balance: {address}")
                
                with open('wallets_with_balance.json', 'w') as f:
                    json.dump(wallets_with_balance, f, indent=4)
            time.sleep(0.1)
                
    except Exception as e:
        print(f"Error checking balances: {str(e)}")
        if wallets_with_balance:
            with open('wallets_with_balance.json', 'w') as f:
                json.dump(wallets_with_balance, f, indent=4)

if __name__ == "__main__":
    check_balance_from_private_key()