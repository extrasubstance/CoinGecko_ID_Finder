import requests
import json
from typing import Dict, List, Tuple, Optional
import re
import logging
from tqdm import tqdm
import time
import os

CG_API_KEY = os.getenv('CG_API_KEY')

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Define the list of symbols we want to track
TARGET_SYMBOLS = {
    "BTC", "ETH", "XRP", "BNB", "SOL", "DOGE", "ADA", "TRX", "LINK", "TON", "AVAX", "XLM", "SUI", "HBAR", "LTC",
    "DOT", "BCH", "UNI", "kPEPE", "APT", "NEAR", "ONDO", "MNT", "AAVE", "ETC", "ENA", "TAO", "TIA", "ATOM", "RNDR",
    "RENDER", "KAS", "FIL", "ALGO", "ARB", "OP", "FET", "MKR", "IMX", "STX", "kBONK", "SEI", "INJ", "LDO", "GALA",
    "CRV", "SAND", "IOTA", "BSV", "CAKE", "kFLOKI", "PYTH", "ENS", "FARTCOIN", "NEO", "AR", "STRK", "CFX", "PENDLE",
    "RSR", "RUNE", "APE", "GRASS", "MATIC", "COMP", "BRETT", "MORPHO", "ZRO", "MINA", "SNX", "KAITO", "ZETA", "EIGEN",
    "BLUR", "SUPER", "DYDX", "POPCAT", "STG", "CELO", "AI16Z", "FXS", "ORDI", "GAS", "TURBO", "RLB", "POLYX", "GMT",
    "GMX", "POL", "IO", "SUSHI", "ALT", "UMA", "MANTA", "ILV", "ANIME", "BOME", "USUAL", "AIXBT", "BIGTIME", "BLAST",
    "PEOPLE", "DYM", "YGG", "ORBS", "REQ", "STRAX", "TRB", "USTC", "XAI", "TNSR", "ARK", "CYBER", "BNT", "OGN",
    "GRIFFAIN", "MOODENG", "MAV", "ZEREBRO", "LISTA", "BADGER", "RDNT", "CATI", "PIXEL", "LOOM", "VINE", "MAVIA",
    "MYRO", "JELLY", "BLZ", "OX", "PANDORA", "CANTO", "UNIBOT", "FRIEND", "OMNI", "BANANA", "ZK", "PURR", "JUP",
    "WLD", "PNUT", "SCR", "S", "FTM", "HPOS", "kSHIB", "SHIA", "FTT", "MEME", "ZEN", "NFTI", "kLUNC", "JTO", "NTRN",
    "ACE", "WIF", "W", "AI", "ETHFI", "SAGA", "MERL", "REZ", "NOT", "MEW", "kDOGS", "HMSTR", "NEIROETH", "kNEIRO",
    "GOAT", "CHILLGUY", "HYPE", "ME", "MOVE", "VIRTUAL", "PENGU", "BIO", "SPX", "TRUMP", "MELANIA", "VVV", "BERA",
    "TST", "LAYER", "IP", "OM", "NIL"
}

# Manual overrides for known problematic symbols
MANUAL_OVERRIDES = {
    "kPEPE": "pepe",
}

def fetch_coingecko_list() -> List[Dict]:
    """Fetch the current list of coins from CoinGecko."""
    logger.info("Fetching coin list from CoinGecko...")
    url = "https://pro-api.coingecko.com/api/v3/coins/list"
    headers = {
        'accept': 'application/json',
        'x-cg-pro-api-key': CG_API_KEY
    }
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        coins = response.json()
        logger.info(f"Successfully fetched {len(coins)} coins from CoinGecko")
        return coins
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching coin list: {e}")
        raise

