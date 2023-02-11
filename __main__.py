import logging

import click

from core.client import Venus

@click.group()
def venus():
    pass

@venus.command(help="Runs the logger")
def run():
    client = Venus(log_level=logging.DEBUG)
    client.run()

@venus.command(help="Adds a new wiki")
def add_wiki():
    pass

@venus.command(help="Adds a new transport")
def add_transport():
    pass

venus()