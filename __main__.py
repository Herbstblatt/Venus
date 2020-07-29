import click

@click.group()
def venus():
    pass

@venus.command(help="Runs the logger")
def run():
    pass

@venus.command(help="Adds a new wiki")
def add_wiki():
    pass

@venus.command(help="Adds a new transport")
def add_transport():
    pass

venus()