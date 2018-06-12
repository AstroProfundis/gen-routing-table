#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Generate OSPF routing table configuration for bird

import argparse
import datetime
import os

from subprocess import Popen, PIPE
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
    parser.add_argument('--exclude', action='append', default=None,
                        help='Country code to exclude from result, this will overwite other filters.')
    parser.add_argument('--gateway', action='store', default=None,
                        help='Default gateway of internet access.')
    parser.add_argument('--table-name', action='store', default='generated_table',
                        help='Routing table name of generated routes.')
    parser.add_argument('-o', '--output', action='store', default='routes.conf',
                        help='Output file name of generated config.')
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

def read_routing_table(as_list):
    result = {}
    with open(routes_file, 'r') as f:
        # read line by line as this file is very large
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
    f.close()
    return result

def find_asn_by_name(name_list):
    result = []
    as_data = get_as_data()
    for as_name, as_info in as_data.items():
        for name in name_list:
            if str.upper(name) in str.upper(as_name):
                result += as_info
    return result

def find_asn_by_country(country_list, exclude_list):
    result = []
    exclude = []
    ip_data = get_ip_data()

    if not country_list:
        country_list = []
    if not exclude_list:
        exclude_list = []

    for code, as_info in ip_data['asn'].items():
        for _code in exclude_list:
            if str.upper(_code) in str.upper(code):
                for as_item in as_info:
                    exclude.append(as_item[0])
        for _code in country_list:
            if str.upper(_code) in str.upper(code):
                for as_item in as_info:
                    result.append(as_item[0])
    return result, exclude


def gen_routing_items(args, net_list):
    table_name = args.table_name
    if args.gateway:
        gateway = args.gateway
    else:
        raise OSError('No default gateway specified!')
    config_template = '''# Generated at: %s
protocol static {
  table %s;
%s
}
'''
    route_template = '  route %s via %s;'

    route_list = []
    for net in net_list:
        route_list.append(route_template % (net, gateway))
    return config_template % (datetime.datetime.now(), table_name, '\n'.join(route_list))


if __name__ == '__main__':
    args = parse_opts()
    as_list = []

    if args.name:
        as_list += find_asn_by_name(args.name)
    if args.country or args.exclude:
        as_list_by_country, as_exclude = find_asn_by_country(args.country, args.exclude)
        as_list += as_list_by_country

    # filter excludes
    for asn in as_exclude:
        if asn in as_list:
            as_list.remove(asn)
    # remove duplicates
    as_list = list(set(as_list))

    detailed_nets = []
    for asn, nets in read_routing_table(as_list).items():
        detailed_nets += nets

    p = Popen(['aggregate'], stdin=PIPE, stdout=PIPE)
    stdout, stderr = p.communicate('\n'.join(detailed_nets).encode('utf-8'))
    if stderr and stderr != '':
        print(stderr)
    write_file(args.output, data=gen_routing_items(args, stdout.decode('utf-8').split('\n')).encode('utf-8'))