'''Monitoring of feemodel app.'''

import os
import re
import threading
import smtplib
import logging
import logging.handlers
import socket
from time import time, sleep
from email.mime.text import MIMEText

from feemodel.util import StoppableThread
from feemodel.config import datadir
from feemodel.app.main import logfile as applogfile

from feemodeldata.rrdcollect import RRDLOGFILE
from feemodeldata.plotdata import PLOTLOGFILE

# Period for checking for new log entries,
# and also for sending heartbeat
UPDATE_PERIOD = 5

HEARTBEAT = 'hb'
HEARTBEATPORT = 8351
HEARTBEAT_TIMEOUT = 300
TERMINATE = 'term'

smtp_lock = threading.Lock()
logger = logging.getLogger(__name__)

MONITORLOGFILE = os.path.join(datadir, 'monitor.log')

# log files to check for errors / warnings
CHECKLOGFILES = [RRDLOGFILE, PLOTLOGFILE, applogfile]


class HeartbeatNode(StoppableThread):
    '''A heartbeat node.

    Sends heartbeat to counterpart every UPDATE_PERIOD seconds.
    Listens for UDP heartbeat packets from counterpart and notifies if one has
    not been received for HEARTBEAT_TIMEOUT seconds.
    '''

    def __init__(self, counterpart_ip):
        self.counterpart = (counterpart_ip, HEARTBEATPORT)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(('', HEARTBEATPORT))
        super(HeartbeatNode, self).__init__()

    @StoppableThread.auto_restart(10)
    def run(self):
        self.start_listen()
        try:
            while not self.is_stopped():
                self.update()
                self.sleep(UPDATE_PERIOD)
        finally:
            self.stop_listen()

    def update(self):
        '''Called with UPDATE_PERIOD.'''
        self.send_heartbeat()
        self.check_counterpart_heartbeat()

    def send_heartbeat(self):
        '''Send a heartbeat packet.'''
        try:
            if self.counterpart[0]:
                self.sock.sendto(HEARTBEAT, self.counterpart)
        except Exception:
            logger.exception("Unable to send heartbeat.")

    def check_counterpart_heartbeat(self):
        '''Check the time of the most recent received heartbeat.'''
        currtime = int(time())
        # logger.debug("heartbeat interval is %d, timeout is %d" %
        #              (currtime - self.last_heartbeat, HEARTBEAT_TIMEOUT))
        if currtime - self.last_heartbeat > HEARTBEAT_TIMEOUT:
            logger.info('{} no heartbeat'.format(self.counterpart[0]))
            SendEmail(
                '{} no heartbeat'.format(self.counterpart[0]), '').start()
            self.last_heartbeat = currtime

    def listen_heartbeat(self):
        '''Listen for heartbeat.

        Continuously listen for heartbeat from counterpart and update the
        last received heartbeat time.
        '''
        logger.info(
            "Listening for heartbeat from {}:{}".format(*self.counterpart))
        while True:
            data, addr = self.sock.recvfrom(1024)
            if addr[0] == self.counterpart[0] and data == HEARTBEAT:
                logger.info("Heartbeat received.")
                self.last_heartbeat = int(time())
            elif data == TERMINATE:
                logger.info(
                    "TERMINATE received; stopped listening for heartbeat.")
                break

    def start_listen(self):
        '''Start the listening thread.'''
        self.last_heartbeat = int(time())
        self.listenthread = threading.Thread(target=self.listen_heartbeat)
        self.listenthread.start()

    def stop_listen(self):
        '''Close the listening thread.'''
        while self.listenthread.is_alive():
            self.sock.sendto(TERMINATE, ('127.0.0.1', HEARTBEATPORT))
            sleep(1)


class MonitorMonitor(HeartbeatNode):
    '''Monitors the monitor by UDP heartbeat.'''

    def __init__(self):
        try:
            monitor_ip = os.environ['FEEMODEL_MONITOR_IP']
        except KeyError:
            logger.warning("No monitor ip set.")
            monitor_ip = ''
        super(MonitorMonitor, self).__init__(monitor_ip)


class Monitor(HeartbeatNode):
    '''Monitors the app log files.

    Upon WARNING/ERROR, sends an email to RECIPIENT.
    Upon no new log entry in TIMEOUT seconds, also send an email.
    '''

    def __init__(self):
        try:
            monitormonitor_ip = os.environ['FEEMODEL_MONITORMONITOR_IP']
        except KeyError:
            logger.warning("No monitormonitor ip set.")
            monitormonitor_ip = ''
        super(Monitor, self).__init__(monitormonitor_ip)
        self.logmonitors = []

    def run(self):
        self.logmonitors = [LogMonitor(logfile) for logfile in CHECKLOGFILES]
        for logmonitor in self.logmonitors:
            logmonitor.add_pattern("WARNING", emailcallback)
            logmonitor.add_pattern("ERROR", emailcallback)
        super(Monitor, self).run()

    def update(self):
        for logmonitor in self.logmonitors:
            logmonitor.update()
        super(Monitor, self).update()


