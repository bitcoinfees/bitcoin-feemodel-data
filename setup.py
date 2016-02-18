from setuptools import setup, find_packages

name = 'bitcoin-feemodel-data'
version = '0.0.4'

setup(
    name=name,
    version=version,
    packages=find_packages(),
    description='feemodel data collection and presentation',
    install_requires=[
        'bitcoin-feemodel',
        'oauth2client==1.5.1',
        'gspread==0.3.0',
        'plotly',
        'click'
    ],
    entry_points={
        'console_scripts': [
            'feemodel-rrd = feemodeldata.rrdcollect:cli',
            'feemodel-monitor = feemodeldata.monitor:monitor',
            'feemodel-monitormonitor = feemodeldata.monitor:monitormonitor',
            'feemodel-plot = feemodeldata.plotting.cli:cli',
            'feemodel-tools = feemodeldata.tools.cli:cli'
        ]
    }
)
