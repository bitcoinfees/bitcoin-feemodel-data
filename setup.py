from setuptools import setup, find_packages

name = 'bitcoin-feemodel-data'
version = '0.0.1'

setup(
    name=name,
    version=version,
    packages=find_packages(),
    description='feemodel data collection and presentation',
    install_requires=['bitcoin-feemodel'],
    entry_points={
        'console_scripts': ['feemodel-rrd = feemodeldata.rrdcollect:main']
    }
)
