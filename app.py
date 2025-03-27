from flask import Flask, render_template, request, jsonify
import pandas as pd
import requests
import time

app = Flask(__name__)

def get_coingecko_ids(symbols):
    # First, get the list of all coins from CoinGecko
    response = requests.get('https://api.coingecko.com/api/v3/coins/list')
    if response.status_code != 200:
        return []
    
    all_coins = response.json()
    
    # Create a mapping of symbols to IDs
    symbol_to_id = {coin['symbol'].upper(): coin['id'] for coin in all_coins}
    
    # Process input symbols
    results = []
    for symbol in symbols:
        symbol = symbol.strip().upper()
        if symbol in symbol_to_id:
            token_id = symbol_to_id[symbol]
            results.append({
                'symbol': symbol,
                'token_id': token_id,
                'link': f'https://www.coingecko.com/en/coins/{token_id}'
            })
        else:
            results.append({
                'symbol': symbol,
                'token_id': 'Not found',
                'link': ''
            })
    
    return results

@app.route('/', methods=['GET'])
def index():
    return render_template('index.html')

@app.route('/generate', methods=['POST'])
def generate():
    data = request.json
    target_symbols = data.get('target_symbols', '')
    manual_overrides = data.get('manual_overrides', '')
    
    # Process target symbols
    symbols = [s.strip() for s in target_symbols.split(',') if s.strip()]
    
    # Get CoinGecko IDs
    results = get_coingecko_ids(symbols)
    
    # Apply manual overrides
    if manual_overrides:
        override_dict = {}
        for override in manual_overrides.split(','):
            if ':' in override:
                symbol, token_id = override.split(':')
                override_dict[symbol.strip().upper()] = token_id.strip()
        
        for result in results:
            if result['symbol'] in override_dict:
                result['token_id'] = override_dict[result['symbol']]
    
    return jsonify(results)

if __name__ == '__main__':
    app.run(debug=True) 