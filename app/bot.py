#!/usr/bin/python3

import configparser
import argparse

import config.config_ini
import logging

from app.checker import Checker

from telegram.ext import Updater, CommandHandler, MessageHandler, Filters
import telegram

logger = logging.getLogger(__name__)


def help(bot, update):
    """Send a message when the command /help is issued."""
    logger.info("help")
    update.message.reply_text('Help!')


def set_alerter(bot, update, args, job_queue, chat_data):
    """Add a job to the queue."""
    chat_id = update.message.chat_id
    try:
        # args[0] should contain the time for the timer in seconds
        due = int(args[0])
        if due < 0:
            update.message.reply_text('Sorry we can not go back to future!')
            return

        # Add job to queue
        job = job_queue.run_once(alarm, due, context=chat_id)
        chat_data['job'] = job

        update.message.reply_text('Timer successfully set!')

    except (IndexError, ValueError):
        update.message.reply_text('Usage: /set <seconds>')


def unset_alerter(bot, update, chat_data):
    """Remove the job if the user changed their mind."""
    if 'job' not in chat_data:
        update.message.reply_text('You have no active timer')
        return

    job = chat_data['job']
    job.schedule_removal()
    del chat_data['job']

    update.message.reply_text('Timer successfully unset!')


def check_order_book(bot, update, args):
    """Send the order book for a given ticker"""
    try:
        exchange = args[0]
        ticker = args[1]

        update.message.reply_text(
            'Checking order book for `{}` in exchange `{}`'.format(
                ticker, exchange), parse_mode=telegram.ParseMode.MARKDOWN)
        checker = Checker.factory(exchange, config)
        (ed_sell_orders, ed_buy_orders) = checker.check_order_book(ticker)

        response_text = """*sell side*\n```\n{}```*buy side*\n```\n{}```""".format(Checker.get_print_table(ed_sell_orders), Checker.get_print_table(ed_buy_orders))

        update.message.reply_text(
            text=response_text,
            parse_mode=telegram.ParseMode.MARKDOWN)

    except IndexError:
        update.message.reply_text('`Usage: /check <exchange> <ticker>`', parse_mode=telegram.ParseMode.MARKDOWN)
    except ValueError as err:
        update.message.reply_text('Error retrieving orders: `{}`'.format(err.args[0]), parse_mode=telegram.ParseMode.MARKDOWN)

    ticker = update.message.text


def echo(bot, update):
    """Echo the user message."""
    update.message.reply_text(update.message.text)


def error(bot, update, error):
    """Log Errors caused by Updates."""
    logger.warning('Update "%s" caused error "%s"', update, error)


def get_parser():
    parser = argparse.ArgumentParser(description='Launch Wechat Bot.')
    parser.add_argument('-c', '--config-file', nargs='?', required=True,
                        help='config file')

    return parser.parse_args()


def main(config):
    """Start the bot."""
    telegram_bot_config = dict(config.items('telegram_bot'))
    telegram_bot_token_file = telegram_bot_config.get(
        'telegram_bot_token_file')
    token_file = open(telegram_bot_token_file, "r")
    telegram_bot_token = token_file.readline().strip()
    # Create the EventHandler and pass it your bot's token.
    updater = Updater(telegram_bot_token)

    # Get the dispatcher to register handlers
    dp = updater.dispatcher

    # on different commands - answer in Telegram
    dp.add_handler(CommandHandler("help", help))

    # on noncommand i.e message - echo the message on Telegram
    # dp.add_handler(MessageHandler(Filters.text, echo))

    # check command
    dp.add_handler(CommandHandler("check", check_order_book, pass_args=True))

    # log all errors
    dp.add_error_handler(error)

    # Start the Bot
    updater.start_polling()

    logger.info("Bot started")

    # Run the bot until you press Ctrl-C or the process receives SIGINT,
    # SIGTERM or SIGABRT. This should be used most of the time, since
    # start_polling() is non-blocking and will stop the bot gracefully.
    updater.idle()


if __name__ == "__main__":
    args = get_parser()

    # Load config
    config = configparser.ConfigParser()
    config.read(args.config_file)

    main(config)
