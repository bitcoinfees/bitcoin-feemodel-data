import plotly.plotly as py
from plotly.graph_objs import (Scatter, Figure, Layout, Data, YAxis, XAxis,
                               Line)

from feemodel.app.predict import Prediction

from feemodeldata.plotting import logger
from feemodeldata.plotting.plotrrd import BASEDIR
from feemodeldata.util import retry

# FEERATES = [1000, 2000, 10000, 12000, 20000, 50000]
FEERATES = [
    (1000, 9999),
    (10000, 50000)
]


def get_feerate_trace(minfeerate, maxfeerate):
    pred = Prediction.from_db(
        1008, "feerate >= {} and feerate <= {}".format(minfeerate, maxfeerate))
    x, y = map(list, zip(*pred.pval_ecdf))
    x.insert(0, 0)
    y.insert(0, 0)
    trace = Scatter(
        x=x,
        y=y,
        name="{} <= feerate <= {}".format(minfeerate, maxfeerate),
        mode="lines"
    )
    return trace


def get_model_trace():
    trace = Scatter(
        x=[0, 1],
        y=[0, 1],
        name="Model",
        mode="lines",
        line=Line(color="black", dash="dot")
    )
    return trace


@retry(wait=1, maxtimes=3, logger=logger)
def plot_with_retry(fig, filename):
    print(py.plot(fig, filename=filename))


def main(basedir=BASEDIR):
    heights = Prediction.get_heights()
    minheight = min(heights)
    maxheight = max(heights)
    traces = [
        get_feerate_trace(minfeerate, maxfeerate)
        for minfeerate, maxfeerate in FEERATES
    ]
    traces.append(get_model_trace())
    layout = Layout(
        title=("Empirical CDF of wait time p-values from blocks {}-{}".
               format(minheight, maxheight)),
        yaxis=YAxis(
            title='Empirical CDF',
            range=[0, 1]
        ),
        xaxis=XAxis(
            title='p-value',
            range=[0, 1]
        ),
        hovermode="compare"
    )
    data = Data(traces)
    fig = Figure(data=data, layout=layout)
    basedir = basedir if basedir.endswith('/') else basedir + '/'
    filename = basedir + "pvals"
    plot_with_retry(fig, filename)
