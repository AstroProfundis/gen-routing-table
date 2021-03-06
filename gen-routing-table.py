#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Generate static routing table configuration for bird

import argparse
import datetime
import os

from subprocess import Popen, PIPE

# the location of raw data
ip_list_file = 'data/delegated-apnic-latest'
as_list_file = 'data/geoip.csv'
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


def parse_opts():
    parser = argparse.ArgumentParser(
        description='Generate static routing table for bird.')
    parser.add_argument('--name', action='append', default=None,
                        help="Name of AS region, partially matched in AS description.")
    parser.add_argument('--asn', action='append', default=None,
                        help='AS Number to include, only the numeric part needed.')
    parser.add_argument('--country', action='append', default=None,
                        help='Country code, to include a whole country/region\'s network')
    parser.add_argument('--exclude', action='append', default=None,
                        help='Country code to exclude from result, this will overwite other filters.')
    parser.add_argument('--exclude-as', action='append', default=None,
                        help='ASN(s) to exclude from result, this will overwite other filters.')
    parser.add_argument('--gateway', action='store', required=True,
                        help='Default gateway of internet access.')
    parser.add_argument('--table-name', action='store', default='generated_table',
                        help='Routing table name of generated routes.')
    parser.add_argument('--version', action='store', type=int, default=1,
                        help='BIRD version, supported values are 1 or 2.')
    parser.add_argument('-o', '--output', action='store', default='routes.conf',
                        help='Output file name of generated config.')
    return parser.parse_args()


def get_ip_data():
    result = {}
    raw_ip = read_file(ip_list_file)
    for line in raw_ip.split('\n'):
        if not line or not str.startswith(line, 'apnic'):
            continue
        _tmp = line.split('|')
        if _tmp[1] == '*' or _tmp[3] == '*':
            continue
        _code = _tmp[1]  # country code
        _type = _tmp[2]  # record type
        if _type != 'asn':
            # skip ip blocks, as we don't need them now, but the looking table
            # structure is kept in case we'll use it in the future
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
    asn_set = set()
    result = {}
    raw_as = read_file(as_list_file)
    for line in raw_as.split('\n'):
        if not line:
            continue
        _tmp = line.split(',')
        # not starting with an ASN
        if not _tmp[1].isdigit():
            continue
        asn = _tmp[1]      # AS Number
        name = _tmp[2]     # AS Name
        if asn in asn_set:
            continue
        asn_set.add(asn)
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
            # store every network only one time
            try:
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
    gateway = args.gateway
    config_template_v1 = '''# Generated for %d routes at: %s
protocol static {
  table %s;
%s
}
'''
    config_template_v2 = '''# Generated for %d routes at: %s
protocol static {
  ipv4 { table %s; };
%s
}
'''
    if args.version == 2:
        config_template = config_template_v2
    else:
        config_template = config_template_v1
    route_template = '  route %s via %s;'

    route_list = []
    for net in net_list:
        if not net:
            continue
        route_list.append(route_template % (net, gateway))
    return config_template % (len(net_list), datetime.datetime.now(), table_name, '\n'.join(route_list))


if __name__ == '__main__':
    args = parse_opts()
    as_list = []

    if args.name:
        as_list += find_asn_by_name(args.name)
    if args.country or args.exclude:
        as_list_by_country, as_exclude = find_asn_by_country(
            args.country, args.exclude)
        as_list += as_list_by_country
    if args.asn:
        for asn in args.asn:
            if asn in as_list:
                continue
            as_list.append(asn)

    # filter excludes
    for asn in as_exclude: # calculated exlucde list from country code
        try:
            as_list.remove(asn)
        except:
            pass
    for asn in args.exclude_as: # exclude list from args
        print("removing asn %s" % asn)
        try:
            as_list.remove(asn)
            print("removed asn %s" % asn)
        except:
            pass
    # remove duplicates
    as_list = list(set(as_list))

    detailed_nets = []
    for asn, nets in read_routing_table(as_list).items():
        detailed_nets += nets

    p = Popen(['aggregate'], stdin=PIPE, stdout=PIPE)
    stdout, stderr = p.communicate('\n'.join(detailed_nets).encode('utf-8'))
    if stderr and stderr != '':
        print(stderr)
    write_file(args.output, data=gen_routing_items(
        args, stdout.decode('utf-8').split('\n')).encode('utf-8'))
