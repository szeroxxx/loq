"""
Test script to verify TRX balance checking is working correctly after the fix
"""
from web3 import Web3
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Connect to BSC
web3 = Web3(Web3.HTTPProvider('https://bsc-dataseed.binance.org/'))

# Token configurations
token_contracts = {
    'TRX': '0xCE7de646e7208a4Ef112cb6ed5038FA6cC6b12e3',
    'USDT': '0x55d398326f99059fF775485246999027B3197955'
}

token_decimals = {
    'TRX': 6,    # TRX uses 6 decimals
    'USDT': 18   # USDT uses 18 decimals
}

# ERC-20 ABI for balanceOf
token_abi = [
    {
        "constant": True,
        "inputs": [{"name": "_owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "balance", "type": "uint256"}],
        "type": "function"
    }
]

def test_token_balance(address, token_name, contract_address):
    """Test token balance with proper decimal handling"""
    try:
        contract = web3.eth.contract(address=contract_address, abi=token_abi)
        balance_raw = contract.functions.balanceOf(address).call()
        
        # Get correct decimals
        decimals = token_decimals.get(token_name, 18)
        
        # Convert using correct decimals
        balance_readable = balance_raw / (10 ** decimals)
        
        logger.info(f"{token_name} Balance:")
        logger.info(f"  Raw balance: {balance_raw}")
        logger.info(f"  Decimals: {decimals}")
        logger.info(f"  Readable balance: {balance_readable:.8f}")
        logger.info(f"  Using old method (18 decimals): {balance_raw / (10 ** 18):.18f}")
        
        return balance_readable
        
    except Exception as e:
        logger.error(f"Error checking {token_name} balance: {e}")
        return 0

def main():
    """Test the TRX balance fix"""
    logger.info("Testing TRX balance fix...")
    logger.info("=" * 60)
    
    # Test with a known address that might have TRX
    # You can replace this with any BSC address you want to test
    test_address = "0x8894E0a0c962CB723c1976a4421c95949bE2D4E3"  # Binance Hot Wallet (likely has TRX)
    
    logger.info(f"Testing address: {test_address}")
    logger.info("-" * 60)
    
    # Test TRX balance
    trx_balance = test_token_balance(test_address, 'TRX', token_contracts['TRX'])
    
    logger.info("-" * 60)
    
    # Test USDT balance for comparison
    usdt_balance = test_token_balance(test_address, 'USDT', token_contracts['USDT'])
    
    logger.info("=" * 60)
    logger.info("SUMMARY:")
    logger.info(f"TRX Balance: {trx_balance:.8f}")
    logger.info(f"USDT Balance: {usdt_balance:.8f}")
    
    if trx_balance > 0:
        logger.info("✅ TRX balance detection is working!")
    else:
        logger.info("⚠️ No TRX balance found (this might be normal if the address has no TRX)")

if __name__ == "__main__":
    main()
