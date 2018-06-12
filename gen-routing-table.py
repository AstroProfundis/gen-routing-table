#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Generate OSPF routing table configuration for bird

import argparse
import base64
import datetime
import json
import os
import re

from aggregate6 import aggregate
try:
    # For Python 2
    import urllib2 as urlreq
    from urllib2 import HTTPError, URLError
except ImportError:
    # For Python 3
    import urllib.request as urlreq
    from urllib.error import HTTPError, URLError

# the url of raw data
ip_list_url = 'https://ftp.apnic.net/apnic/stats/apnic/delegated-apnic-latest'
as_list_url = 'ftp://ftp.arin.net/info/asn.txt'
ip_list_file = 'data/delegated-apnic-latest'
as_list_file = 'data/asn.txt'
routes_file = 'data/oix-full-snapshot-latest.dat'
# match IP address format
ip_pattern = re.compile(r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b')

# paths for files
outfile = 'data/ospf.conf'

def read_file(filename):
    data = None
    with open(filename, 'r') as f:
        data = f.read()
    f.close()
    return data

def write_file(filename, data=None):
    if not data:
        return
    with open(filename, 'w') as f:
        try:
            f.write(str(data, 'utf-8'))
        except TypeError:
            f.write(data)
    f.close()

def read_url(url):
    if not url or url == '':
        return
    try:
        response = urlreq.urlopen(url)
        return response.read().decode('utf-8')
    except HTTPError as err:
        return err.read()
    except URLError as err:
        return None

def parse_opts():
    parser = argparse.ArgumentParser(description='Generate OSPF routing table for bird.')
    parser.add_argument('--name', action='append', default=None,
                        help="Name of AS region, partially matched in AS description.")
    parser.add_argument('--asn', action='append', default=None,
                        help='AS Number to include, only the numeric part needed.')
    parser.add_argument('--country', action='append', default=None,
                        help='Country code, to include a whole country/region\'s network')
    parser.add_argument('--gateway', action='store', default=None,
                        help='Default gateway of internet access.')
    return parser.parse_args()

def get_ip_data():
    result = {}
    #raw_ip = read_url(ip_list_url)
    raw_ip = read_file(ip_list_file)
    for line in raw_ip.split('\n'):
        if not line or not str.startswith(line, 'apnic'):
            continue
        _tmp = line.split('|')
        if _tmp[1] == '*' or _tmp[3] == '*':
            continue
        _code = _tmp[1] # country code
        _type = _tmp[2] # record type
        if _type != 'asn':
            # skip ip blocks, as we don't need them now, but the looking table
            # structure is keeped in case we'll use it in the future
            continue
        try:
            result[_type][_code].append(_tmp[3:])
        except KeyError:
            try:
                result[_type][_code] = [_tmp[3:]]
            except KeyError:
                result[_type] = {_code: [_tmp[3:]]}
    return result

def get_as_data():
    result = {}
    #raw_as = read_url(as_list_url)
    raw_as = read_file(as_list_file)
    for line in raw_as.split('\n'):
        if not line:
            continue
        _tmp = line.split()
        # not starting with an ASN
        if not _tmp[0].isdigit():
            continue
        asn = _tmp[0]      # AS Number
        name = _tmp[1]     # AS Name
        try:
            result[name].append(asn)
        except KeyError:
            result[name] = [asn]
    return result

def group_networks(net_set):
    return aggregate(list(net_set))

def read_routing_table(as_list):
    result = {}
    with open(routes_file, 'r') as f:
        for tuple_line in enumerate(f):
            line = tuple_line[1]
            if not line or not str.startswith(line, '*'):
                continue

            _tmp = line.split()
            inet = _tmp[1]
            # filter out default route
            if inet == '0.0.0.0/0':
                continue
            if _tmp[-1] == 'i' or _tmp[-1] == 'r' or _tmp[-1] == 'S':
                asn = _tmp[-2]
            else:
                asn = _tmp[-1]
            # filter by AS Numbers
            if asn not in as_list:
                continue
            try:
                # store every network only one time
                result[asn].add(inet)
            except KeyError:
                result[asn] = set()
                result[asn].add(inet)
    for asn, nets in result.items():
        result[asn] = group_networks(nets)
    return result

def find_asn_by_name(name_list):
    result = []
    as_data = get_as_data()
    for as_name, as_info in as_data.items():
        for name in name_list:
            if str.upper(name) in str.upper(as_name):
                result += as_info
    return result

def find_asn_by_country(country_list):
    result = []
    ip_data = get_ip_data()
    for ccode, as_info in ip_data['asn'].items():
        for code in country_list:
            if str.upper(code) in str.upper(ccode):
                for as_item in as_info:
                    result.append(as_item[0])
    return result


def gen_routing_items(args):
    as_name = args.name
    as_num = args.asn
    country = args.country


if __name__ == '__main__':
    args = parse_opts()
    as_list = []

    if args.name:
        as_list += find_asn_by_name(args.name)
    if args.country:
        as_list += find_asn_by_country(args.country)
    # remove duplicates
    as_list = list(set(as_list))

    for asn, nets in read_routing_table(as_list).items():
        for net in nets:
            print(net)