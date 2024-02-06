# opnsense-ipv6-alias-updater

---

** ⚠️ This Project has been archived! ⚠️ **

Alternative recommendation: You can create a interface group that contains all your local networks, then use that groups net alias in firewall rules.

---

A little helper script for OPNSense that automatically updates an alias with a dynamic IP prefix, determined by looking at an currently running interface.

This can be useful if your ISP only gives you a dynamic IPV6 prefix and you want to have a firewall rule that permits internet access, but forbids local access:

```
Protocol 	Source 	Port 	Destination 	Port 	Gateway 	Schedule 	Description
IPv4+6      *       *      	!nets_local 	* 	    * 	        * 	        Allow Internet Access
```

In this case, the `nets_local` alias must contain all local networks.
This is easy to do for IPv4 (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`), but not so for IPv6.
If you enter your current IPv6 prefix and it changes at a later point,
your alias will no longer block local access (which is a pretty big security risk!) and will probably block some other random other customer on your ISP.

To fix this, you would need to either:

- Manually update the alias every time your internal network changes
- Use some sort of IPv6 mapping solution (such as NAT66 or NPT6)

This script automates the task of updating a given alias with your currently assigned IPv6 prefix.
It runs as a service on OPNsense, so you don't even have to set up a scheduled job for it.

## Installation

1. Clone this repository onto your OPNSense box
2. Rename `ipv6_alias_updater.example.conf` to `ipv6_alias_updater.conf` and adjust the settings inside
  - **Make sure to adjust the API key parameters or the script will fail!**
3. Install the service by running `make install` as root
4. Start the service using `service ipv6_alias_updater start`
5. Check the output in `/var/log/ipv6_alias_updater.log`

## Notes

- If the service does not show up in `ps aux` after starting it, there was probably an error while reading the config file.
  Make sure that all your entries are correct and that the file is in the right place (same folder as the script).
