#!/usr/bin/env python
# coding: utf-8

from __future__ import print_function, unicode_literals
import urllib
import json
import os
import time

from flask import Flask
from flask import request
from flask import make_response

# Flask app should start in global layout
app = Flask(__name__)

MAX_COINS = 1000
baseurl = "https://api.coinmarketcap.com/v1/ticker/?convert=KRW&limit={}".format(MAX_COINS)
cache = []


@app.route('/webhook', methods=['POST'])
def webhook():
    if cached_at < time.time() - 60:
        cache_price()

    res = processRequest(request.get_json(silent=True, force=True))

    r = make_response(json.dumps(res, indent=4))
    r.headers['Content-Type'] = 'application/json'
    return r


def processRequest(req):
    if req.get("result").get("action") == u"QueryCoinPrice":

        parameters = req.get("result").get("parameters")
        coin = parameters.get("coin", "")

        result = filter(lambda c: c["symbol"] == coin, cache)

        if not result:
            coin_id = map_coin_id(coin)
            if coin_id == "all":
                result = cache
            else:
                result = filter(lambda c: c["id"] == coin_id, cache)

        return make_webhook_result(result)
    else:
        return {}


def map_coin_id(coin_name):
    coin_alias_map = {
        "bitcoin": ["비트코인", "BTC", "XBT"],
        "ethereum": ["이더리움", "이시리움", "이더", "ETH"],
        "ethereum-classic": ["이더리움클래식", "이클", "ETC"],
        "digibyte": ["디지바이트", "대구은행", "DGB"],
    }

    for coin_id, coin_aliases in coin_alias_map.items():
        if coin_name in coin_aliases:
            return coin_id

    return "all"


def make_webhook_result(coin_prices):
    if coin_prices is None or len(coin_prices) == 0:
        return {}

    coin_prices = beautify_coin_info(coin_prices)

    speech = u"문의하신 가상화폐 가격은 다음과 같습니다."

    if len(coin_prices) > 1:
        slack_fields = []
        for coin in sorted(coin_prices, key=lambda c: int(c['rank']))[:10]:
            slack_fields.append({
                "title": coin.get("name"),
                "value": "미화 " + coin.get("price_usd") + " 달러\n" +
                         "한화 " + coin.get("price_krw") + " 원",
                "short": "true"
            })

        slack_message = {
            "text": speech,
            "attachments": [
                {
                    "title": "가상화폐 가격",
                    "title_link": "https://coinmarketcap.com",
                    "color": "#36a64f",
                    "fields": slack_fields
                }
            ]
        }

    else:
        coin = coin_prices[0]
        slack_message = {
            "text": speech,
            "attachments": [
                {
                    "title": coin.get("name") + "(" + coin.get("symbol") + ") - " + coin.get("last_updated") + " 기준",
                    "title_link": "https://coinmarketcap.com/currencies/" + coin.get("id"),
                    "color": "#36a64f",
                    "fields": [
                        {
                            "title": "시세 (= " + coin.get("price_btc") + " Bitcoin)",
                            "value": "미화 " + coin.get("price_usd") + " 달러\n" +
                                     "한화 " + coin.get("price_krw") + " 원",
                            "short": "false"
                        },
                        {},
                        {
                            "title": "시장규모 (" + coin.get("rank") + "위)",
                            "value": "미화 " + coin.get("market_cap_usd") + " 달러\n" +
                                     "한화 " + coin.get("market_cap_krw") + " 원",
                            "short": "false"
                        },
                        {
                            "title": "가격 변동",
                            "value": "최근 7일간 " + coin.get("percent_change_7d") + " %\n" +
                                     "최근 24시간 " + coin.get("percent_change_24h") + " %\n" +
                                     "최근 1시간 " + coin.get("percent_change_1h") + " %",
                            "short": "false"
                        },
                        {
                            "title": "거래량 (최근 24시간)",
                            "value": "미화 " + coin.get("24h_volume_usd") + " 달러\n" +
                                     "한화 " + coin.get("24h_volume_krw") + " 원",
                            "short": "false"
                        },
                        {
                            "title": "통화량",
                            "value": "전체 통화량 " + coin.get("total_supply") + " " + coin.get("symbol") + "\n" +
                                     "거래 통화량 " + coin.get("available_supply") + " " + coin.get("symbol"),
                            "short": "false"
                        },

                    ]
                }
            ]
        }

    print(json.dumps(slack_message))

    return {
        "speech": speech,
        "displayText": speech,
        "data": {"slack": slack_message},
        # "contextOut": [],
        "source": "apiai-weather-webhook-sample"
    }


def beautify_coin_info(info):
    from datetime import datetime

    result = []

    for coin in info:
        result_coin = {}
        for k, v in coin.items():
            try:
                if any([s in k for s in ("price_btc",)]):
                    result_coin[k] = "{:,.8f}".format(float(v))
                elif any([s in k for s in ("usd",)]):
                    result_coin[k] = "{:,.2f}".format(float(v))
                elif any([s in k for s in ("krw",)]):
                    result_coin[k] = "{:,.0f}".format(float(v))
                elif any(s in k for s in ("market_cap", "volume", "supply")):
                    result_coin[k] = "{:,.2f}".format(float(v))
                elif k == "last_updated":
                    result_coin[k] = datetime.fromtimestamp(int(v)).strftime('%Y-%m-%d %H:%M:%S')
                else:
                    result_coin[k] = v
            except TypeError:
                pass

        result.append(result_coin)

    return result


def cache_price():
    global cache, cached_at

    # for one in json.loads(urllib.urlopen(baseurl).read()):
    #     cache[one.get("id")] = one
    cache = json.loads(urllib.urlopen(baseurl).read())
    cached_at = time.time()

    print("cache done.")


if __name__ == '__main__':
    # cache init
    cache_price()

    port = int(os.getenv('PORT', 5000))

    print("Starting app on port %d" % port)

    app.run(debug=False, port=port, host='0.0.0.0')
