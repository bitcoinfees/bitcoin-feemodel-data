import os
import unittest
import logging
from time import sleep

import feemodeldata.monitor as monitor
from feemodeldata.monitor import Monitor, MonitorMonitor

logging.basicConfig(level=logging.DEBUG,
        format="%(name)s [%(levelname)s]: %(message)s")

logfile = '_tmp.log'
monitor.CHECKLOGFILES = [logfile]
monitor.TIMEOUT = 5
monitor.HEARTBEAT_TIMEOUT = 10

logger = logging.getLogger('monitor_test')
logger.setLevel(logging.DEBUG)
formatter = logging.Formatter("%(asctime)s %(name)s [%(levelname)s]: %(message)s")
handler = logging.FileHandler(logfile)
handler.setLevel(logging.DEBUG)
handler.setFormatter(formatter)
logger.addHandler(handler)

# os.environ['FEEMODEL_MONITORMONITOR_IP'] = '127.0.0.1'


class MonitorTest(unittest.TestCase):

    def test_A(self):
        '''Send notification emails.'''
        monitor = Monitor()
        with monitor.context_start():
            sleep(3)
            # Email for warning
            logger.warning('Test warning.')
            sleep(6)
            # Email for error
            logger.error('Test error.')
            # Email for no new entry
            sleep(15)
            # Email for no heartbeat

    def tearDown(self):
        if os.path.exists(logfile):
            os.remove(logfile)


class MonitorMonitorTest(unittest.TestCase):

    def test_A(self):
        mm = MonitorMonitor()
        with mm.context_start():
            sleep(15)
            # Email for no heartbeat

if __name__ == '__main__':
    unittest.main()
