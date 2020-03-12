import os
import logging

def StringToDict(str):
    d: dict = {}

    if ';' in str:
        for i in str.split(';'):
            key, value = i.split('=')
            d[key] = value

    if len(d) > 0:
        logging.debug(d)

    return d


def is_owner(ctx):
    return ctx.message.author.id == int(os.environ['OWNER_ID'])


def is_mod(ctx):
    return ctx.message.author.is_mod == 1
