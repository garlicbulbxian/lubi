#!/usr/bin/python3
#
# taker.py: EtherDelta taker client
# =================================
#
# This client waits until the EtherDelta order book is available,
# and then buys the best (cheapest) sell order from the book.
#
# Author: Tom Van Braeckel <tomvanbraeckel+etherdelta@gmail.com>
# License: MIT License (MIT)
#
# Installation:
# =============
# This client comes with service.py that contains common EtherDelta API service facilities.
# Please see service.py for instructions on how to install it and its dependencies.
#
# Configuration:
# ==============
# Copy config.ini.example to config.ini and fill in the values.
#
# Execution:
# ==========
# . venv/bin/activate   # initialize Python 3 virtual environment, not needed if you have python 3 installed system-wide
# python taker.py

import time
import sys
import configparser
import argparse
import schedule
import json
import pprint
import config.config_ini
import logging

from prettytable import PrettyTable

from etherdeltaclientservice import EtherDeltaClientService
from binance.client import Client

logger = logging.getLogger(__name__)


class Order:
    def __init__(self, price, volume):
        self.price = price
        self.volume = volume

    def stringify(self):
        return ['{0:.8f}'.format(self.price), '{0:.3f}'.format(self.volume)]


def parse_ed_tokens(tokens_file):
    with open(tokens_file) as data_file:
        data = json.load(data_file)
    return data


def get_parser():
    parser = argparse.ArgumentParser(description='Launch Wechat Bot.')
    parser.add_argument('-c', '--config-file', nargs='?', required=True,
                        help='config file')

    return parser.parse_args()


class Checker(object):
    def __init__(self, config):
        pass

    def check_order_book(self, ticker, number_of_orders=10):
        raise NotImplementedError("Please Implement this method")

    @staticmethod
    def get_print_table(orders):
        t = PrettyTable(['price', 'volume'])
        for order in orders:
            t.add_row(order.stringify())
        return t

    def print_order_book(self, symbol, sells, buys):
        print('order book for {}'.format(symbol))
        print('{}'.format(Checker.get_print_table(sells)))
        print('------------------------------------------------------------')
        print('{}'.format(Checker.get_print_table(buys)))

    def factory(type, config):
        if type == "ed":
            return EtherDeltaChecker(config)
        if type == "binance":
            return BinanceChecker(config)
        assert 0, "Bad checker creation: " + type

    factory = staticmethod(factory)


class BinanceChecker(Checker):
    def __init__(self, config):
        Checker.__init__(self, config)
        binance_config = dict(config.items('binance'))
        binance_api_key = binance_config.get('binance_api_key')
        binance_api_secret = binance_config.get('binance_api_secret')

        self.binance_client = Client(binance_api_key, binance_api_secret)

    def check_order_book(self, ticker, number_of_orders=10):
        symbol = '{}ETH'.format(ticker.upper())
        depth = self.binance_client.get_order_book(symbol=symbol)
        # prices = binance_client.get_all_tickers()

        binance_sells = depth['asks']
        binance_buys = depth['bids']

        top_binance_sells = list(reversed(binance_sells[0:number_of_orders]))
        top_binance_buys = binance_buys[0:number_of_orders]

        binance_sell_orders = list(
            map((lambda entry: Order(float(entry[0]), float(entry[1]))), top_binance_sells))
        binance_buy_orders = list(
            map((lambda entry: Order(float(entry[0]), float(entry[1]))), top_binance_buys))

        return (binance_sell_orders, binance_buy_orders)


class EtherDeltaChecker(Checker):
    def __init__(self, config):
        Checker.__init__(self, config)
        # Load config
        etherdelta_config = dict(config.items('etherdelta'))

        self.user_account = etherdelta_config.get('user_wallet_public_key')
        self.secret_key = etherdelta_config.get('user_wallet_private_key')

        # Load ed tokens
        self.tokens = parse_ed_tokens(etherdelta_config.get('tokens_file'))
        self.es = EtherDeltaClientService()

    def check_order_book(self, ticker, number_of_orders=10):
        symbol = '{}-ETH'.format(ticker.upper())
        token = self.tokens.get(ticker)

        if token is None:
            raise ValueError('No token found for {}'.format(ticker))

        def check_loop():
            logger.info("Getting order book")
            (ed_sells, ed_buys) = self.es.get_order_book()

            top_ed_sells = list(reversed(ed_sells[0:number_of_orders]))
            top_ed_buys = ed_buys[0:number_of_orders]

            if len(top_ed_sells) == 0 or len(top_ed_buys) == 0:
                return ()

            ed_sell_orders = list(map((lambda entry: Order(
                float(entry['price']), float(entry['ethAvailableVolume']))), top_ed_sells))
            ed_buy_orders = list(map((lambda entry: Order(
                float(entry['price']), float(entry['ethAvailableVolume']))), top_ed_buys))

            return (ed_sell_orders, ed_buy_orders)

        try:
            logger.info("EtherDelta token for ticker {}: {}".format(ticker, token))
    
            self.es.start(self.user_account, token)
            logger.info("EtherDeltaServiceClient started")
    
            self.es.printBalances(token, self.user_account)
    
            retries = 5
            for i in range(retries):
                orders = check_loop()
                if len(orders) == 0:
                    logger.info("No orders found, sleep for 10 seconds")
                    time.sleep(10)
                else:
                    return orders
           
            raise ValueError('No orders found after {} retries in EtherDelta\'s API, try later'.format(retries))
        finally:
            self.es.terminate()




def check(config, ticker):
    ed_checker = EtherDeltaChecker(config)
    ed_checker.check_order_book(ticker)


if __name__ == "__main__":
    args = get_parser()

    # Load config
    config = configparser.ConfigParser()
    config.read(args.config_file)

    schedule.every().minute.do(check, config, 'ven')

    while True:
        schedule.run_pending()
        time.sleep(10)

    logger.info("checker.py exiting")
    sys.exit()
