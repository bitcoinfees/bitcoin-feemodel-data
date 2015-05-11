'''Poll the feemodel API and input into RRD.'''
from __future__ import division

import os
import rrdtool
import threading
import logging
import logging.handlers
from time import time, ctime
from feemodel.config import datadir
from feemodel.util import StoppableThread
from feemodel.apiclient import APIClient

STEP = 60
RRDFILE = os.path.join(datadir, 'feedata.rrd')
RRDLOGFILE = os.path.join(datadir, 'rrd.log')
DATASOURCES = [
    "DS:fee12:GAUGE:{}:0:U".format(str(3*STEP)),
    "DS:fee20:GAUGE:{}:0:U".format(str(3*STEP)),
    "DS:fee30:GAUGE:{}:0:U".format(str(3*STEP)),
    "DS:fee60:GAUGE:{}:0:U".format(str(3*STEP)),
    "DS:mempoolsize:GAUGE:{}:0:U".format(str(3*STEP)),
    "DS:txbyterate:GAUGE:{}:0:U".format(str(3*STEP)),
    "DS:capacity:GAUGE:{}:0:U".format(str(3*STEP)),
    "DS:pdistance:GAUGE:{}:0:1".format(str(3*STEP))
]
RRA = [
    "RRA:AVERAGE:0.5:1:10080",  # 1 week of 1 min data
    "RRA:AVERAGE:0.5:180:8760",  # 3 years of 3 hour data
    "RRA:MIN:0.5:180:8760",
    "RRA:MAX:0.5:180:8760",
    "RRA:AVERAGE:0.5:1440:10950",  # 30 years of daily data
    "RRA:MIN:0.5:1440:10950",
    "RRA:MAX:0.5:1440:10950",
]

logger = logging.getLogger(__name__)


def create_rrd(starttime):
    '''Create the RRD.'''
    rrdtool.create(
        RRDFILE,
        '--start', str(starttime),
        '--step', str(STEP),
        '--no-overwrite',
        DATASOURCES,
        RRA
    )


def update_rrd(updatetime, *args):
    '''Update the RRD.'''
    updatestr = "{}:{}:{}:{}:{}:{}:{}:{}:{}".format(updatetime, *args)
    rrdtool.update(RRDFILE, updatestr)
    logger.info("RRD updated with {}".format(updatestr))


class RRDCollect(StoppableThread):
    '''Thread to collect model data and store in RRD.'''

    def __init__(self):
        super(RRDCollect, self).__init__()
        self.apiclient = APIClient()

    def init_rrd(self):
        timenow = int(time())
        starttime = timenow - (timenow % STEP)
        self.next_update = starttime + STEP
        if not os.path.exists(RRDFILE):
            try:
                create_rrd(starttime)
            except Exception:
                logger.exception("Unable to create RRD.")
                self.stop()

    @StoppableThread.auto_restart(3)
    def run(self):
        self.init_rrd()
        logger.info(
            "Starting RRD collection, next update at {}".
            format(ctime(self.next_update)))
        self.sleep_till_next()
        while not self.is_stopped():
            self.update_async(self.next_update)
            self.next_update += STEP
            self.sleep_till_next()

    def update_async(self, currtime):
        """Call self.update in a new thread."""
        threading.Thread(target=self._update, args=(currtime,)).start()

    def _update(self, currtime):
        measurements = []
        # Get feerate for specified confirmation / wait time
        for conftime in [12, 20, 30, 60]:
            try:
                fee_estimate = self.apiclient.estimatefee(conftime)['feerate']
            except Exception:
                logger.exception("Error in getting conftime %d." % conftime)
                fee_estimate = -1
            measurements.append(fee_estimate)

        # Get mempool size with fee (i.e. total size of txs with
        # feerate >= MINRELAYTXFEE)
        try:
            mempoolstats = self.apiclient.get_mempool()
            mempoolsize = mempoolstats['sizewithfee']
        except Exception:
            logger.exception("Exception in getting mempool stats.")
            mempoolsize = -1
        # Get tx byterate with fee
        try:
            txstats = self.apiclient.get_txrate()
            txbyterate = txstats['ratewithfee']
        except Exception:
            logger.exception("Exception in getting tx byterate.")
            txbyterate = -1
        measurements.extend([mempoolsize, txbyterate])

        # Get pools capacity
        try:
            pools_stats = self.apiclient.get_pools()
            blockinterval = pools_stats['blockinterval']
            expectedmaxblocksize = sum([
                pool['proportion']*pool['maxblocksize']
                for pool in pools_stats['pools'].values()
                if pool['minfeerate'] < float("inf")
            ])
        except Exception:
            logger.exception("Exception in getting pools stats.")
            cap = -1
        else:
            cap = expectedmaxblocksize / blockinterval
        measurements.append(cap)

        # Get the p-distance
        try:
            predictstats = self.apiclient.get_prediction()
            pdistance = predictstats['pdistance']
        except Exception:
            logger.exception("Exception in getting p-distance.")
            pdistance = -1
        measurements.append(pdistance)

        # Update the RRD!
        try:
            update_rrd(currtime, *measurements)
        except Exception:
            logger.exception("Error in updating RRD.")

    def sleep_till_next(self):
        '''Sleep till the next update time.'''
        self.sleep(max(0, self.next_update - time()))


def main():
    formatter = logging.Formatter(
        '%(asctime)s:%(name)s [%(levelname)s] %(message)s')
    filehandler = logging.handlers.RotatingFileHandler(
        RRDLOGFILE, maxBytes=1000000, backupCount=1)
    filehandler.setLevel(logging.DEBUG)
    filehandler.setFormatter(formatter)
    logger.setLevel(logging.DEBUG)
    logger.addHandler(filehandler)
    RRDCollect().run()
