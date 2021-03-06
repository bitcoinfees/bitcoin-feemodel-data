from __future__ import division

from datetime import datetime

import plotly.plotly as py
from plotly.graph_objs import (Scatter, Figure, Layout, Data, YAxis, XAxis,
                               Line)

from feemodel.apiclient import client

from feemodeldata.plotting import logger
from feemodeldata.plotting.plotrrd import BASEDIR
from feemodeldata.util import retry


@retry(wait=1, maxtimes=3, logger=logger)
def plot_with_retry(fig, filename):
    print(py.plot(fig, filename=filename, auto_open=False))


def get_data():
    pe = client.get_poolsobj()
    maxblocksizes = sorted(pe.maxblocksizes)
    minfeerates = sorted(pe.minfeerates)
    numfeerates = len(minfeerates)
    minfeerates = filter(lambda f: f < float("inf"), minfeerates)

    return [
        minfeerates, [i/numfeerates for i in range(1, len(minfeerates)+1)],
        maxblocksizes, [i/len(maxblocksizes)
                        for i in range(1, len(maxblocksizes)+1)]]


def main(basedir=BASEDIR):
    basedir = basedir if basedir.endswith('/') else basedir + '/'
    timestr = datetime.utcnow().ctime() + " UTC"

    mfr, mfr_p, mbs, mbs_p = get_data()

    # Plot minfeerates
    trace = Scatter(
        x=mfr,
        y=mfr_p,
        line=Line(color='black', shape='hv')
    )
    layout = Layout(
        title="Min fee rate distribution at {}".format(timestr),
        hovermode='closest',
        xaxis=XAxis(title="Fee rate (satoshis/kB)", rangemode="tozero"),
        yaxis=YAxis(title="Cumulative proportion", range=[0, 1])
    )
    fig = Figure(data=Data([trace]), layout=layout)
    filename = basedir + "pools_mfr"
    plot_with_retry(fig, filename)

    # Plot maxblocksizes
    trace = Scatter(
        x=mbs,
        y=mbs_p,
        line=Line(color='black', shape='hv')
    )
    layout = Layout(
        title="Max block size distribution at {}".format(timestr),
        hovermode='closest',
        xaxis=XAxis(title="Block size (bytes)", rangemode="tozero"),
        yaxis=YAxis(title="Cumulative proportion", range=[0, 1])
    )
    fig = Figure(data=Data([trace]), layout=layout)
    filename = basedir + "pools_mbs"
    plot_with_retry(fig, filename)
