'''Poll the feemodel API and input into RRD.'''
from __future__ import division

import os
import rrdtool
import logging
import logging.handlers
import threading
from time import time, ctime
from feemodel.config import datadir, minrelaytxfee
from feemodel.util import StoppableThread, interpolate
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
    "DS:predictscore:GAUGE:{}:0:1".format(str(3*STEP))
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
    updatestr = "{}:{}:{}:{}:{}:{}:{}:{}".format(updatetime, *args)
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
        logger.info("Starting RRD collection, next update at {}".format(
            ctime(self.next_update)))
        self.sleep_till_next()
        while not self.is_stopped():
            threading.Thread(
                target=self.update,
                args=(self.next_update,),
                name="rrdupdate"
            ).start()
            self.next_update += STEP
            self.sleep_till_next()
        for thread in threading.enumerate():
            if thread.name.startswith('rrdupdate'):
                thread.join()

    def update(self, currtime):
        measurements = []
        for conftime in [12, 20, 30, 60]:
            try:
                fee_estimate = self.apiclient.estimatefee(conftime)['feerate']
            except Exception:
                logger.exception("Error in getting conftime %d." % conftime)
                fee_estimate = -1
            measurements.append(fee_estimate)

        try:
            trans_stats = self.apiclient.get_transient()
            mempoolsize = trans_stats['mempoolsize']
            txbyterate, _dum = interpolate(
                minrelaytxfee,
                trans_stats['cap']['feerates'],
                trans_stats['cap']['tx_byterates'])
        except Exception:
            logger.exception("Error in processing transient stats.")
            mempoolsize = -1
            txbyterate = -1
        measurements.extend([mempoolsize, txbyterate])

        try:
            predictstats = self.apiclient.get_predictscores()
        except Exception:
            logger.exception("Error in getting predict scores.")
            score = -1
        else:
            num_in = sum(predictstats['num_in'])
            num_txs = sum(predictstats['num_txs'])
            score = num_in / num_txs
        measurements.append(score)
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
