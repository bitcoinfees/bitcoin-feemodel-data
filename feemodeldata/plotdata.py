'''Plot the RRD data and also maybe some others.'''
from __future__ import division

import logging
from time import time
from datetime import datetime

import rrdtool
import plotly.plotly as py
from plotly.graph_objs import (YAxis, XAxis, Scatter, Data, Layout,
                               Line, Figure)

from feemodeldata.rrdcollect import RRDFILE

BASEDIR = 'feemodel_RRD/'
RRDGRAPH_SCHEMA = [
    (60, 180, '1m'),  # Every minute, for 3 hours.
    (1800, 60, '30m'),  # Every 30 minutes, for 1.25 days.
    (10800, 56, '3h'),  # Every 3 hours, for a week.
    (86400, 180, '1d'),  # Daily, for ~ half a year.
]

LAYOUT = Layout(
    title=('Required fee rate for given average confirmation time'),
    yaxis=YAxis(
        title='Fee rate (satoshis per kB)',
        domain=[0.55, 1],
        rangemode='tozero',
    ),
    yaxis2=YAxis(
        title='Bytes per decaminute or bytes',
        domain=[0, 0.45],
        rangemode='tozero',
    ),
    xaxis=XAxis(title='Time (UTC)'),
    xaxis2=XAxis(anchor='y2', title='Time (UTC)'),
)

logger = logging.getLogger(__name__)


def rrdplot(res):
    '''Plot the latest data from a resolution level.

    res is an element of RRDGRAPH_SCHEMA.
    '''
    interval, numpoints, filename = res
    endtime = int(time()) // interval * interval
    starttime = endtime - interval*numpoints
    timerange, datasources, datapoints = rrdtool.fetch(
        RRDFILE,
        'AVERAGE',
        '--resolution', str(interval),
        '--start', str(starttime),
        '--end', str(endtime)
    )

    datastart, dataend, datainterval = timerange
    tracesdata = zip(*datapoints)[:-1]
    times = range(datastart+datainterval, dataend+datainterval, datainterval)
    if datainterval != interval:
        q, r = divmod(interval, datainterval)
        assert not r
        times = downsample(times, q, last)
        tracesdata = map(
            lambda datatrace: downsample(datatrace, q, average), tracesdata)

    x = [datetime.utcfromtimestamp(t) for t in times]
    traces = [Scatter(x=x, y=tracedata) for tracedata in tracesdata]
    names = ['12 min', '20 min', '30 min', '60 min']
    for i, name in enumerate(names):
        traces[i].update(dict(name=name))
    traces[4].update(dict(
        name='Mempool size',
        xaxis='x2',
        yaxis='y2',
        line=Line(color='black')
    ))
    traces[5].update(dict(
        name='Tx byterate',
        xaxis='x2',
        yaxis='y2',
        line=Line(color='black', dash='dot')
    ))
    # Convert bytes/sec to bytes/decaminute.
    traces[5].update(
        dict(y=[rate*600 if rate else None for rate in tracesdata[5]]))
    data = Data(traces)
    fig = Figure(data=data, layout=LAYOUT)
    try:
        py.plot(fig, filename=BASEDIR+filename)
    except Exception:
        logger.exception("Exception in plotting.")


def downsample(data, n, cf):
    '''Downsample data by factor of n with consolidation function cf.'''
    datadown = [data[i*n:(i+1)*n] for i in range(len(data)//n)]
    return map(cf, datadown)


def average(data):
    '''Consolidation function which uses the mean.'''
    datatrue = [d for d in data if d is not None]
    if len(datatrue) / len(data) < 0.5:
        return None
    else:
        return sum(datatrue) / len(datatrue)


def last(data):
    '''Consolidation function which takes the last point.'''
    for d in reversed(data):
        if d is not None:
            return d
    return None
