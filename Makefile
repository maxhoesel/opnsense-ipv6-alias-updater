# Simple makefile for opnsense-ipv6-alias-updater

install:
	install -d /root/ipv6_alias_updater/
	install -m 755 ipv6_alias_updater.py /root/ipv6_alias_updater/
	install -m 640 ipv6_alias_updater.conf /root/ipv6_alias_updater/
	install -m 755 service/ipv6_alias_updater /usr/local/etc/rc.d/
	echo 'ipv6_alias_updater_enable="YES"' > /etc/rc.conf.d/ipv6_alias_updater
