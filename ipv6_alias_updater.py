#!/usr/bin/env python3

import argparse
import configparser
import ipaddress
import logging
import subprocess
import time
import typing

import urllib3
import requests


# DO NOT EDIT BELOW THIS LINE!
config = {}


class UpdaterError(Exception):
    pass


def api_request(method: str, path: str, params: typing.List = None, content: dict = None) -> typing.Dict:
    if params is None:
        params = []
    if content is None:
        content = {}

    host = config["opnsense"]["host"]
    auth = (config["opnsense"]["api_key"], config["opnsense"]["api_secret"])
    verify = config["opnsense"].getboolean("ssl_verify")

    def makerequest(func):
        try:
            return func
        except requests.RequestException as e:
            raise UpdaterError(e) from e

    if method == "GET":
        r = makerequest(requests.get(
            host + "/api/" + path + "/" + "/".join(params),
            auth=auth, verify=verify
        ))
    elif method == "POST":
        r = makerequest(requests.post(
            host + "/api/" + path + "/" + "/".join(params), json=content,
            auth=auth, verify=verify
        ))
    elif method == "PUT":
        r = makerequest(requests.post(
            host + "/api/" + path + "/" + "/".join(params), json=content,
            auth=auth, verify=verify
        ))
    elif method == "DELETE":
        r = makerequest(requests.get(
            host + "/api/" + path + "/" + "/".join(params),
            auth=auth, verify=verify
        ))
    else:
        raise ValueError("method not supported")

    try:
        r.raise_for_status()
        return r.json()
    except requests.RequestException as e:
        raise UpdaterError(e) from e

# Actual execution


def update_alias(old_prefix: ipaddress.IPv6Network, new_prefix: ipaddress.IPv6Network):
    uuid = api_request("GET", "firewall/alias/getAliasUUID", [config["default"]["alias"]])["uuid"]
    alias_contents = api_request("GET", "firewall/alias_util/list", [config["default"]["alias"]])

    logging.debug(f"Alias uuid: {uuid}")

    new_rows = []
    for row in alias_contents["rows"]:
        if row["ip"] != str(old_prefix):
            new_rows.append(row["ip"])
    new_rows.append(str(new_prefix))

    post_body = {
        "alias": {
            "enabled": 1,
            "name": config["default"]["alias"],
            "type": "network",
            "content": "\n".join(new_rows)
        }
    }

    api_request("POST", "firewall/alias/setItem", [uuid], post_body)
    api_request("POST", "firewall/alias/reconfigure")
    logging.info(f"Updated alias with prefix {new_prefix}")


def get_iface_ipv6_prefix() -> ipaddress.IPv6Network:
    try:
        iface = subprocess.run(["ifconfig", config["default"]["monitor_iface"], "inet6"],
                               capture_output=True, check=True)
    except OSError as e:
        raise UpdaterError(f"Error trying to get local ipv6 address: {e}") from e

    for line in iface.stdout.splitlines():
        try:
            _addr = str(line).strip().split(" ")[1]
            # Not all ifconfig lines are ip addresses
            iface_ipv6_addr = ipaddress.IPv6Address(_addr)
        except (ValueError, IndexError):
            continue

        # FOUND IT!
        if iface_ipv6_addr.is_global:
            prefix = ipaddress.IPv6Network(
                str(iface_ipv6_addr) + f"/{int(config['default']['prefix_length'])}", strict=False)
            return prefix

    raise UpdaterError("No global IPv6 address found")


def get_alias_ipv6_prefix() -> ipaddress.IPv6Network:
    res = api_request("GET", "firewall/alias_util/list", [config["default"]["alias"]])
    prefix_strings = [row["ip"] for row in res["rows"]]

    def ipv6_filter(prefix: str):
        """Check if a given prefix string is a globally routable IPv6 prefix"""
        # Convert to IP address to check whether we are a global prefix
        try:
            ip_a = ipaddress.IPv6Address(prefix.split("/")[0])
        except ValueError:
            # Not a valid IPv6 address, we don't care
            return None

        if ip_a.is_global:
            return ipaddress.IPv6Network(str(ip_a) + f"/{config['default']['prefix_length']}", strict=False)
        return None

    ipv6_guas = list(filter(None, [ipv6_filter(prefix) for prefix in prefix_strings]))

    if len(ipv6_guas) > 1:
        logging.warning("Found more than 1 global IPv6 prefix in alias -"
                        f"selecting the first one ({ipv6_guas[0]}) and ignoring the others ({ipv6_guas[1:]}).")
    elif len(ipv6_guas) == 0:
        logging.warning("Did not find a valid IPV6 global prefix in alias.")
        return None
    return ipv6_guas[0]


def run():
    try:
        iface_ipv6_prefix = get_iface_ipv6_prefix()
    except UpdaterError as e:
        logging.warning(f"Could not determine interface IPv6 address. Error: {e}")
    logging.info(f"Current Interface IPv6 prefix: {iface_ipv6_prefix}")

    try:
        alias_ipv6_prefix = get_alias_ipv6_prefix()
    except UpdaterError as e:
        logging.warning(f"Error while determining alias IPv6 address. Error: {e}")
    logging.info(f"Current Alias IPv6 prefix: {alias_ipv6_prefix}")

    if iface_ipv6_prefix == alias_ipv6_prefix:
        logging.info("Alias and interface prefix match. No action required")
        return

    logging.info("Prefix mismatch. Updating alias...")
    try:
        update_alias(alias_ipv6_prefix, iface_ipv6_prefix)
    except UpdaterError as e:
        logging.error(f"Could not update Alias. Reason: {e}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-c", "--config", help="Path to the configuration file. Default: './ipv6_alias_updater.conf'", default="./ipv6_alias_updater.conf")
    args = parser.parse_args()

    # pylint: disable=global-statement
    global config
    config = configparser.ConfigParser(default_section="default")
    config.read(args.config)

    # Initial setup
    logging.basicConfig(level=getattr(logging, config["logging"]["level"]),
                        filename=config["logging"]["file"], format="%(asctime)s %(levelname)s: %(message)s")
    logging.info("ipv6_alias_updater starting...")

    if not config["opnsense"].getboolean("ssl_verify"):
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    # Check connectivity to API
    api_request("GET", "core/firmware/status")
    logging.info("ipv6_alias_updater is running")

    while True:
        run()
        time.sleep(int(config["default"]["check_interval"]))


if __name__ == "__main__":
    main()