def fetch_market_data(coin_ids: List[str]) -> Dict[str, float]:
    """Fetch market cap data for a list of coin IDs."""
    logger.info("Fetching market data...")
    market_caps = {}
    batch_size = 250
    total_batches = (len(coin_ids) + batch_size - 1) // batch_size
    
    for i in tqdm(range(0, len(coin_ids), batch_size), desc="Fetching market data", total=total_batches):
        batch = coin_ids[i:i+batch_size]
        url = f"https://pro-api.coingecko.com/api/v3/coins/markets"
        params = {
            'vs_currency': 'usd',
            'ids': ','.join(batch),
            'order': 'market_cap_desc',
            'per_page': batch_size,
            'page': 1,
            'sparkline': False
        }
        headers = {
            'accept': 'application/json',
            'x-cg-pro-api-key': CG_API_KEY
        }
        try:
            response = requests.get(url, params=params, headers=headers)
            response.raise_for_status()
            data = response.json()
            for coin in data:
                market_caps[coin['id']] = coin.get('market_cap', 0)
            time.sleep(0.5)  # Rate limiting
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching market data for batch {i//batch_size + 1}: {e}")
            continue
    
    logger.info(f"Successfully fetched market data for {len(market_caps)} coins")
    return market_caps

def normalize_symbol(symbol: str) -> str:
    """Normalize a symbol for comparison."""
    # Remove common prefixes and suffixes
    symbol = re.sub(r'^k', '', symbol)  # Remove 'k' prefix
    symbol = re.sub(r'^t', '', symbol)  # Remove 't' prefix
    symbol = re.sub(r'-token$', '', symbol)  # Remove '-token' suffix
    return symbol.upper()

def find_best_match(symbol: str, coins: List[Dict], market_caps: Dict[str, float]) -> Optional[str]:
    """Find the best matching coin ID for a given symbol using multiple strategies and market cap."""
    normalized_symbol = normalize_symbol(symbol)
    matches = []
    
    # Strategy 1: Direct match
    for coin in coins:
        if coin['symbol'].upper() == normalized_symbol:
            market_cap = market_caps.get(coin['id'], 0) or 0  # Convert None to 0
            matches.append((coin['id'], market_cap))
    
    # Strategy 2: Case-insensitive match
    if not matches:
        for coin in coins:
            if coin['symbol'].upper() == symbol.upper():
                market_cap = market_caps.get(coin['id'], 0) or 0  # Convert None to 0
                matches.append((coin['id'], market_cap))
    
    # Strategy 3: Match without prefixes/suffixes
    if not matches:
        for coin in coins:
            if normalize_symbol(coin['symbol']) == normalized_symbol:
                market_cap = market_caps.get(coin['id'], 0) or 0  # Convert None to 0
                matches.append((coin['id'], market_cap))
    
    # Strategy 4: Fuzzy match (if symbol is close enough)
    if not matches and len(normalized_symbol) > 3:
        for coin in coins:
            if normalized_symbol in coin['symbol'].upper():
                market_cap = market_caps.get(coin['id'], 0) or 0  # Convert None to 0
                matches.append((coin['id'], market_cap))
    
    # Return the match with the highest market cap
    if matches:
        best_match = max(matches, key=lambda x: x[1])
        if len(matches) > 1:
            logger.debug(f"Multiple matches found for {symbol}: {matches}")
        return best_match[0]
    
    return None

def create_symbol_to_id_mapping(coins: List[Dict]) -> Dict[str, str]:
    """Create a mapping from symbol to id, handling duplicates and edge cases."""
    logger.info("Creating symbol to ID mapping...")
    symbol_to_id = {}
    
    # First, apply manual overrides
    logger.info("Applying manual overrides...")
    for symbol, id in MANUAL_OVERRIDES.items():
        if symbol in TARGET_SYMBOLS:
            symbol_to_id[symbol] = id
            logger.debug(f"Applied manual override: {symbol} -> {id}")
    
    # Fetch market data for all coins
    coin_ids = [coin['id'] for coin in coins]
    market_caps = fetch_market_data(coin_ids)
    
    # Then process remaining symbols
    logger.info("Processing remaining symbols...")
    for symbol in tqdm(TARGET_SYMBOLS, desc="Matching symbols"):
        if symbol not in symbol_to_id:  # Skip if already handled by manual override
            best_match = find_best_match(symbol, coins, market_caps)
            if best_match:
                symbol_to_id[symbol] = best_match
                logger.debug(f"Matched {symbol} -> {best_match}")
            else:
                symbol_to_id[symbol] = "MISSING_ID"
                logger.warning(f"No match found for {symbol}")
    
    return symbol_to_id

def update_coingecko_ids_file(current_mappings: Dict[str, str], new_mappings: Dict[str, str]) -> Dict[str, str]:
    """Update the coingecko_ids dictionary with new mappings while preserving existing ones."""
    logger.info("Updating coingecko_ids file...")
    updated_mappings = {}
    
    # Only keep mappings for our target symbols
    for symbol in TARGET_SYMBOLS:
        if symbol in new_mappings:
            updated_mappings[symbol] = new_mappings[symbol]
        elif symbol in current_mappings:
            updated_mappings[symbol] = current_mappings[symbol]
        else:
            updated_mappings[symbol] = "MISSING_ID"
    
    return updated_mappings

def main():
    try:
        logger.info("Starting CoinGecko ID update process...")
        
        # Fetch current CoinGecko list
        coins = fetch_coingecko_list()
        
        # Create new mappings
        new_mappings = create_symbol_to_id_mapping(coins)
        
        # Read current coingecko_ids.py file
        logger.info("Reading current coingecko_ids.py file...")
        with open('app/services/coingecko_id.py', 'r') as f:
            content = f.read()
        
        # Extract current mappings
        current_mappings = {}
        exec(content, {'coingecko_ids': current_mappings})
        
        # Update mappings
        updated_mappings = update_coingecko_ids_file(current_mappings, new_mappings)
        
        # Generate new file content
        logger.info("Generating new file content...")
        new_content = "coingecko_ids = {\n"
        
        # Sort symbols: first by whether they're missing, then alphabetically
        sorted_symbols = sorted(updated_mappings.items(), 
                              key=lambda x: (x[1] == "MISSING_ID", x[0]))
        
        for symbol, id in sorted_symbols:
            new_content += f'    "{symbol}": "{id}",\n'
        new_content += "}\n"
        
        # Write updated content back to file
        logger.info("Writing updated content to file...")
        with open('app/services/coingecko_id.py', 'w') as f:
            f.write(new_content)
        
        # Print statistics
        total_symbols = len(updated_mappings)
        missing_ids = sum(1 for id in updated_mappings.values() if id == "MISSING_ID")
        logger.info(f"Update complete! Total symbols: {total_symbols}, Missing IDs: {missing_ids}")
        
        # Print problematic symbols for manual review
        if missing_ids > 0:
            logger.warning("\nSymbols that might need manual review:")
            for symbol, id in sorted_symbols:
                if id == "MISSING_ID":
                    logger.warning(f"- {symbol}")
        
    except Exception as e:
        logger.error(f"An error occurred during the update process: {e}")
        raise

if __name__ == "__main__":
    main() 