from core.order_manager import OrderManager

def test_order_manager_init():
    config = {
        'api_key': 'xxx', 'api_secret': 'yyy',
        'symbols': ['DOGE/USD'], 'order_buffer_atr': 0.5
    }
    om = OrderManager(config)
    assert hasattr(om, 'place_limit_order')