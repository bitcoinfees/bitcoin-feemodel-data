import os
import unittest
from feemodeldata.monitor import SendEmail

if 'FEEMODEL_SMTP_HOST' not in os.environ:
    print("SMTP settings not set.")
    raise SystemExit


class EmailTest(unittest.TestCase):
    def test_A(self):
        t = SendEmail('test subject', 'test body')
        t.start()
        t.join()


if __name__ == '__main__':
    unittest.main()
