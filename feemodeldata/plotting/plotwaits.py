from __future__ import division

import sqlite3
from bisect import bisect_left

import plotly.plotly as py
from plotly.graph_objs import Scatter, Figure, Layout, Data, YAxis, XAxis

from feemodel.util import DataSample
from feemodel.app.predict import PVALS_DBFILE

from feemodeldata.plotting.plotrrd import BASEDIR


def get_waits(dbfile=PVALS_DBFILE):
    db = None
    try:
        db = sqlite3.connect(dbfile)
        txs = db.execute("select feerate, waittime from txs").fetchall()
        blockheights = db.execute("select blockheight from txs").fetchall()
        blockheights = [tx[0] for tx in blockheights]
        return txs, min(blockheights), max(blockheights)
    finally:
        if db is not None:
            db.close()


def get_txgroups(txs, feerates=(2000, 10000, 12000, 20000, 50000)):
    """Sort the txs by feerate."""
    txs.sort()
    txfeerates, _dum = zip(*txs)
    idxs = [bisect_left(txfeerates, feerate) for feerate in feerates]
    idxs.insert(0, 0)
    print("idxs are {}.".format(idxs))
    txgroups = [txs[idxs[i]:idxs[i+1]] for i in range(len(idxs)-1)]

    return txgroups


def get_traces(txgroups):
    traces = []
    for txgroup in txgroups:
        feerates, waits = zip(*txgroup)
        minfeerate = min(feerates)
        maxfeerate = max(feerates)
        waitdata = DataSample(waits)

        percentilepts = [i / 100 for i in range(1, 99)]
        percentiles = [waitdata.get_percentile(p) for p in percentilepts]

        percentilepts.insert(0, 0)
        percentiles.insert(0, 0)

        trace = Scatter(
            x=percentiles,
            y=percentilepts,
            name="{} <= feerate <= {}".format(minfeerate, maxfeerate)
        )
        traces.append(trace)
    return traces


def plotwaits(traces, minheight, maxheight, basedir=BASEDIR):
    title = ("Empirical CDF of waittimes from blocks {}-{}".
             format(minheight, maxheight))
    data = Data(traces)
    layout = Layout(
        title=title,
        yaxis=YAxis(
            title="Empirical CDF",
            range=[0, 1]
        ),
        xaxis=XAxis(
            title="Wait time (s)",
            rangemode="tozero",
            type="log"
        ),
        hovermode="closest"
    )
    fig = Figure(data=data, layout=layout)
    basedir = basedir if basedir.endswith('/') else basedir + '/'
    filename = basedir + "waits_cdf"
    return py.plot(fig, filename=filename, auto_open=False)


def main(basedir=BASEDIR):
    txs, minheight, maxheight = get_waits(PVALS_DBFILE)
    print("Got {} txs.".format(len(txs)))
    txgroups = get_txgroups(txs)
    print("Got txgroups.")
    traces = get_traces(txgroups)
    print("Got traces.")
    url = plotwaits(traces, minheight, maxheight, basedir=basedir)
    print(url)
