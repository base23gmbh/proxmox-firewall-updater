# Proxmox Firewall Updater

The Proxmox Firewall Updater is a Python script designed to automate the process of updating firewall IPSets and aliases based on DNS entries. This ensures that firewall configurations remain synchronized with DNS changes, enhancing security and network management in Proxmox environments.

The configuration of the firewall objects to update is done by adding a comment to the IPSet or alias with the domain name to resolve.

For example, an IPSet or alias with the comment `#resolve=example.com` will be updated with the IP address(es) of `example.com`. 

<img width="397" alt="image" src="https://github.com/simonegiacomelli/proxmox-firewall-updater/assets/3785783/85518007-756c-4804-b0a5-925b88330e02">

You can also add a regular comment along with the resolve directive.

> [!NOTE]
> The older syntax with `#resolve:` is still supported for backward compatibility, but the new syntax with `#resolve=` is preferred for consistency with other options.

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

## Table of Contents

- [Proxmox Firewall Updater](#proxmox-firewall-updater)
  - [Table of Contents](#table-of-contents)
  - [Installation](#installation)
    - [Scheduling with Cron](#scheduling-with-cron)
    - [Scheduling without Cron](#scheduling-without-cron)
  - [Command Line Options](#command-line-options)
    - [Custom DNS Servers](#custom-dns-servers)
  - [Configuring IPSets and Aliases](#configuring-ipsets-and-aliases)
    - [Understanding IPSets vs Aliases](#understanding-ipsets-vs-aliases)
    - [Configuration Syntax](#configuration-syntax)
    - [Step-by-Step Configuration Guide](#step-by-step-configuration-guide)
    - [Configuration Examples](#configuration-examples)
    - [Best Practices](#best-practices)
    - [Common Configuration Scenarios](#common-configuration-scenarios)
  - [Logging](#logging)
  - [Internal Workings](#internal-workings)
    - [Automated Tests](#automated-tests)
    - [Proxmox API](#proxmox-api)
      - [pvesh get](#pvesh-get)
      - [pvesh create/set](#pvesh-createset)
    - [Relevant Proxmox Forum Thread](#relevant-proxmox-forum-thread)
    - [Advanced Features](#advanced-features)
      - [Multiple Queries for DNS Round-Robin](#multiple-queries-for-dns-round-robin)
      - [Per-Entry DNS Server Override](#per-entry-dns-server-override)
        - [DNS Server Priority](#dns-server-priority)
        - [Special Keywords](#special-keywords)
        - [Use Cases](#use-cases)
        - [Examples](#examples)
    - [Configuration Syntax](#configuration-syntax-1)
      - [Available Options](#available-options)
      - [Examples](#examples-1)
    - [Migrating from Old to New Syntax](#migrating-from-old-to-new-syntax)
      - [Old Syntax](#old-syntax)
      - [New Syntax](#new-syntax)
      - [How to Migrate](#how-to-migrate)
    - [Troubleshooting](#troubleshooting)
      - [DNS Resolution Issues](#dns-resolution-issues)
      - [Custom DNS Server Issues](#custom-dns-server-issues)
      - [Multiple Queries Not Working](#multiple-queries-not-working)
      - [Alias References Not Being Preserved](#alias-references-not-being-preserved)

## Installation

To get the script on your Proxmox server, run the following command in your pve shell:

```bash
curl https://raw.githubusercontent.com/base23gmbh/proxmox-firewall-updater/main/update_firewall.py -o update_firewall.py \
  && install -g root -o root -m 750 ./update_firewall.py /usr/local/sbin/pve-firewall-dns-updater \
  && rm ./update_firewall.py
```

### Scheduling with Cron

You can add a cron job to run the script every 5 minutes:

```bash
(crontab -l 2>/dev/null; echo "*/5 * * * * /usr/bin/env python3 /usr/local/sbin/pve-firewall-dns-updater 2>&1 | logger -t pve-firewall-dns-updater") | crontab -
```

The cron daemon will log the execution of the script to the system log which is usually too verbose.
If you want to avoid this, you can use the scheduling explained in the next section.

### Scheduling without Cron

If you prefer to avoid verbose cron job logs, you can create a bash script with a loop that runs the python script every 5 minutes.
To activate this script, add it to the @reboot cron job:

```bash
echo "while true; do (python3 /usr/local/sbin/pve-firewall-dns-updater | logger -t pve-firewall-dns-updater); sleep 300; done" > firewall_updater_forever.sh
chmod +x firewall_updater_forever.sh
(crontab -l 2>/dev/null; echo "@reboot /bin/bash -c $(pwd)/firewall_updater_forever.sh &") | crontab -
```

Bewear that the above will take effect at every reboot.
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
- `--dns-servers`: Specify custom DNS servers to use for resolution (space-separated list). If not specified, uses system DNS servers.

You can use multiple options together, for example:

```bash
python3 update_firewall.py --ipsets --dry-run --verbose
```

You can also use this command (as root), when installed as described previously:

```bash
pve-firewall-dns-updater --ipsets --dry-run --verbose
```

In this mode, the script will print detailed logs of its intended actions for IPSets without actually making any changes.

### Custom DNS Servers

You can specify custom DNS servers to use for domain resolution instead of the system default DNS servers:

```bash
pve-firewall-dns-updater --dns-servers 8.8.8.8 1.1.1.1 --verbose
```

This is useful when:

- You want to use specific DNS servers (like Google DNS, Cloudflare DNS, etc.)
- Your system DNS configuration is not suitable for the domains you're resolving
- You need to query authoritative DNS servers directly
- You're troubleshooting DNS resolution issues

The script will try each specified DNS server in order and combine the results. If all custom DNS servers fail, it will fall back to the system DNS servers.

Examples of custom DNS server usage:

```bash
# Use Google DNS servers
pve-firewall-dns-updater --dns-servers 8.8.8.8 8.8.4.4

# Use Cloudflare DNS servers
pve-firewall-dns-updater --dns-servers 1.1.1.1 1.0.0.1

# Use multiple DNS servers for redundancy
pve-firewall-dns-updater --dns-servers 8.8.8.8 1.1.1.1 9.9.9.9

# Combine with other options
pve-firewall-dns-updater --dns-servers 8.8.8.8 1.1.1.1 --ipsets --verbose --dry-run
```

## Configuring IPSets and Aliases

This section provides a comprehensive guide to configuring DNS-based firewall rules using IPSets and Aliases.

### Understanding IPSets vs Aliases
- **IPSets**:
  - Support multiple IP addresses from multiple domains
  - Preserve special alias references (dc/, guest/)
  - Ideal for services with multiple endpoints or load-balanced services
  - Can perform multiple DNS queries to capture all IPs
  
- **Aliases**:
  - Only use the first IP address from the first domain
  - Best for single-endpoint services
  - Simpler configuration but less flexible

### Configuration Syntax
The core configuration syntax uses special comments in firewall objects:
```text
#resolve=domain1.com,domain2.com #queries=3 #delay=5 #dns-servers=8.8.8.8
```

### Step-by-Step Configuration Guide
1. **Creating an IPSet**:
   - Navigate to Datacenter → Firewall → IPSets
   - Click "Create" and enter a name
   - Add comment: `#resolve=example.com,backup.example.com #queries=3`
   - Save the IPSet

2. **Creating an Alias**:
   - Navigate to Datacenter → Firewall → Aliases
   - Click "Create" and enter a name
   - Add comment: `#resolve=api.example.com`
   - Save the Alias

### Configuration Examples
**Basic IPSet for a CDN service**:
```text
#resolve=cdn.example.com #queries=5 #delay=2
```

**Alias for a single-endpoint API**:
```text
#resolve=api.example.com
```

**IPSets with custom DNS servers**:
```text
#resolve=internal.service.com #dns-servers=192.168.1.10,192.168.1.11
```

### Best Practices
1. Use IPSets for services with multiple IPs
2. Use Aliases for simple, single-IP services
3. Always include `#queries` for load-balanced services
4. Specify `#dns-servers` for internal domains
5. Combine domains in a single IPSet when they serve the same purpose

### Common Configuration Scenarios
| Scenario | Recommended Type | Example Configuration |
|----------|------------------|----------------------|
| Load-balanced web service | IPSet | `#resolve=web.example.com #queries=3` |
| Single API endpoint | Alias | `#resolve=api.example.com` |
| Internal service with custom DNS | IPSet | `#resolve=internal.service.com #dns-servers=192.168.1.10` |
| Multi-region service | IPSet | `#resolve=us.service.com,eu.service.com` |

## Logging

The script is sending it's tog to the syslog tagged with `pve-firewall-dns-updater`.  
You can retrieve the logs by using:

```bash
journalctl -xef -t pve-firewall-dns-updater
```

## Internal Workings

### Automated Tests

This project includes comprehensive automated tests to ensure its reliability and correctness. These tests cover various scenarios and edge cases, providing a robust safety net for ongoing development.

The tests are written using Python's built-in `unittest` module, and they thoroughly test the functionality of the script, including the DNS resolution and the updating of firewall IPSets and aliases.

To run the tests, clone the repo and use the following command:

```bash
python3 -m unittest update_firewall_test.py
```

### Proxmox API

The script uses `pvesh` commands to interact with Proxmox VE firewall objects. For more details, refer to the [Proxmox VE API documentation](https://pve.proxmox.com/pve-docs/api-viewer/index.html).

#### pvesh get

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

#### pvesh create/set

Creating or updating an IPSet:

`pvesh create cluster/firewall/ipset --name ipset_example --comment "#resolve: example.com"`

Adding an entry to an IPSet:

`pvesh create cluster/firewall/ipset/ipset_example --cidr 1.2.3.4`

Updating an alias:

`pvesh set cluster/firewall/aliases/alias_example_com --cidr 1.2.3.4 --comment "#resolve: example.com"`

### Relevant Proxmox Forum Thread

For more information, check out this [Proxmox Forum thread](https://forum.proxmox.com/threads/ffirewall-alias-with-domainname.43036/) on firewall aliases with domain names.

### Advanced Features

#### Multiple Queries for DNS Round-Robin

Some domains use DNS round-robin or similar techniques to distribute load, returning different IP addresses on successive DNS queries. To capture all these IP addresses, you can configure IPSets to perform multiple DNS queries:

```text
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

#### Per-Entry DNS Server Override

You can override the DNS servers used for specific firewall entries by adding the `#dns-servers=` option to the comment. This allows fine-grained control over DNS resolution on a per-entry basis.

```text
#resolve=example.com #dns-servers=8.8.8.8,1.1.1.1
```

This configuration will:

1. Use the specified DNS servers (8.8.8.8 and 1.1.1.1) for this specific entry
2. Override any DNS servers specified via the `--dns-servers` command line option
3. Fall back to system DNS if the custom servers fail

##### DNS Server Priority

The DNS server selection follows this priority order:

1. **Comment DNS servers** (`#dns-servers=`) - highest priority
2. **CLI DNS servers** (`--dns-servers`) - medium priority  
3. **System DNS servers** - lowest priority (fallback)

##### Special Keywords

- `#dns-servers=system` - Forces the use of system DNS servers, ignoring any CLI DNS servers

##### Use Cases

This feature is particularly useful when:

- Different domains require different DNS servers (e.g., internal vs external domains)
- Some domains need authoritative DNS servers while others can use public DNS
- You want to force system DNS for specific entries while using custom DNS for others
- Troubleshooting DNS resolution issues for specific domains

##### Examples

1. **Use specific DNS servers for one entry:**

   ```text
   #resolve=internal.company.com #dns-servers=192.168.1.10,192.168.1.11
   ```

2. **Force system DNS for one entry while CLI uses custom DNS:**

   ```text
   #resolve=example.com #dns-servers=system
   ```

3. **Combine with other options:**

   ```text
   #resolve=service.com #queries=3 #delay=2 #dns-servers=8.8.8.8,1.1.1.1
   ```

4. **Multiple domains with custom DNS:**

   ```text
   #resolve=service1.com,service2.com #dns-servers=1.1.1.1,8.8.8.8
   ```

This feature works for both IPSets and Aliases, giving you maximum flexibility in DNS configuration.

### Configuration Syntax

When configuring firewall objects for DNS resolution, you can use the following comment syntax:

```text
#resolve=domain1.com,domain2.com #queries=3 #delay=5
```

#### Available Options

- `#resolve=domains`: Specifies one or more domain names (comma-separated) to resolve.
- `#queries=N`: Number of DNS queries to perform for each domain (default: 1).
- `#delay=N`: Delay in seconds between multiple queries (default: 3).
- `#dns-servers=servers`: Specifies custom DNS servers for this specific entry (comma-separated). Use `system` to force system DNS.

#### Examples

1. Basic IPSet with a single domain:

   ```text
   #resolve=example.com
   ```

2. IPSet with multiple domains:

   ```text
   #resolve=example.com,example.org
   ```

3. IPSet with multiple queries for DNS round-robin:

   ```text
   #resolve=load-balanced-service.com #queries=5 #delay=2
   ```

4. IPSet with multiple domains and custom queries:

   ```text
   #resolve=service1.com,service2.com #queries=3 #delay=1
   ```

5. Alias with a single domain (only uses first IP):

   ```text
   #resolve=example.com
   ```

> [!NOTE]
> For backward compatibility, the older syntax `#resolve:` is still supported, but the new `#resolve=` syntax is preferred for consistency.

### Migrating from Old to New Syntax

With version 3.5.0, we introduced a more consistent syntax for configuration options. While the older syntax is still supported for backward compatibility, we recommend migrating to the new syntax:

#### Old Syntax

```text
#resolve: example.com
```

#### New Syntax

```text
#resolve=example.com
```

#### How to Migrate

You can update your firewall objects in the Proxmox web interface by editing the comments:

1. Go to Datacenter → Firewall → IPSets (or Aliases)
2. Edit the comment for each object
3. Replace `#resolve: ` with `#resolve=` (remove the space after the colon)

This will make your configuration more consistent and future-proof. The old syntax will continue to work for backward compatibility, so there is no urgency to update all at once.

### Troubleshooting

#### DNS Resolution Issues

If you're having trouble with DNS resolution:

1. **Use the `--verbose` flag** to see detailed information:

   ```bash
   python3 update_firewall.py --verbose
   ```

2. **Try custom DNS servers** if system DNS is not working properly:

   ```bash
   python3 update_firewall.py --dns-servers 8.8.8.8 1.1.1.1 --verbose
   ```

3. **Try multiple queries** for domains with round-robin DNS:

   ```text
   #resolve=example.com #queries=5
   ```

4. **Verify the domain is resolvable** from your Proxmox host:

   ```bash
   nslookup example.com
   # Or test with specific DNS server
   nslookup example.com 8.8.8.8
   ```

#### Custom DNS Server Issues

If you're having trouble with custom DNS servers:

1. **Verify the DNS servers are reachable**:

   ```bash
   ping 8.8.8.8
   ```

2. **Test DNS resolution manually** with dig:

   ```bash
   dig @8.8.8.8 example.com A
   ```

3. **Check if dig is installed** (required for custom DNS servers):

   ```bash
   which dig
   # If not installed, install it:
   apt-get update && apt-get install dnsutils
   ```

4. **Try different DNS servers** if some are not responding:

   ```bash
   # Google DNS
   python3 update_firewall.py --dns-servers 8.8.8.8 8.8.4.4
   
   # Cloudflare DNS
   python3 update_firewall.py --dns-servers 1.1.1.1 1.0.0.1
   
   # Quad9 DNS
   python3 update_firewall.py --dns-servers 9.9.9.9 149.112.112.112
   ```

#### Multiple Queries Not Working

If multiple queries (`#queries=N`) aren't returning different IP addresses:

1. Verify the domain actually uses round-robin DNS or similar load balancing
2. Try increasing the delay (`#delay=10`) to allow for DNS cache timeout
3. Make sure your DNS server isn't caching responses locally

#### Alias References Not Being Preserved

If your alias references (starting with `dc/` or `guest/`) aren't being preserved:

1. Ensure you're using version 3.4.0 or higher
2. Run with `--verbose` to see if the alias references are being detected
3. Check that the alias references are properly formatted in the IPSet
