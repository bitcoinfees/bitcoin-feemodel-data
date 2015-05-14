import click


@click.group()
def cli():
    pass


@cli.command()
@click.argument("filename", type=click.STRING, required=True)
def mempooldump(filename):
    from feemodeldata.tools.mempooldump import dump
    dump(filename)


@cli.command()
@click.argument("filename", type=click.STRING, required=True)
def mempoolload(filename):
    from feemodeldata.tools.mempooldump import load
    load(filename)
