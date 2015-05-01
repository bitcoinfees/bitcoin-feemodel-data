from __future__ import division

from math import floor
from itertools import groupby
from time import sleep

import plotly.plotly as py
from plotly.graph_objs import Layout, XAxis, YAxis, Data, Scatter, Figure

from feemodel.txmempool import MemBlock
from feemodel.apiclient import client
from feemodel.util import cumsum_gen

pe = None


def calc_smallprop(blockthresh=10):
    """Tally proportion of small pools.

    Returns the proportion of pools which are small, defined as pools that
    have found less than <blocksthresh> blocks in this estimation window.
    """
    global pe

    def prop_mapfn(poolitem):
        return poolitem[1].hashrate / totalhashrate

    if pe is None:
        pe = client.get_poolsobj()
    poolitems = sorted(pe.pools.items(), key=lambda item: item[1].hashrate,
                       reverse=True)
    totalhashrate = sum([pool.hashrate for name, pool in poolitems])
    for idx, cumprop in enumerate(
            cumsum_gen(poolitems, mapfn=prop_mapfn)):
        if len(poolitems[idx][1].blocks) < blockthresh:
            break

    name, pool = poolitems[idx]
    return name, 1 - cumprop + pool.hashrate/totalhashrate


def calc_unknown_prop():
    """Calculate the proportion of unknown pools."""
    global pe
    if pe is None:
        pe = client.get_poolsobj()
    unknownhashrate = 0
    for name, pool in pe.pools.items():
        if name.endswith("_"):
            unknownhashrate += pool.hashrate
    totalhashrate = sum([pool.hashrate for pool in pe.pools.values()])
    return unknownhashrate / totalhashrate


def plot_pools(propthresh=0.95, poolname=None):
    """Plot pools blocksize vs stranding feerate.

    This is done for the top (propthresh*100)% of pools by hashrate.
    """
    global pe
    NUM_TRACES = 4
    MAX_RETRIES = 3

    def hashrate_keyfn(poolitem):
        return poolitem[1].hashrate

    def get_trace_number(height):
        return floor((height - blockrange[0]) /
                     (blockrange[1] - blockrange[0]) *
                     NUM_TRACES)

    if pe is None:
        pe = client.get_poolsobj()
    blockrange = (min(pe.blocksmetadata), max(pe.blocksmetadata)+1)

    poolitems = sorted(pe.pools.items(), key=hashrate_keyfn, reverse=True)
    totalhashrate = sum([pool.hashrate for name, pool in poolitems])

    fig_urls = []

    for idx, cumhashrate in enumerate(
            cumsum_gen(poolitems, mapfn=hashrate_keyfn)):
        name, pool = poolitems[idx]
        if poolname is not None and name != poolname:
            continue
        blockpts = []
        for block in sorted(pool.blocks, key=lambda b: b.height):
            height = block.height
            b = MemBlock.read(height)
            if not b:
                continue
            try:
                sfr = b.calc_stranding_feerate()['sfr']
            except Exception:
                continue
            blocksize = block.size
            trace_number = get_trace_number(height)
            blockpts.append(((sfr, blocksize, height), trace_number))

        traces = []
        for tracenum, tracegroup in groupby(blockpts, lambda t: t[1]):
            tracepts = [t[0] for t in tracegroup]
            x, y, heights = zip(*tracepts)
            text = map(str, heights)
            trace = Scatter(
                x=x,
                y=y,
                mode="markers",
                text=text,
                name="heights < {}".format(max(heights))
            )
            traces.append(trace)

        data = Data(traces)
        layout = Layout(
            title="Blocksize vs Stranding feerate for {}".format(name),
            xaxis=XAxis(
                title="Stranding feerate (satoshis)",
                rangemode="tozero"
            ),
            yaxis=YAxis(
                title="Blocksize (bytes)",
                range=[0, 1.1e6]
            )
        )
        fig = Figure(data=data, layout=layout)
        for i in range(MAX_RETRIES+1):
            url = None
            try:
                url = py.plot(
                    fig,
                    filename='poolblockstats/{}'.format(str(idx)+'_'+name),
                    auto_open=False)
            except Exception as e:
                print(repr(e))
                sleep(1)
            else:
                break
        if url:
            fig_urls.append(url)
        print("Completed {}, cum prop is {}.".
              format(name, cumhashrate/totalhashrate))

        if cumhashrate > propthresh*totalhashrate:
            break

    return fig_urls


if __name__ == "__main__":
    urls = plot_pools()
    print(urls)
    unknown_prop = calc_unknown_prop()
    print("The unknown proportion is {}.".format(unknown_prop))
    BLOCKTHRESH = 10
    smallname, smallprop = calc_smallprop(blockthresh=BLOCKTHRESH)
    print("The small pool thresh name is {}, and the small prop is {}.".
          format(smallname, smallprop))
