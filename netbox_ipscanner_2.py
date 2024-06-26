import pynetbox, urllib3, socket, ipaddress
from extras.scripts import Script
from ping3 import ping, verbose_ping

# Token und Netbox URL für API Zugang
TOKEN='<your token>'

NETBOXURL='http://<yournetboxinstal>/'

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning) # HTTP Warnung ausmachen

class IpScan(Script):
    # Meta Klasse
    class Meta:
        name = "IP Scanner"
        description = "Scans available prefixes and updates ip addresses in IPAM Module using ping3"
        job_timeout = 36000

    def run(self, data, commit):

        def reverse_lookup(ip):
            '''
            Mini function that does DNS reverse lookup with controlled failure
            '''
            try:
                data = socket.gethostbyaddr(ip)
            except Exception:
                return '' # Bricht schön ab
            if data[0] == '': # Gibt wenn nichts da ist
                return ''
            else:
                return data[0]

        nb = pynetbox.api(NETBOXURL, token=TOKEN)
        nb.http_session.verify = False # Keine Zertifikate checken

        subnets = nb.ipam.prefixes.all()  # Prefixe auslesen

        for subnet in subnets:
            if str(subnet.status) == 'Reserved': # Keine reservierten Subnets scannen
                self.log_warning(f"Scan of {subnet.prefix} NOT done (is Reserved)")
                continue
            IPv4network = ipaddress.IPv4Network(subnet)
            mask = '/'+str(IPv4network.prefixlen)

            # IPs von Netbox ziehen
            netbox_addresses = dict()
            for ip in nb.ipam.ip_addresses.filter(parent=str(subnet)):
                netbox_addresses[str(ip)] = ip

            for address in IPv4network.hosts(): # Addressen pro Prefix verarbeiten
                ip_mask=str(address)+mask
                current_in_netbox = netbox_addresses.get(ip_mask)
                name = reverse_lookup(str(address)) # Namensauflösung
                if ping(str(address), timeout=1):  # Wenn Ping durch geht
                    if current_in_netbox != None: # Die Addresse ist schon in Netbox, setze den als online und check ob sich die Name geändert hat
                        if current_in_netbox.status.value != "online":
                            nb.ipam.ip_addresses.update([{'id':current_in_netbox.id, 'status':'online'},])
                        if current_in_netbox.dns_name.lower() != name.lower(): # Wenn die Namen vom DNS und Netbox nicht passen, wird die Name vom DNS übernommen
                            self.log_success(f'Name for {address} updated to {name}')
                            nb.ipam.ip_addresses.update([{'id':current_in_netbox.id, 'dns_name':name},])
                    else: # Wenn gar nicht in Netbox vorhanden, Addresse hinzufügen
                        res = nb.ipam.ip_addresses.create(address=ip_mask, status='online', dns_name=name)
                        if res:
                            self.log_success(f'Added {address} - {name}')
                        else:
                            self.log_error(f'Adding {address} - {name} FAILED')
                else: # Wenn Ping nicht durch geht
                    if name != '': # Wenn die Addresse im DNS vorhanden ist
                        if current_in_netbox != None: # Und die Addresse in Netbox vorhanden ist
                            nb.ipam.ip_addresses.update([{'id':current_in_netbox.id, 'status':'in dns', 'dns_name':name},])
                        else: # Wenn die Addresse nicht in Netbox ist
                            res = nb.ipam.ip_addresses.create(address=ip_mask, status='in dns', dns_name=name)
                            if res:
                                self.log_success(f'Added {address} - {name} with status in dns')
                            else:
                                self.log_error(f'Adding {address} - {name} FAILED')
                    else: # if the host does not have a DNS name
                        if current_in_netbox != None: # Wenn die Addresse im Netbox vorhanden ist
                            nb.ipam.ip_addresses.update([{'id':current_in_netbox.id, 'status':'offline'},])
