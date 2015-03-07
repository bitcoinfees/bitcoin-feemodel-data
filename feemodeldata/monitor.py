'''Monitoring of feemodel app.'''

import os
import threading
import smtplib
import logging
import logging.handlers
import socket
from time import time, sleep
from email.mime.text import MIMEText

from feemodel.util import StoppableThread
from feemodel.config import applogfile, datadir

from feemodeldata.rrdcollect import RRDLOGFILE

# Period for checking for new log entries,
# and also for sending heartbeat
UPDATE_PERIOD = 5

TIMEOUT = 300  # Notify if no new log entry for TIMEOUT seconds
CHECKLOGFILES = [RRDLOGFILE, applogfile]

HEARTBEAT = 'hb'
HEARTBEATPORT = 8351
HEARTBEAT_TIMEOUT = 300
TERMINATE = 'term'

smtp_lock = threading.Lock()
logger = logging.getLogger(__name__)

MONITORLOGFILE = os.path.join(datadir, 'monitor.log')


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
            SendErrorEmail(
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

    def run(self):
        try:
            self.logmonitors = [
                LogMonitor(open(filename, 'r')) for filename in CHECKLOGFILES]
            super(Monitor, self).run()
        finally:
            for logmonitor in self.logmonitors:
                logmonitor.file_obj.close()

    def update(self):
        for logmonitor in self.logmonitors:
            logmonitor.update()
        super(Monitor, self).update()


class LogMonitor(object):
    '''Tracks a specific log file.'''

    def __init__(self, file_obj):
        self.file_obj = file_obj
        self.file_obj.seek(0, 2)
        self.lastnewentrytime = int(time())

    def update(self):
        '''Called by monitor with UPDATE_PERIOD'''
        currtime = int(time())
        lines = get_latest_lines(self.file_obj)
        if lines:
            # logger.debug("Lines is: {}".format(lines))
            self.lastnewentrytime = currtime
            self.check_errors(lines)
        else:
            self.check_newentries(currtime)

    def check_newentries(self, currtime):
        '''Check for new log entries.

        Check to see if any new log entries have been written in the past
        TIMEOUT seconds. If not, send notification email.
        '''
        if currtime - self.lastnewentrytime > TIMEOUT:
            SendErrorEmail(
                'no new log entries in {}'.format(self.file_obj.name),
                '').start()
            logger.info("No new entries in {}.".format(self.file_obj.name))
            self.lastnewentrytime = currtime

    def check_errors(self, lines):
        '''Check for WARNING/ERROR log entries.

        If so, send notification email.
        '''
        if '[WARNING]' in lines or '[ERROR]' in lines:
            SendErrorEmail(
                'WARNING/ERROR in {}'.format(self.file_obj.name),
                lines).start()
            logger.info("WARNING/ERROR in {}".format(self.file_obj.name))


class SendErrorEmail(threading.Thread):
    '''Send the error notification email.'''

    def __init__(self, subject, body):
        self.subject = subject
        self.body = body
        super(SendErrorEmail, self).__init__()

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


def get_latest_lines(fileobj):
    '''Get latest lines from a file.'''
    lines = ''
    line = fileobj.readline()
    while line:
        lines += line
        line = fileobj.readline()
    return lines


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
