from itertools import groupby
from datetime import datetime

import plotly.plotly as py
from plotly.graph_objs import (Scatter, Figure, Layout, Data, YAxis, XAxis,
                               Line, Font)

from feemodel.util import cumsum_gen
from feemodel.apiclient import client
from feemodeldata.plotting.plotrrd import BASEDIR


def get_waitsgraph():
    stats = client.get_transient()
    feerates = stats['feepoints']
    waits = stats['expectedwaits']
    trace = Scatter(
        x=feerates,
        y=waits,
        name='Expected wait time',
        line=Line(color='red'),
        mode="lines",
        yaxis='y2'
    )
    return trace


def get_txgraph():
    stats = client.get_txrate()

    feerates = stats['cumbyterate']['feerates']
    byterates = stats['cumbyterate']['byterates']

    byterates_decaminute = [b*600 for b in byterates]
    trace = Scatter(
        x=feerates,
        y=byterates_decaminute,
        name='Cumul. tx byterate',
        mode="lines",
        line=Line(color='black', dash='dot')
    )
    return trace


def get_mempoolgraph():
    stats = client.get_mempool()

    feerates = stats['cumsize']['feerates']
    sizes = stats['cumsize']['size']

    trace = Scatter(
        x=feerates,
        y=sizes,
        name='Cumul. mempool size',
        mode="lines",
        line=Line(color='black')
    )
    return trace


def get_poolsgraph():
    stats = client.get_pools()

    pitems = sorted(stats['pools'].items(),
                    key=lambda p: p[1]['minfeerate'])

    def mfr_keyfn(poolitem):
        return poolitem[1]['minfeerate']

    def sumgroupbyterates(grouptuple):
        feerate, feegroup = grouptuple
        blockrate = 1 / stats['blockinterval']
        totalhashrate = stats['totalhashrate']
        groupbyterate = sum([
            pool['hashrate']*pool['maxblocksize']
            for name, pool in feegroup]) * blockrate / totalhashrate
        return (feerate, groupbyterate)

    pitems = filter(lambda pitem: pitem[1]['minfeerate'] < float("inf"),
                    pitems)
    byterate_by_fee = map(sumgroupbyterates, groupby(pitems, mfr_keyfn))
    feerates, byterates = zip(*byterate_by_fee)
    feerates = [0] + list(feerates)
    byterates = [0] + list(byterates)
    cumbyterates = list(cumsum_gen(byterates))

    cumbyterates_decaminute = [b*600 for b in cumbyterates]
    trace = Scatter(
        x=feerates,
        y=cumbyterates_decaminute,
        name="Cumul. capacity byterate",
        mode="lines",
        line=Line(color='black', dash='dash', shape='hv')
    )
    return trace


def _filter_xaxis(trace, xthresh):
    pts = zip(trace['x'], trace['y'])
    pts = filter(lambda pt: pt[0] <= xthresh, pts)
    trace['x'], trace['y'] = map(list, zip(*pts))
    return trace


def main(basedir=BASEDIR):
    waitsgraph = get_waitsgraph()
    maxfeerate = max(waitsgraph['x'])
    mempoolgraph = _filter_xaxis(get_mempoolgraph(), maxfeerate)
    txgraph = _filter_xaxis(get_txgraph(), maxfeerate)

    poolsgraph = _filter_xaxis(get_poolsgraph(), maxfeerate)
    poolsgraph['x'].append(maxfeerate)
    poolsgraph['y'].append(poolsgraph['y'][-1])

    data = Data([
        waitsgraph,
        mempoolgraph,
        txgraph,
        poolsgraph
    ])
    timestr = datetime.utcnow().ctime() + " UTC"
    layout = Layout(
        title="Queue profile at {}".format(timestr),
        hovermode='closest',
        xaxis=XAxis(
            title="Feerate (satoshis per kB)",
            rangemode="tozero"
        ),
        yaxis=YAxis(
            title="Bytes or<br>Bytes per decaminute",
            rangemode="tozero"
        ),
        yaxis2=YAxis(
            title="Expected wait (s)",
            overlaying='y',
            side='right',
            rangemode="tozero",
            titlefont=Font(color='red'),
            tickfont=Font(color='red')
        ),
        legend={'x': 1.1, 'y': 1}
    )
    fig = Figure(data=data, layout=layout)
    basedir = basedir if basedir.endswith('/') else basedir + '/'
    filename = basedir + "profile"
    print py.plot(fig, filename=filename)
