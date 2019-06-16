Oanda API wrapper
=================

API wrapper for [Oanda](https://oanda.com "Online Trading & FX for Business | OANDA") broker

Python requests-like library that allows making API calls through
Oanda-specific Session and simplifies working with API responses.

Install
=======

### Using pip:

```bash
pip install git+https://okaminoseishin/oanda-api.git
```

Design
======

Endpoints represented as request methods of Oanda-specific Session object, like `requests.Session().get()`, and organized in groups in the same way as in [API documentation](http://developer.oanda.com/rest-live-v20/introduction/ "Oanda REST-V20 API"). Each method-endpoint in these groups binded directly to Session, so they shares one context, which acts as `requests.Session()`, preserving TCP connection, cache etc.

Usage
=====

### API-endpoint access

#### Create context

```python
import os
import oanda

accountID = os.environ['OANDA_ACCOUNT_ID']
context = oanda.Context(os.environ['OANDA_TOKEN'], type='practice')
```

#### Or as context manager

```python
with oanda.Context(os.environ['OANDA_TOKEN'], type='practice') as context:
    trades = context.trade.trades(accountID).trades
    print(trades[0].unrealizedPL)
```

### Market Order with relative Stop Loss

```python
result = context.order.create(accountID, **{
    'type': 'MARKET',
    'instrument': 'EUR_USD',
    'units': 1000,
    'stopLossOnFill': {
        'distance': 10
}})
```

### Price streaming

```python
for price in context.pricing.stream(accountID, 'EUR_USD', 'AUD_CAD'):
    print(price.bids, price.asks)
```
