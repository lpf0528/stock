#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import os.path
import sys

cpath_current = os.path.dirname(os.path.dirname(__file__))
cpath = os.path.abspath(os.path.join(cpath_current, os.pardir))
sys.path.append(cpath)

import instock.lib.database as mdb


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    logging.info(
        "database_target host=%s port=%s user=%s database=%s charset=%s",
        mdb.db_host,
        mdb.db_port,
        mdb.db_user,
        mdb.db_database,
        mdb.db_charset,
    )

    sql = """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = %s
        ORDER BY table_name
    """
    rows = mdb.executeSqlFetch(sql, (mdb.db_database,))
    if not rows:
        print("No tables found or failed to query tables.")
        return

    print(f"Tables in {mdb.db_database}:")
    for idx, row in enumerate(rows, start=1):
        print(f"{idx}. {row[0]}")


if __name__ == "__main__":
    main()
