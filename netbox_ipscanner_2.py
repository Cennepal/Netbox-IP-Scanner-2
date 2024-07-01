from extras.scripts import Script, StringVar
import pynetbox, urllib3, socket, ipaddress
from ping3 import ping, verbose_ping

class IpScan(Script):
    class Meta:
        name = "IP Scanner"
        description = "Scans available prefixes and updates ip addresses in IPAM Module using ping3"
        job_timeout = 36000

    token = StringVar(
        description="Token for API access"
    )
    netbox_url = StringVar(
        description="Netbox URL"
    )

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

        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning) # HTTP Warnung ausmachen

        nb = pynetbox.api(url=data['netbox_url'], token=data['token'])
        nb.http_session.verify = False # Keine Zertifikate checken

        subnets = nb.ipam.prefixes.all()  # Prefixe auslesen

        for subnet in subnets:
            if str(subnet.status) == 'Reserved': # Keine reservierten Subnets scannen
                self.log_info(f"Scan of {subnet.prefix} NOT done (is Reserved)")
                continue
            IPv4network = ipaddress.IPv4Network(subnet.prefix)
            mask = '/'+str(IPv4network.prefixlen)

            # IPs von Netbox ziehen
            netbox_addresses = dict()
            for ip in nb.ipam.ip_addresses.filter(parent=str(subnet.prefix)):
                netbox_addresses[str(ip.address)] = ip

            for address in IPv4network.hosts(): # Addressen pro Prefix verarbeiten
                ip_mask=str(address)+mask
                current_in_netbox = netbox_addresses.get(ip_mask)
                name = reverse_lookup(str(address)) # Namensauflösung
                if ping(str(address), timeout=1):  # Wenn Ping durch geht
                    if current_in_netbox != None: # Die Addresse ist schon in Netbox, setze den als online und check ob sich die Name geändert hat
                        if current_in_netbox.status.label != "Online":
                            current_in_netbox.update(data={'status':'online'})
                        if current_in_netbox.dns_name.lower() != name.lower(): # Wenn die Namen vom DNS und Netbox nicht passen, wird die Name vom DNS übernommen
                            self.log_info(f'Name for {address} updated to {name}')
                            current_in_netbox.update(data={'dns_name':name})
                    else: # Wenn gar nicht in Netbox vorhanden, Addresse hinzufügen
                        res = nb.ipam.ip_addresses.create(address=ip_mask, status='online', dns_name=name)
                        if res:
                            self.log_info(f'Added {address} - {name}')
                        else:
                            self.log_failure(f'Adding {address} - {name} FAILED')
                else: # Wenn Ping nicht durch geht
                    if name != '': # Wenn die Addresse im DNS vorhanden ist
                        if current_in_netbox != None: # Und die Addresse in Netbox vorhanden ist
                            current_in_netbox.update(data={'status':'in dns', 'dns_name':name})
                        else: # Wenn die Addresse nicht in Netbox ist
                            res = nb.ipam.ip_addresses.create(address=ip_mask, status='in dns', dns_name=name)
                            if res:
                                self.log_info(f'Added {address} - {name} with status in dns')
                            else:
                                self.log_failure(f'Adding {address} - {name} FAILED')
                    else: # Wenn der Host im DNS nicht vorhanden ist
                        if current_in_netbox != None: # Wenn die Addresse im Netbox vorhanden ist
                            current_in_netbox.update(data={'status':'offline'})
