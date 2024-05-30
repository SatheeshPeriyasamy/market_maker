import ccxt
import pandas as pd
import logging
import time

# Setup logging
logging.basicConfig(filename='market_making_bot.log', level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s')

api_key = 'api_key'
api_secret = 'secret_key'

binance = ccxt.binance({
    'apiKey': api_key,
    'secret': api_secret,
    'enableRateLimit': True,
    'options': {
        'adjustForTimeDifference': True  
    }
})

symbols = ['SHIB/USDT']

def fetch_ohlcv(symbol, timeframe='1h', limit=100):
    ohlcv = binance.fetch_ohlcv(symbol, timeframe, limit=limit)
    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    return df

def get_balance(asset):
    try:
        balance = binance.fetch_balance()
        available_balance = balance['free'][asset]
        logging.info(f"Available balance for {asset}: {available_balance}")
        return available_balance
    except Exception as e:
        logging.error(f"Error fetching balance: {e}")
        return 0

def place_order(symbol, order_type, side, amount, price=None):
    try:
        if order_type == 'limit':
            order = binance.create_limit_order(symbol, side, amount, price)
        elif order_type == 'market':
            order = binance.create_market_order(symbol, side, amount)
        logging.info(f"Placed {side} order for {amount} {symbol} at {price}")
        return order
    except ccxt.InsufficientFunds as e:
        logging.error(f"Insufficient funds for placing order: {e}")
    except ccxt.InvalidOrder as e:
        logging.error(f"Invalid order parameters: {e}")
    except Exception as e:
        logging.error(f"Error placing order: {e}")

def adjust_order_size(symbol, amount, price):
    try:
        markets = binance.load_markets()
        market = markets[symbol]
        
        quote_asset = symbol.split('/')[1]
        balance = get_balance(quote_asset)
        max_amount_based_on_balance = balance / price
        
        amount = min(amount, max_amount_based_on_balance, market['limits']['amount']['max'])
        amount = max(amount, market['limits']['amount']['min'])
        
        return amount
    except Exception as e:
        logging.error(f"Error adjusting order size: {e}")
        return 0

def manage_orders(symbol):
    try:
        open_orders = binance.fetch_open_orders(symbol)
        current_price = binance.fetch_ticker(symbol)['last']
        for order in open_orders:
            if order['side'] == 'buy' and order['price'] < current_price * 0.98:
                binance.cancel_order(order['id'], symbol)
                logging.info(f"Cancelled buy order {order['id']} for {symbol} due to price deviation")
            elif order['side'] == 'sell' and order['price'] > current_price * 1.02:
                binance.cancel_order(order['id'], symbol)
                logging.info(f"Cancelled sell order {order['id']} for {symbol} due to price deviation")
    except Exception as e:
        logging.error(f"Error managing orders: {e}")

def market_making_strategy(symbol, chunk_size=0.01, spread=0.001, max_order_value_percentage=0.05):
    try:
        ticker = binance.fetch_ticker(symbol)
        last_price = ticker['last']
        base_asset, quote_asset = symbol.split('/')
        
        quote_balance = get_balance(quote_asset) / len(symbols)  # Split balance among symbols
        base_balance = get_balance(base_asset) / len(symbols)
        
        max_order_value = quote_balance * max_order_value_percentage
        
        buy_price = last_price * (1 - spread)
        sell_price = last_price * (1 + spread)
        
        buy_amount = adjust_order_size(symbol, max_order_value / buy_price, buy_price)
        sell_amount = adjust_order_size(symbol, max_order_value / sell_price, sell_price)
        
        if quote_balance > buy_amount * buy_price:
            place_order(symbol, 'limit', 'buy', buy_amount, buy_price)
        
        if base_balance > sell_amount:
            place_order(symbol, 'limit', 'sell', sell_amount, sell_price)
        
        logging.info(f"Placed market-making orders for {symbol}: Buy {buy_amount} at {buy_price}, Sell {sell_amount} at {sell_price}")
    except Exception as e:
        logging.error(f"Error in market-making strategy for {symbol}: {e}")

def trading_loop():
    while True:
        try:
            for symbol in symbols:
                manage_orders(symbol)
                market_making_strategy(symbol)
            logging.info("Completed trading loop iteration")
        except Exception as e:
            logging.error(f"Error in trading loop: {e}")
        time.sleep(5)

if __name__ == "__main__":
    trading_loop()
