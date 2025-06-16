# Proxmox Firewall Updater

The Proxmox Firewall Updater is a Python script designed to automate the process of updating firewall IPSets and aliases based on DNS entries. This ensures that firewall configurations remain synchronized with DNS changes, enhancing security and network management in Proxmox environments.

The configuration of the firewall objects to update is done by adding a comment to the IPSet or alias with the domain name to resolve.

For example, an IPSet or alias with the comment `#resolve=example.com` will be updated with the IP address(es) of `example.com`. 

<img width="397" alt="image" src="https://github.com/simonegiacomelli/proxmox-firewall-updater/assets/3785783/85518007-756c-4804-b0a5-925b88330e02">

You can also add a regular comment along with the resolve directive.

> Note: The older syntax with `#resolve:` is still supported for backward compatibility, but the new syntax with `#resolve=` is preferred for consistency with other options.

Note: IPSets and aliases handle IP addresses differently:

- **IPSets**: 
  - Can contain multiple IP addresses from DNS resolution
  - Support multiple comma-separated domain names (e.g., `#resolve=example.com,example.org`)
  - All IP addresses from all domains will be included in the IPSet
  - Special entries starting with `dc/` or `guest/` (which are references to aliases) will be preserved and not removed during DNS synchronization
  - Can perform multiple DNS queries per domain to capture more IP addresses (e.g., `#resolve=example.com #queries=3 #delay=5`)
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
#resolve=example.com #queries=3 #delay=5
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

## Configuration Syntax

When configuring firewall objects for DNS resolution, you can use the following comment syntax:

```
#resolve=domain1.com,domain2.com #queries=3 #delay=5
```

### Available Options

- `#resolve=domains`: Specifies one or more domain names (comma-separated) to resolve.
- `#queries=N`: Number of DNS queries to perform for each domain (default: 1).
- `#delay=N`: Delay in seconds between multiple queries (default: 3).

### Examples

1. Basic IPSet with a single domain:
   ```
   #resolve=example.com
   ```

2. IPSet with multiple domains:
   ```
   #resolve=example.com,example.org
   ```

3. IPSet with multiple queries for DNS round-robin:
   ```
   #resolve=load-balanced-service.com #queries=5 #delay=2
   ```

4. IPSet with multiple domains and custom queries:
   ```
   #resolve=service1.com,service2.com #queries=3 #delay=1
   ```

5. Alias with a single domain (only uses first IP):
   ```
   #resolve=example.com
   ```

> Note: For backward compatibility, the older syntax `#resolve:` is still supported, but the new `#resolve=` syntax is preferred for consistency.

## Migrating from Old to New Syntax

With version 3.5.0, we introduced a more consistent syntax for configuration options. While the older syntax is still supported for backward compatibility, we recommend migrating to the new syntax:

### Old Syntax

```
#resolve: example.com
```

### New Syntax

```
#resolve=example.com
```

### How to Migrate

You can update your firewall objects in the Proxmox web interface by editing the comments:

1. Go to Datacenter → Firewall → IPSets (or Aliases)
2. Edit the comment for each object
3. Replace `#resolve: ` with `#resolve=` (remove the space after the colon)

This will make your configuration more consistent and future-proof. The old syntax will continue to work for backward compatibility, so there is no urgency to update all at once.

## Troubleshooting

### DNS Resolution Issues

If you're having trouble with DNS resolution:

1. **Use the `--verbose` flag** to see detailed information:
   ```
   python3 update_firewall.py --verbose
   ```

2. **Try multiple queries** for domains with round-robin DNS:
   ```
   #resolve=example.com #queries=5
   ```
   
3. **Verify the domain is resolvable** from your Proxmox host:
   ```bash
   nslookup example.com
   ```

### Multiple Queries Not Working

If multiple queries (`#queries=N`) aren't returning different IP addresses:

1. Verify the domain actually uses round-robin DNS or similar load balancing
2. Try increasing the delay (`#delay=10`) to allow for DNS cache timeout
3. Make sure your DNS server isn't caching responses locally

### Alias References Not Being Preserved

If your alias references (starting with `dc/` or `guest/`) aren't being preserved:

1. Ensure you're using version 3.4.0 or higher
2. Run with `--verbose` to see if the alias references are being detected
3. Check that the alias references are properly formatted in the IPSet
