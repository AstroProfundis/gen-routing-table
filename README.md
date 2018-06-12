```
mkdir -p data
wget -O data/delegated-apnic-latest https://ftp.apnic.net/apnic/stats/apnic/delegated-apnic-latest
wget -O data/asn.txt ftp://ftp.arin.net/info/asn.txt
wget -O data/oix-full-snapshot-latest.dat.bz2 http://archive.routeviews.org/oix-route-views/oix-full-snapshot-latest.dat.bz2
cd data
bzip2 -d oix-full-snapshot-latest.dat.bz2
```
