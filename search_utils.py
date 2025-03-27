import requests
import logging
from typing import Dict, List, Optional
from common_mapping import COMMON_CRYPTO_MAPPING

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def get_coingecko_ids(tickers: List[str]):
    """Get CoinGecko IDs for a list of tickers with improved matching and false positive prevention."""
    results = []
    tickers_to_search = []
    
    # First check common mapping
    for ticker in tickers:
        ticker = ticker.strip().upper()
        if ticker in COMMON_CRYPTO_MAPPING:
            results.append({
                'ticker': ticker,
                'token_id': COMMON_CRYPTO_MAPPING[ticker],
                'link': f'https://www.coingecko.com/en/coins/{COMMON_CRYPTO_MAPPING[ticker]}',
                'fuzzy_match': False,
                'matched_ticker': ticker
            })
        else:
            results.append({
                'ticker': ticker,
                'token_id': 'Not found',
                'link': '',
                'fuzzy_match': False,
                'matched_ticker': None
            })
            tickers_to_search.append(ticker)
    
    # Skip API calls if all tickers were in common mapping
    if not tickers_to_search:
        return results
    
    # Get the list of all coins from CoinGecko
    try:
        response = requests.get('https://api.coingecko.com/api/v3/coins/list?include_platform=false')
        response.raise_for_status()
        all_coins = response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching coin list: {e}")
        return results
    
    # Create lookup dictionaries for faster searching
    symbol_to_coins = {}
    id_to_coin = {}
    
    for coin in all_coins:
        # Symbol lookup (case insensitive)
        symbol = coin['symbol'].upper()
        if symbol not in symbol_to_coins:
            symbol_to_coins[symbol] = []
        symbol_to_coins[symbol].append(coin)
        
        # ID lookup
        id_to_coin[coin['id']] = coin
    
    # Collect potential matches for all tickers
    potential_matches = {}
    for ticker in tickers_to_search:
        ticker_upper = ticker.upper()
        ticker_lower = ticker.lower()
        potential_matches[ticker] = []
        
        # 1. Exact symbol match (highest priority)
        if ticker_upper in symbol_to_coins:
            for coin in symbol_to_coins[ticker_upper]:
                potential_matches[ticker].append((coin, 'exact_symbol', 100))
        
        # 2. ID-based matching
        for coin_id, coin in id_to_coin.items():
            # Only match if the ID is exactly the ticker or has clear word boundaries
            if coin_id == ticker_lower:
                potential_matches[ticker].append((coin, 'exact_id_match', 95))
            elif f"-{ticker_lower}-" in f"-{coin_id}-":  # Ensure word boundaries
                potential_matches[ticker].append((coin, 'id_contains_ticker_with_boundaries', 90))
            # Handle special case where ID is hyphenated version of ticker
            elif coin_id.replace('-', '') == ticker_lower:
                potential_matches[ticker].append((coin, 'id_is_hyphenated_ticker', 95))
        
        # 3. Name-based matching with stricter rules
        for coin in all_coins:
            coin_name_upper = coin['name'].upper()
            coin_name_parts = coin_name_upper.split('-')
            coin_name_words = coin_name_upper.split(' ')
            
            # Only match if ticker is a complete word in the name
            if ticker_upper in coin_name_parts or ticker_upper in coin_name_words:
                # Check if ticker is not just a small substring of a longer word
                is_substring = False
                for part in coin_name_parts + coin_name_words:
                    if ticker_upper != part and ticker_upper in part and len(ticker_upper) < len(part) * 0.7:
                        is_substring = True
                        break
                
                if not is_substring:
                    potential_matches[ticker].append((coin, 'name_contains_ticker_as_word', 50))
            
            # Special case for hyphenated names
            if '-' in coin_name_upper:
                # Ticker is first part of hyphenated name
                if ticker_upper == coin_name_parts[0]:
                    potential_matches[ticker].append((coin, 'name_starts_with_ticker', 75))
                # Ticker is concatenation of parts (lookbro -> look-bro)
                elif ''.join(coin_name_parts).upper() == ticker_upper:
                    potential_matches[ticker].append((coin, 'name_parts_form_ticker', 85))
    
    # Get market caps for all potential matches
    coin_ids_to_check = []
    for matches in potential_matches.values():
        coin_ids_to_check.extend([match[0]['id'] for match in matches])
    
    market_caps = {}
    if coin_ids_to_check:
        market_caps = fetch_market_data(list(set(coin_ids_to_check)))
    
    # Process matches with market cap information
    for i, result in enumerate(results):
        if result['token_id'] != 'Not found':
            continue
            
        ticker = result['ticker']
        matches = potential_matches.get(ticker, [])
        
        if not matches:
            continue
        
        # First check if we have exact symbol matches - if so, only consider those
        exact_matches = [m for m in matches if m[1] == 'exact_symbol']
        if exact_matches:
            matches = exact_matches
        
        # Score matches based on match type and market cap
        scored_matches = []
        for coin, match_type, base_score in matches:
            market_cap = market_caps.get(coin['id'], 0) or 0
            
            # For short tickers (3 chars or less), be very strict to avoid false positives
            if len(ticker) <= 3 and match_type not in ['exact_symbol', 'exact_id_match']:
                base_score *= 0.5  # Reduce score for fuzzy matches on short tickers
            
            # Adjust score based on market cap (logarithmic scale to avoid dominance)
            market_cap_score = 0
            if market_cap > 0:
                import math
                market_cap_score = math.log10(max(market_cap, 1)) * 10
            
            # Calculate final score
            final_score = base_score + market_cap_score
            
            # Debug logging for important cases
            if ticker.upper() in ['LOOKBRO', 'JELLY', 'SEND']:
                logger.info(f"Match for {ticker}: {coin['id']} (type: {match_type}, score: {final_score}, market cap: {market_cap})")
            
            scored_matches.append((coin, market_cap, final_score, match_type))
        
        # Find best match based on score
        if scored_matches:
            best_match = max(scored_matches, key=lambda x: x[2])
            coin, market_cap, score, match_type = best_match
            
            # Additional check for false positives
            # For short tickers, reject fuzzy matches with low scores
            if len(ticker) <= 3 and match_type != 'exact_symbol' and score < 100:
                # Check if the match is too ambiguous
                if coin['symbol'].upper() != ticker.upper() and coin['id'] != ticker.lower():
                    # This is likely a false positive
                    continue
            
            # Check if this is a fuzzy match
            is_fuzzy = match_type != 'exact_symbol'
            
            results[i] = {
                'ticker': ticker,
                'token_id': coin['id'],
                'link': f'https://www.coingecko.com/en/coins/{coin["id"]}',
                'fuzzy_match': is_fuzzy,
                'matched_ticker': coin['symbol'],
                'match_score': score,
                'match_type': match_type
            }
    
    return results

def fetch_market_data(coin_ids: List[str]) -> Dict[str, float]:
    """Fetch market cap data for specific coin IDs only."""
    logger.info(f"Fetching market data for {len(coin_ids)} coins...")
    market_caps = {}
    batch_size = 250
    
    for i in range(0, len(coin_ids), batch_size):
        batch = coin_ids[i:i+batch_size]
        url = "https://api.coingecko.com/api/v3/coins/markets"
        params = {
            'vs_currency': 'usd',
            'ids': ','.join(batch),
            'per_page': batch_size,
            'page': 1,
            'sparkline': False
        }
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            for coin in data:
                market_caps[coin['id']] = coin.get('market_cap', 0)
            if i + batch_size < len(coin_ids):
                requests.get("https://api.coingecko.com/api/v3/ping")  # Avoid rate limiting
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching market data: {e}")
    
    return market_caps
