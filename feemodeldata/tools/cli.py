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


@cli.command()
@click.argument("source", type=click.STRING, required=True)
@click.argument("dest", type=click.STRING, required=True)
@click.argument("startheight", type=click.INT, required=True)
@click.argument("endheight", type=click.INT, required=True)
def memblocktransfer(source, dest, startheight, endheight):
    import sqlite3
    from feemodel.txmempool import MemBlock
    for height in range(startheight, endheight+1):
        b = MemBlock.read(height)
        if b:
            try:
                b.write(dest, float("inf"))
            except sqlite3.IntegrityError:
                click.echo("Height {} already exists in dest.".format(height))
            else:
                click.echo("Height {} written.".format(height))
        else:
            click.echo("Height {} missing.".format(height))
