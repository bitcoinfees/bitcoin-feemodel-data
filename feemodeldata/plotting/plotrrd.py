'''Plot the RRD data and also maybe some others.'''
from __future__ import division

from time import time
from datetime import datetime

import rrdtool
import plotly.plotly as py
from plotly.graph_objs import (YAxis, XAxis, Scatter, Data, Layout,
                               Line, Figure)

from feemodeldata.util import retry
from feemodeldata.rrdcollect import RRDFILE
from feemodeldata.plotting import logger

BASEDIR = 'feemodel_RRD'
RRDGRAPH_SCHEMA = [
    (60, 180, '1m'),  # Every minute, for 3 hours.
    (1800, 60, '30m'),  # Every 30 minutes, for 1.25 days.
    (10800, 56, '3h'),  # Every 3 hours, for a week.
    (86400, 180, '1d'),  # Daily, for ~ half a year.
]

LAYOUT = Layout(
    title=('Required fee rate for given average wait time'),
    yaxis=YAxis(
        title='Fee rate<br>(satoshis per kB)',
        domain=[0.55, 1],
        rangemode='tozero',
    ),
    yaxis2=YAxis(
        title='Bytes or<br>Bytes per decaminute',
        domain=[0, 0.45],
        rangemode='tozero',
    ),
    xaxis2=XAxis(anchor='y2', title='Time (UTC)'),
)


# #@retry(wait=1, maxtimes=3, logger=logger)
# #def plotlatest(res, basedir=BASEDIR):
# #    '''Plot the latest data from a resolution level.
# #
# #    res is an element of RRDGRAPH_SCHEMA.
# #    '''
# #    basedir = basedir if basedir.endswith('/') else basedir + '/'
# #    try:
# #        rrdplot(starttime, endtime, interval, filename=basedir+filename)
# #    except Exception as e:
# #        logger.exception("Exception in plotting {}.".format(filename))
# #        raise e
# #    else:
# #        logger.info("Plotted {}".format(res))

def plot_latest(resnumber, basedir=BASEDIR):
    _dum0, _dum1, filename = RRDGRAPH_SCHEMA[resnumber]
    rrdplot(*get_latest_datapoints(resnumber), filename=basedir+filename)


def plot_custom(starttime, endtime, interval,
                cf="AVERAGE", filename="testing/customrrd"):
    rrdplot(*get_datapoints(starttime, endtime, interval, cf=cf),
            filename=filename)


def get_latest_datapoints(resnumber, cf='AVERAGE'):
    interval, numpoints, filename = RRDGRAPH_SCHEMA[resnumber]
    endtime = int(time()) // interval * interval
    starttime = endtime - interval*numpoints
    return get_datapoints(starttime, endtime, interval, cf)


def get_datapoints(starttime, endtime, interval, cf='AVERAGE'):
    timerange, datasources, datapoints = rrdtool.fetch(
        RRDFILE,
        cf,
        '--resolution', str(interval),
        '--start', str(starttime),
        '--end', str(endtime)
    )
    datastart, dataend, datainterval = timerange
    # Select all but the pdistance.
    tracesdata = zip(*datapoints)[:-1]
    times = range(datastart+datainterval, dataend+datainterval, datainterval)
    if datainterval != interval:
        q, r = divmod(interval, datainterval)
        assert not r
        times = downsample(times, q, last)
        tracesdata = map(
            lambda datatrace: downsample(datatrace, q, average), tracesdata)
    # Convert bytes/sec to bytes/decaminute.
    tracesdata[5] = map(lambda rate: rate*600 if rate else None, tracesdata[5])
    tracesdata[6] = map(lambda rate: rate*600 if rate else None, tracesdata[6])
    return times, tracesdata


@retry(wait=1, maxtimes=3, logger=logger)
def rrdplot(times, tracesdata, filename='test'):
    '''Plot based on specified time range.

    starttime/endtime is unix time, interval is the point spacing in seconds.
    '''

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
    traces[6].update(dict(
        name='Capacity byterate',
        xaxis='x2',
        yaxis='y2',
        line=Line(color='black', dash='dash')
    ))
    data = Data(traces)
    fig = Figure(data=data, layout=LAYOUT)
    py.plot(fig, filename=filename, auto_open=False)


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