class LogMonitor(object):
    """Tracks a specific log file.

    self.update is called with period UPDATE_PERIOD. A regex search is made
    in the latest logfile lines for each user specified pattern, and the
    corresponding callback is called if there's a match.

    taillines is the number of lines to tail each time. It should be set so
    that the number of log lines in each UPDATE_PERIOD does not exceed
    taillines, otherwise some lines could be missed.
    """

    def __init__(self, filename):
        # Create the log file if it does not exist.
        if not os.path.exists(filename):
            open(filename, 'w').close()
        self.filename = filename
        self.patterns = []
        self.lastpos = self._get_filesize()

    def add_pattern(self, pattern, callback):
        """Add a regex pattern to match with latest log file lines.

        If there's a match, callback is called with
        args=(self.fileobj, line, lines).
        """
        self.patterns.append((pattern, callback))

    def update(self):
        """Called by monitor with UPDATE_PERIOD"""
        try:
            lines = self.get_latest_lines()
        except Exception:
            logger.warning("No such logfile: {}".format(self.filename))
        for pattern, callback in self.patterns:
            for line in lines:
                if re.search(pattern, line):
                    callback(pattern, line, lines, self.filename)

    def get_latest_lines(self):
        filesize = self._get_filesize()
        if filesize < self.lastpos:
            # We take it to mean that the log file was rotated.
            self.lastpos = 0
        with open(self.filename, "r") as f:
            f.seek(self.lastpos)
            lines = f.readlines()
            self.lastpos = f.tell()
        return lines

    def _get_filesize(self):
        return os.path.getsize(self.filename)


def emailcallback(pattern, line, lines, filename):
    """Send an email with the log context, when there is a match."""
    _dum, just_the_name = os.path.split(filename)
    subject = "{} in {}".format(pattern, just_the_name)
    body = ''.join(lines)
    SendEmail(subject, body).start()


class SendEmail(threading.Thread):
    '''Send a text mail with specified subject and body.'''

    def __init__(self, subject, body):
        self.subject = subject
        self.body = body
        super(SendEmail, self).__init__()

    def run(self):
        server = None
        try:
            SMTPHOST = os.environ['FEEMODEL_SMTP_HOST']
            USERNAME = os.environ['FEEMODEL_SMTP_USERNAME']
            PASSWORD = os.environ['FEEMODEL_SMTP_PASSWORD']
            RECIPIENT = os.environ['FEEMODEL_SMTP_RECIPIENT']
            with smtp_lock:
                msg = MIMEText(self.body)
                msg['Subject'] = 'feemodel - {}'.format(self.subject)
                msg['From'] = USERNAME
                msg['To'] = RECIPIENT

                server = smtplib.SMTP(SMTPHOST)
                server.starttls()
                server.login(USERNAME, PASSWORD)
                server.sendmail(USERNAME, RECIPIENT, msg.as_string())
        except KeyError:
            # Couldn't get the env vars
            logger.warning("No SMTP settings.")
            logger.info("Subject: {}".format(self.subject))
            logger.info("Body: {}".format(self.body))
        except Exception:
            logger.exception("Exception sending mail.")
        finally:
            if server is not None:
                try:
                    server.quit()
                except Exception:
                    pass


def loggercfg():
    '''Logger config.'''
    formatter = logging.Formatter(
        '%(asctime)s:%(name)s [%(levelname)s] %(message)s')
    filehandler = logging.handlers.RotatingFileHandler(
        MONITORLOGFILE, maxBytes=100000, backupCount=1)
    filehandler.setLevel(logging.DEBUG)
    filehandler.setFormatter(formatter)
    logger.setLevel(logging.DEBUG)
    logger.addHandler(filehandler)


def monitor():
    '''Run the monitor.

    Required env vars:

    FEEMODEL_SMTP_HOST
    FEEMODEL_SMTP_USERNAME
    FEEMODEL_SMTP_PASSWORD
    FEEMODEL_SMTP_RECIPIENT
    FEEMODEL_MONITORMONITOR_IP
    '''
    loggercfg()
    m = Monitor()
    m.run()


def monitormonitor():
    '''Run the monitor monitor.

    Required env vars:

    FEEMODEL_SMTP_HOST
    FEEMODEL_SMTP_USERNAME
    FEEMODEL_SMTP_PASSWORD
    FEEMODEL_SMTP_RECIPIENT
    FEEMODEL_MONITOR_IP
    '''
    loggercfg()
    m = MonitorMonitor()
    m.run()
