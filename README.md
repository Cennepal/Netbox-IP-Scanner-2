# Netbox-IP-Scanner-2
This is a rewrite of [this repo](https://github.com/bbird81/Netbox-ipscanner) which is in my opinion, completely broken.

# Yes, I will tell you my life story
Basically, the older script relied on 'networkscan'. A package, that just does not work. Meaning if you were to scan a subnet it would just say "Nothing found". That got me pretty frustrated, but the thing didn't even set a timeout for it's own job! So good luck scanning your gazillions of subnets in 5 minutes before Netbox aborts the script.

# What am I selling you?
Well, it's not crack, but hear me out.  

- First, ping3 is used for network stuffs and not networkscan, which is borked.
- Second, you will actually be able to run this across your gazillion subnets without it aborting. The timeout is 10 hours, put it higher if you need.
- Third, one of my own additions. Now the scan marks IP Addresses as either 'online', 'in dns' or 'offline'. So even if something is offline at the time of scan, but it has an existing DNS entry, it will be saved.

# Alright, here are the dependencies. No rush.
Alright here you go:  
- ipcalc
- pynetbox
- ping3

# Custom status?
Yes, this thing uses them. Just go into your 'configuration.py' and insert this funny little block just above the "Required Settings" banner: 
```
FIELD_CHOICES = {
    'ipam.IPAddress.status+': (
        ('online', 'Online', 'green'),
        ('offline', 'Offline', 'red'),
        ('in dns', 'In DNS', 'orange'),
    )
}
```
