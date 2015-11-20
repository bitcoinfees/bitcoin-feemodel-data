from __future__ import division

import json
import sys
from datetime import datetime

import gspread
from oauth2client.client import SignedJwtAssertionCredentials

SPREADSHEET = "feemodeldata"


def push_timestr(worksheet):
    timestr = datetime.utcnow().ctime() + " UTC"
    table_cols = [[timestr]]
    pushtable(worksheet, table_cols)


def get_credentials(credentialsfile):
    with open(credentialsfile, "r") as f:
        json_key = json.load(f)
    scope = ['https://spreadsheets.google.com/feeds']
    credentials = SignedJwtAssertionCredentials(
        json_key['client_email'], json_key['private_key'], scope)
    return credentials


def get_spreadsheet(credentialsfile):
    gc = gspread.authorize(get_credentials(credentialsfile))
    return gc.open(SPREADSHEET)


def pushrrd(credentialsfile, resnumber):
    from feemodeldata.plotting.plotrrd import get_latest_datapoints as getdata
    spreadsheet = get_spreadsheet(credentialsfile)
    WORKSHEETNAMES = ["1m", "30m", "3h", "1d"]
    worksheet = spreadsheet.worksheet(WORKSHEETNAMES[resnumber])
    t, data = getdata(resnumber)
    assert len(t) == len(data[0])
    data.insert(0, t)
    pushtable(worksheet, data)


def pushprofile(credentialsfile):
    import feemodeldata.plotting.plotprofile as profile
    spreadsheet = get_spreadsheet(credentialsfile)

    for graphtype in ['waits', 'mempool', 'tx', 'pools']:
        worksheet = spreadsheet.worksheet("profile_{}".format(graphtype))
        funcname = "get_{}graph".format(graphtype)
        trace = getattr(profile, funcname)()
        table_cols = [trace['x'], trace['y']]
        pushtable(worksheet, table_cols)

    worksheet = spreadsheet.worksheet("profile_updatetime")
    push_timestr(worksheet)


def pushmining(credentialsfile):
    from feemodeldata.plotting.plotpools import get_data
    from bisect import bisect
    data = get_data()
    spreadsheet = get_spreadsheet(credentialsfile)

    worksheet = spreadsheet.worksheet("mining_mfr")
    mfr, mfr_p = data[:2]
    idx95 = bisect(mfr_p, 0.99)
    table_cols = [mfr[:idx95], mfr_p[:idx95]]
    pushtable(worksheet, table_cols)

    worksheet = spreadsheet.worksheet("mining_mbs")
    table_cols = data[2:]
    pushtable(worksheet, table_cols)

    worksheet = spreadsheet.worksheet("mining_updatetime")
    push_timestr(worksheet)


def pushpvals(credentialsfile):
    from feemodel.apiclient import client
    p = client.get_prediction()['pval_ecdf']
    spreadsheet = get_spreadsheet(credentialsfile)
    worksheet = spreadsheet.worksheet("pvals")
    pushtable(worksheet, p)

    worksheet = spreadsheet.worksheet("pvals_updatetime")
    push_timestr(worksheet)


def pushtable(worksheet, table_cols):
    numcols = len(table_cols)
    numrows = len(table_cols[0])
    worksheet.resize(rows=numrows+1)
    endcell = worksheet.get_addr_int(numrows+1, numcols)
    cell_list = worksheet.range('A2:' + endcell)
    table_list = [col[i] for i in range(numrows) for col in table_cols]
    for cell, cellvalue in zip(cell_list, table_list):
        cell.value = cellvalue
    worksheet.update_cells(cell_list)


if __name__ == "__main__":
    # For testing only.
    credentialsfile = sys.argv[1]
    # pushrrd(sys.argv[1], 3)
    # pushmining(credentialsfile)
    pushpvals(credentialsfile)
