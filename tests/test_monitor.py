import os
import unittest
import logging
import logging.handlers
from time import sleep

import feemodeldata.monitor as monitor
from feemodeldata.monitor import Monitor, MonitorMonitor

logging.basicConfig(level=logging.DEBUG,
                    format="%(name)s [%(levelname)s]: %(message)s")

logfile = '_tmp.log'
monitor.CHECKLOGFILES = [logfile]
monitor.HEARTBEAT_TIMEOUT = 10

logger = logging.getLogger('monitor_test')
logger.setLevel(logging.DEBUG)
formatter = logging.Formatter(
    "%(asctime)s %(name)s [%(levelname)s]: %(message)s")
handler = logging.handlers.RotatingFileHandler(
    logfile, maxBytes=500, backupCount=1)
handler.setLevel(logging.DEBUG)
handler.setFormatter(formatter)
logger.addHandler(handler)

# os.environ['FEEMODEL_MONITORMONITOR_IP'] = '127.0.0.1'


class MonitorTest(unittest.TestCase):

    # def setUp(self):
    #     with open(logfile, "w") as f:
    #         pass

    def test_A(self):
        '''Send notification emails.'''
        print("Starting test A - basic error tests")
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

    def test_B(self):
        '''
        Test when log file is rotated.
        '''
        print("Starting test B - detecting of new entries upon file rotation.")
        monitor = Monitor()
        with monitor.context_start():
            for i in range(30):
                logger.info("heartbeat")
                sleep(0.1)
            # Should get error email.
            logger.warning("Test warning")
            sleep(7)

    def tearDown(self):
        files = os.listdir('.')
        for filename in files:
            if filename.startswith(logfile):
                os.remove(filename)


class MonitorMonitorTest(unittest.TestCase):

    def test_A(self):
        mm = MonitorMonitor()
        with mm.context_start():
            sleep(20)
            # Email for no heartbeat

if __name__ == '__main__':
    unittest.main()
