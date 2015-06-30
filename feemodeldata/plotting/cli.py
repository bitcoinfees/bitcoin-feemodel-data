import click
from feemodeldata.plotting.plotrrd import BASEDIR


@click.group()
def cli():
    pass


@cli.command()
@click.option("--basedir", "-d", type=click.STRING, default=BASEDIR)
@click.argument("resnumber", type=click.INT, required=True)
def rrd(resnumber, basedir):
    if resnumber not in [0, 1, 2, 3]:
        click.echo("resnumber needs to be in [0, 1, 2, 3].")
        return
    from feemodeldata.plotting import logger
    from feemodeldata.plotting.plotrrd import main
    try:
        main(resnumber, basedir=basedir)
    except Exception:
        logger.exception("Exception in plotting rrd.")


@cli.command()
@click.option("--cf", "-c",
              type=click.Choice(['AVERAGE', 'MIN', 'MAX']),
              default="AVERAGE")
@click.option("--interval", "-i", type=click.INT, default=60)
@click.option("--filename", "-f",
              type=click.STRING,
              default="testing/customrrd")
@click.argument("starttime", type=click.STRING, required=True)
@click.argument("endtime", type=click.STRING, required=True)
def rrdcustom(starttime, endtime, interval, cf, filename):
    """datetime format is %Y/%m/%d %H:%M"""
    from datetime import datetime
    from feemodeldata.util import utc_to_timestamp
    from feemodeldata.plotting.plotrrd import rrdplot

    date_fmt = "%Y/%m/%d %H:%M"
    start_dt = datetime.strptime(starttime, date_fmt)
    end_dt = datetime.strptime(endtime, date_fmt)
    start_timestamp = utc_to_timestamp(start_dt)
    end_timestamp = utc_to_timestamp(end_dt)
    rrdplot(start_timestamp, end_timestamp, interval, cf=cf, filename=filename)


@cli.command()
@click.option("--basedir", "-d", type=click.STRING, default=BASEDIR)
def waitcdf(basedir):
    from feemodeldata.plotting.plotwaits import main
    main(basedir=basedir)


@cli.command()
@click.option("--basedir", "-d", type=click.STRING, default=BASEDIR)
def profile(basedir):
    from feemodeldata.plotting import logger
    from feemodeldata.plotting.plotprofile import main
    try:
        main(basedir=basedir)
    except Exception:
        logger.exception("Exception in plotting profile.")
    else:
        logger.info("Profile plotted.")


@cli.command()
@click.option("--basedir", "-d", type=click.STRING, default=BASEDIR)
def pvals(basedir):
    from feemodeldata.plotting import logger
    from feemodeldata.plotting.plotpvals import main
    try:
        main(basedir=basedir)
    except Exception:
        logger.exception("Exception in plotting pvals.")
    else:
        logger.info("pvals plotted.")


@cli.command()
@click.option("--basedir", "-d", type=click.STRING, default=BASEDIR)
def pools(basedir):
    from feemodeldata.plotting import logger
    from feemodeldata.plotting.plotpools import main
    try:
        main(basedir=basedir)
    except Exception:
        logger.exception("Exception in plotting pools.")
    else:
        logger.info("Pools plotted.")

# @cli.command()
# @click.argument("credentialsfile", type=click.STRING, required=True)
# def poolstable(credentialsfile):
#     from feemodeldata.plotting import logger
#     from feemodeldata.plotting.plotpools import main
#     try:
#         main(credentialsfile)
#     except Exception:
#         logger.exception("Exception in tabulating pools.")
#     else:
#         logger.info("Pools tabulated.")
