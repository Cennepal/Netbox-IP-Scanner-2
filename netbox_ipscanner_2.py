from extras.scripts import Script
import ipaddress
from ping3 import ping
import dns.resolver
import dns.reversename
from ipam.models import IPAddress, Prefix

class IPScanner(Script):
    class Meta:
        name = "IP Scanner"
        description = "Scans available prefixes and updates ip addresses in IPAM Module using ping3."
        job_timeout = 36000  # Timeout für 10 Stunden

    def run(self, data, commit):
        # Reverse Lookup mit Abbruch
        self.log_info(f"Running script (commit={commit})")
        if not commit:
            self.log_failure("Commit changes is not checked. Aborting script.")
            return

        def reverse_dns_lookup(ip):
            try:
                addr = dns.reversename.from_address(ip)
                return str(dns.resolver.resolve(addr, "PTR")[0])
            except (dns.resolver.NXDOMAIN, dns.resolver.Timeout, dns.resolver.NoNameservers):
                return ''

        # Prefixe aus Netbox ziehen
        subnets = Prefix.objects.all()

        # Iteration über alle Prefixe
        for subnet in subnets:
            self.log_info(f"Processing subnet: {subnet.prefix}")

            # Reservierte Subnetze überspringen
            if subnet.status == 'reserved':
                self.log_info(f"Skipping reserved subnet: {subnet.prefix}")
                continue

            # IP-Adressen aus dem Subnetz ziehen
            network = ipaddress.IPv4Network(subnet.prefix)
            mask = f"/{network.prefixlen}"
            is_pingable_ms_to = 0.4
            sb_timeout = False

            for ip in network.hosts():
                ip_with_mask = f"{ip}{mask}"
                dns_name = reverse_dns_lookup(str(ip))

                # Pingen mit Timeout
                is_pingable = ping(str(ip), timeout=is_pingable_ms_to, unit='ms')

                if not sb_timeout and is_pingable:
                    is_pingable_first = ping(str(ip), timeout=0.4, unit='ms')
                    is_pingable_ms = round(is_pingable_first, 0)
                    is_pingable_ms_to = (is_pingable_ms + 20) / 1000
                    self.log_info(f"Pinging IP {ip} with result: {is_pingable_ms_to} s.")
                    sb_timeout = True

                existing_ip = IPAddress.objects.filter(address=ip_with_mask)

                # IP-Adresse existiert bereits
                if existing_ip:
                    # Mache aus dem str() 'existing_ip' ein Objekt (Kann man an .filter und .get unterscheiden)
                    existing_ip = IPAddress.objects.get(address=ip_with_mask)
                    # Wenn die IP-Adresse pingbar ist und der Status nicht 'Online' ist, setze den Status auf 'Online'
                    if is_pingable and existing_ip.status != "online":
                        existing_ip.status = 'online'
                        self.log_info(f"IP {ip} is online. Updating status.")
                    # Wenn die IP-Adresse nicht pingbar ist und der Status nicht 'Offline' ist, setze den Status auf 'Offline'
                    elif not is_pingable and existing_ip.status != "offline":
                        existing_ip.status = 'offline'
                        self.log_info(f"IP {ip} is offline. Updating status.")
                    # Wenn die DNS-Namen unterschiedlich sind, setze den DNS-Namen neu
                    if dns_name:
                        if dns_name.lower() != existing_ip.dns_name.lower():
                            existing_ip.dns_name = dns_name
                            self.log_info(f"Updating DNS name for IP {ip} to {dns_name}.")
                    existing_ip.full_clean()
                    existing_ip.save()
                    self.log_info(f"Updated IP {ip_with_mask}.")
                # IP-Adresse existiert noch nicht
                elif is_pingable or dns_name:
                    status = 'online' if is_pingable else 'in dns'
                    new_ip = IPAddress(address=ip_with_mask, status=status)
                    new_ip.full_clean()
                    new_ip.save()
                    # Wenn ein DNS-Name gefunden wurde, setze ihn
                    if dns_name:
                        new_ip.dns_name = dns_name
                        new_ip.full_clean()
                        new_ip.save()
                    
                    self.log_info(f"Added new IP {ip_with_mask} with status {status}.")