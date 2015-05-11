from __future__ import division

import json
from datetime import datetime

import gspread
from oauth2client.client import SignedJwtAssertionCredentials

from feemodel.apiclient import client


def get_pools_table():
    pe = client.get_poolsobj()
    poolitems = sorted(pe.pools.items(),
                       key=lambda p: p[1].hashrate, reverse=True)
    totalhashrate = pe.calc_totalhashrate()

    table = [[
        name,
        pool.hashrate*1e-12,
        pool.hashrate/totalhashrate,
        pool.maxblocksize,
        pool.minfeerate,
        pool.mfrstats['abovekn'],
        pool.mfrstats['belowkn'],
        pool.mfrstats['mean'],
        pool.mfrstats['std'],
        pool.mfrstats['bias']]
        for name, pool in poolitems]

    timestamp = (datetime.utcfromtimestamp(pe.timestamp).
                 strftime("%Y/%m/%d %H:%M"))
    misc_stats = [totalhashrate*1e-12, 1 / pe.blockrate, timestamp]

    return table, misc_stats


def main(credentialsfile):
    with open(credentialsfile, "r") as f:
        json_key = json.load(f)
    scope = ['https://spreadsheets.google.com/feeds']
    credentials = SignedJwtAssertionCredentials(
        json_key['client_email'], json_key['private_key'], scope)
    gc = gspread.authorize(credentials)
    spreadsheet = gc.open("Mining Pools")
    pools_wks = spreadsheet.worksheet("Pools")

    table, misc_stats = get_pools_table()
    numrows = len(table)
    numcols = len(table[0])
    endcell = pools_wks.get_addr_int(numrows+1, numcols)
    cell_list = pools_wks.range('A2:' + endcell)
    table_list = sum(table, [])
    for cell, cellvalue in zip(cell_list, table_list):
        cell.value = cellvalue
    pools_wks.update_cells(cell_list)

    misc_wks = spreadsheet.worksheet("Misc")
    cell_list = misc_wks.range("A2:C2")
    for cell, cellvalue in zip(cell_list, misc_stats):
        cell.value = cellvalue
    misc_wks.update_cells(cell_list)
