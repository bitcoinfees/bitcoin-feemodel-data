import os
import logging
import logging.handlers
from feemodel.config import datadir

PLOTLOGFILE = os.path.join(datadir, 'plotting.log')

logger = logging.getLogger(__name__)
formatter = logging.Formatter(
    '%(asctime)s:%(name)s [%(levelname)s] %(message)s')
filehandler = logging.handlers.RotatingFileHandler(
    PLOTLOGFILE, maxBytes=1000000, backupCount=1)
filehandler.setLevel(logging.DEBUG)
filehandler.setFormatter(formatter)
logger.setLevel(logging.DEBUG)
logger.addHandler(filehandler)
