from flask import Flask, render_template, request, jsonify
from search_utils import get_coingecko_ids

app = Flask(__name__)

@app.route('/', methods=['GET'])
def index():
    return render_template('index.html')

@app.route('/generate', methods=['POST'])
def generate():
    data = request.json
    target_tickers = data.get('target_tickers', '')
    manual_overrides = data.get('manual_overrides', '')
    
    # Process target tickers
    tickers = [t.strip() for t in target_tickers.split(',') if t.strip()]
    
    # Get CoinGecko IDs
    results = get_coingecko_ids(tickers)
    
    # Apply manual overrides
    if manual_overrides:
        override_dict = {}
        for override in manual_overrides.split(','):
            if ':' in override:
                ticker, token_id = override.split(':')
                override_dict[ticker.strip().upper()] = token_id.strip()
        
        for result in results:
            if result['ticker'] in override_dict:
                result['token_id'] = override_dict[result['ticker']]
                result['link'] = f'https://www.coingecko.com/en/coins/{result["token_id"]}'
                result['fuzzy_match'] = False
                result['matched_ticker'] = None
    
    return jsonify(results)

if __name__ == '__main__':
    app.run(debug=True) 