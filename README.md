# What's This

This is a simple script that can generate static routing table config file in `bird` format from the global BGP dump.

The propose of this script is to detect and save certain networks (IP blocks) to a special routing table for futher actions. I'm using it to hijack some specific networks to a encrypted tunnel on my gateway, to bypass a firewall on the default route.

# Usage

Download data files to local.
```
mkdir -p data
wget -O data/delegated-apnic-latest https://ftp.apnic.net/apnic/stats/apnic/delegated-apnic-latest
wget -O geoip.zip https://geolite.maxmind.com/download/geoip/database/GeoLite2-ASN-CSV.zip
wget -O data/oix-full-snapshot-latest.dat.bz2 http://archive.routeviews.org/oix-route-views/oix-full-snapshot-latest.dat.bz2
cd data
bzip2 -d oix-full-snapshot-latest.dat.bz2
unzip geoip.zip
mv GeoLite2-ASN-CSV_*/GeoLite2-ASN-Blocks-IPv4.csv geoip.csv
```
Then run the script to generate config file, there're some arguments that controls the filters of ASes, see `-h` for details.

The `--name`/`--country`/`--asn`/`--exclude` arguments can be used multiple times, to pass more than one values. The `--exclude` argument only accept two-letter country code.

Argument values are case insensitive, except `-o`/`--output` and `--table-name`.

It's possible to write a wrap script to automate the update process.

# License

This script is written for private usage, and absolutely no garentee is provided. The code and its features may be updated or changed without any notice, or may not be having any future update at all.

The project is licensed under [GLWTPL](https://github.com/me-shaon/GLWTPL) and wish you a good luck.
