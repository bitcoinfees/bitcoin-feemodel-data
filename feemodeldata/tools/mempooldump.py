from bitcoin.core import CTransaction
from feemodel.util import proxy, save_obj, load_obj


def dump(filename):
    mempool_txids = proxy.getrawmempool()
    txs = [proxy.getrawtransaction(txid).serialize() for txid in mempool_txids]
    save_obj(txs, filename)
    print("{} txs dumped.".format(len(txs)))


def load(filename):
    txs = load_obj(filename)
    numloaded = 0
    numpresent = 0
    mempool_txids = proxy.getrawmempool()
    for txser in txs:
        tx = CTransaction.deserialize(txser)
        if tx.GetHash() in mempool_txids:
            numpresent += 1
            continue
        try:
            proxy.sendrawtransaction(CTransaction.deserialize(tx))
        except Exception as e:
            print(e)
        else:
            numloaded += 1

    print("{} txs loaded, {} already present.".format(numloaded, numpresent))
