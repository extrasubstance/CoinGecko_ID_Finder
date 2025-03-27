import requests
import time
import json
from typing import Dict, List

# Configuration
CONFIG = {
    'total_limit': 2000,        # Total number of coins to fetch
    'per_page': 100,           # Maximum coins per page (CoinGecko limit)
    'delay_between_requests': 5,  # Seconds to wait between requests
    'rate_limit_delay': 30,     # Seconds to wait if rate limit is hit
    'output_file': 'common_mapping.py'  # Output file for the mapping
}

def fetch_top_coins() -> List[Dict]:
    """Fetch top coins by market cap from CoinGecko using pagination."""
    url = "https://api.coingecko.com/api/v3/coins/markets"
    all_coins = []
    total_pages = (CONFIG['total_limit'] + CONFIG['per_page'] - 1) // CONFIG['per_page']
    
    for page in range(1, total_pages + 1):
        params = {
            'vs_currency': 'usd',
            'order': 'market_cap_desc',
            'per_page': CONFIG['per_page'],
            'page': page,
            'sparkline': False
        }
        
        try:
            print(f"Fetching page {page} of {total_pages}...")
            response = requests.get(url, params=params)
            response.raise_for_status()
            coins = response.json()
            all_coins.extend(coins)
            
            # Respect rate limiting with longer delay
            if page < total_pages:  # Don't delay after the last request
                print(f"Waiting {CONFIG['delay_between_requests']} seconds before next request...")
                time.sleep(CONFIG['delay_between_requests'])
            
            # Break if we've got enough coins
            if len(all_coins) >= CONFIG['total_limit']:
                all_coins = all_coins[:CONFIG['total_limit']]
                break
                
        except requests.exceptions.RequestException as e:
            print(f"Error fetching page {page}: {e}")
            if "429" in str(e):  # Rate limit error
                print(f"Rate limit hit. Waiting {CONFIG['rate_limit_delay']} seconds before retrying...")
                time.sleep(CONFIG['rate_limit_delay'])
                continue
            break
    
    return all_coins

def generate_mapping(coins: List[Dict]) -> Dict[str, str]:
    """Generate mapping from ticker to id for the coins."""
    mapping = {}
    for coin in coins:
        ticker = coin['symbol'].upper()
        # Skip if we already have this ticker (keep the first occurrence)
        if ticker not in mapping:
            mapping[ticker] = coin['id']
    return mapping

def save_mapping(mapping: Dict[str, str]):
    """Save the mapping to a Python file."""
    with open(CONFIG['output_file'], 'w') as f:
        f.write("COMMON_CRYPTO_MAPPING = {\n")
        for ticker, id in sorted(mapping.items()):
            f.write(f"    '{ticker}': '{id}',\n")
        f.write("}\n")

def main():
    print(f"Fetching top {CONFIG['total_limit']} cryptocurrencies by market cap...")
    coins = fetch_top_coins()
    
    if not coins:
        print("Failed to fetch data")
        return
    
    print(f"Successfully fetched {len(coins)} coins")
    mapping = generate_mapping(coins)
    
    print(f"Generated mapping with {len(mapping)} entries")
    save_mapping(mapping)
    print(f"Mapping saved to {CONFIG['output_file']}")

if __name__ == "__main__":
    main() 