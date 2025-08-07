import requests

# Your CoinMarketCap API Key
CMC_API_KEY = '65822c4a-0660-47ba-88d5-ab3e3ef5d8b1'

# Fetch top gainers from CoinMarketCap
def get_top_gainers(limit=100):
    url = 'https://pro-api.coinmarketcap.com/v1/cryptocurrency/listings/latest'
    headers = {
        'Accepts': 'application/json',
        'X-CMC_PRO_API_KEY': CMC_API_KEY,
    }
    params = {
        'start': '1',
        'limit': str(limit),
        'convert': 'USD'
    }
    response = requests.get(url, headers=headers, params=params)
    data = response.json()

    gainers = []
    for coin in data['data']:
        name = coin['name']
        symbol = coin['symbol']
        percent_change_1h = coin['quote']['USD']['percent_change_1h']
        gainers.append((name, symbol, percent_change_1h))

    # Sort descending by 1h % change
    gainers.sort(key=lambda x: x[2], reverse=True)
    return gainers[:10]  # Top 10

# Fetch Kraken tradable asset pairs
def get_kraken_pairs():
    url = 'https://api.kraken.com/0/public/AssetPairs'
    response = requests.get(url)
    data = response.json()
    
    symbols = set()
    for pair_info in data['result'].values():
        altname = pair_info.get('altname', '')
        # Common format: XXBTZUSD, XETHZUSD etc.
        if 'USD' in altname:  # Focus only on USD pairs
            # Extract asset symbol, e.g., "XETHZUSD" -> "ETH"
            asset = altname.replace('ZUSD', '').replace('USD', '')
            asset = asset.lstrip('X').lstrip('Z')
            symbols.add(asset.upper())
    return symbols

# Cross-match hot coins with Kraken tradables
def filter_tradable_gainers():
    top_gainers = get_top_gainers()
    kraken_symbols = get_kraken_pairs()

    tradable = []
    for name, symbol, change in top_gainers:
        if symbol.upper() in kraken_symbols:
            tradable.append((name, symbol, change))

    print("\n?? Tradable Hot Coins on Kraken ??\n")
    for name, symbol, change in tradable:
        print(f"{name} ({symbol}): {change:.2f}% in the past hour")
    
    if not tradable:
        print("No hot coins tradable on Kraken at the moment.")

# Run it
filter_tradable_gainers()
