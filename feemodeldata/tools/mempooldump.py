"""
Script to write mempool to disk (pickle) and subsequently load it.
Requires python-bitcoinlib > 0.5.0

Use the feemodel-tools command.
"""

import pickle
from collections import defaultdict
from bitcoin.rpc import Proxy

proxy = Proxy()


def dump(filename):
    mempool = proxy.getrawmempool(verbose=True)
    depmap = defaultdict(set)
    txs = {}
    for txid, txinfo in mempool.items():
        try:
            tx = proxy._call("getrawtransaction", txid, 0)
        except Exception as e:
            print(e)
            continue
        depends = txinfo['depends']
        txs[txid] = (tx, depends)
        for dependee in depends:
            depmap[dependee].add(txid)

    with open(filename, "wb") as f:
        pickle.dump((txs, depmap), f)


def load(filename):
    with open(filename, "rb") as f:
        txs, depmap = pickle.load(f)
    tx_nodep = [(txid, tx) for txid, (tx, depends) in txs.items()
                if not depends]
    numsent = 0
    while tx_nodep:
        txid, tx = tx_nodep.pop()
        for dependant in depmap[txid]:
            txs[dependant][1].remove(txid)
            if not txs[dependant][1]:
                tx_nodep.append((dependant, txs[dependant][0]))
        try:
            proxy._call("sendrawtransaction", tx)
        except Exception as e:
            print(e)
        numsent += 1
    assert numsent == len(txs)
