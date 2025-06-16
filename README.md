# Proxmox Firewall Updater

The Proxmox Firewall Updater is a Python script designed to automate the process of updating firewall IPSets and aliases based on DNS entries. This ensures that firewall configurations remain synchronized with DNS changes, enhancing security and network management in Proxmox environments.

The configuration of the firewall objects to update is done by adding a comment to the IPSet or alias with the domain name to resolve.

For example, an IPSet or alias with the comment `#resolve: example.com` will be updated with the IP address(es) of `example.com`.

<img width="397" alt="image" src="https://github.com/simonegiacomelli/proxmox-firewall-updater/assets/3785783/85518007-756c-4804-b0a5-925b88330e02">

You can also add a regular comment along with the resolve directive.

Note: IPSets and aliases handle IP addresses differently:

- **IPSets**: 
  - Can contain multiple IP addresses from DNS resolution
  - Support multiple comma-separated domain names (e.g., `#resolve: example.com,example.org`)
  - All IP addresses from all domains will be included in the IPSet
  - Special entries starting with `dc/` or `guest/` (which are references to aliases) will be preserved and not removed during DNS synchronization
  - Can perform multiple DNS queries per domain to capture more IP addresses (e.g., `#resolve: example.com #queries=3 #delay=5`)
- **Aliases**: 
  - Only use the first IP address from DNS resolution 
  - If multiple domains are specified, only the first domain is used

The script only updates entries if the IP address(es) of the corresponding domain name change in order to minimize logging.

## Installation

To get the script on your Proxmox server, run the following command in your pve shell:

```bash
curl https://raw.githubusercontent.com/base23gmbh/proxmox-firewall-updater/main/update_firewall.py -o update_firewall.py
```

### Scheduling with Cron

You can add a cron job to run the script every 5 minutes:

```bash
(crontab -l 2>/dev/null; echo "*/5 * * * * /usr/bin/env python3 $(pwd)/update_firewall.py 2>&1 | logger -t update_firewall.py") | crontab -
```

The cron daemon will log the execution of the script to the system log which is usually too verbose.
If you want to avoid this, you can use the scheduling explained in the next section.

### Scheduling without Cron

If you prefer to avoid verbose cron job logs, you can create a bash script with a loop that runs the python script every 5 minutes.
To activate this script, add it to the @reboot cron job:

```bash
echo "while true; do (python3 $(pwd)/update_firewall.py | logger -t update_firewall.py); sleep 300; done" > firewall_updater_forever.sh
chmod +x firewall_updater_forever.sh
(crontab -l 2>/dev/null; echo "@reboot /bin/bash -c $(pwd)/firewall_updater_forever.sh &") | crontab -
```

Beware that the above will take effect at every reboot.
The first time, to avoid rebooting the server, you can run the bash script manually:

```bash
/bin/bash -c ./firewall_updater_forever.sh &
```

## Command Line Options

The script supports several command line options:

- `--dry-run`: Executes the script without making any changes. This is useful for testing and debugging.
- `--verbose`: Provides detailed logging of operations, which can aid in understanding the script's behavior and troubleshooting.
- `--ipsets`: Only update IPSets (don't process aliases).
- `--aliases`: Only update aliases (don't process IPSets).
- `--all`: Update both IPSets and aliases (default if no option is specified).
- `--version`: Show version information and exit.

You can use multiple options together, for example:

```bash
python3 update_firewall.py --ipsets --dry-run --verbose
```

In this mode, the script will print detailed logs of its intended actions for IPSets without actually making any changes.

# Internal Workings

## Automated Tests

This project includes comprehensive automated tests to ensure its reliability and correctness. These tests cover various scenarios and edge cases, providing a robust safety net for ongoing development.

The tests are written using Python's built-in `unittest` module, and they thoroughly test the functionality of the script, including the DNS resolution and the updating of firewall IPSets and aliases.

To run the tests, clone the repo and use the following command:

```bash
python3 -m unittest update_firewall_test.py
```

## Proxmox API

The script uses `pvesh` commands to interact with Proxmox VE firewall objects. For more details, refer to the Proxmox VE API documentation.

### pvesh get

Get IPSets:

`pvesh get cluster/firewall/ipset --output-format json`

Example output:

```json
[
  {
    "name": "ipset_example",
    "comment": "#resolve: example.com",
    "entries": [
      {"cidr": "1.2.3.4"},
      {"cidr": "5.6.7.8"}
    ]
  }
]
```

Get aliases:

`pvesh get cluster/firewall/aliases --output-format json`

Example output:

```json
[
  {
    "cidr": "1.2.3.4",
    "comment": "comment foo #resolve: example.com",
    "digest": "48ba54e4cabe338b1cb490bb9c5b617f61bd4212",
    "ipversion": 4,
    "name": "alias_example_com"
  }
]
```

### pvesh create/set

Creating or updating an IPSet:

`pvesh create cluster/firewall/ipset --name ipset_example --comment "#resolve: example.com"`

Adding an entry to an IPSet:

`pvesh create cluster/firewall/ipset/ipset_example --cidr 1.2.3.4`

Updating an alias:

`pvesh set cluster/firewall/aliases/alias_example_com --cidr 1.2.3.4 --comment "#resolve: example.com"`

## Relevant Proxmox Forum Thread

For more information, check out this [Proxmox Forum thread](https://forum.proxmox.com/threads/firewall-alias-with-domainname.43036/) on firewall aliases with domain names.

## Advanced Features

### Multiple Queries for DNS Round-Robin

Some domains use DNS round-robin or similar techniques to distribute load, returning different IP addresses on successive DNS queries. To capture all these IP addresses, you can configure IPSets to perform multiple DNS queries:

```
#resolve: example.com #queries=3 #delay=5
```

This configuration will:
1. Query the domain 3 times (instead of the default once)
2. Wait 5 seconds between each query (instead of the default 3 seconds)
3. Collect all unique IP addresses from all queries

The syntax options are:
- `#queries=N` - Number of times to query each domain (default: 1)
- `#delay=N` - Delay in seconds between queries (default: 3)

This feature is especially useful for domains that use DNS-based load balancing or geographic distribution, ensuring your firewall rules include all possible IP addresses the domain might resolve to.

Note: This feature is only available for IPSets, not for aliases (which always use only the first IP address from the first query).
