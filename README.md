# Proxmox Firewall Updater

A Python script that automates the process of updating Proxmox firewall IPSets and aliases based on DNS entries. This ensures firewall configurations remain synchronized with DNS changes, enhancing security and network management.

![Proxmox Firewall Configuration](https://github.com/simonegiacomelli/proxmox-firewall-updater/assets/3785783/85518007-756c-4804-b0a5-925b88330e02)

## Table of Contents

- [Proxmox Firewall Updater](#proxmox-firewall-updater)
  - [Table of Contents](#table-of-contents)
  - [Overview](#overview)
    - [How It Works](#how-it-works)
    - [IPSets vs Aliases](#ipsets-vs-aliases)
    - [Key Features](#key-features)
  - [Installation](#installation)
    - [Quick Install](#quick-install)
    - [Scheduling Options](#scheduling-options)
      - [Option 1: Cron (Simple)](#option-1-cron-simple)
      - [Option 2: Background Loop (Less Verbose)](#option-2-background-loop-less-verbose)
  - [Configuration](#configuration)
    - [Basic Syntax](#basic-syntax)
    - [Configuration Options](#configuration-options)
    - [Step-by-Step Setup](#step-by-step-setup)
      - [Creating an IPSet](#creating-an-ipset)
      - [Creating an Alias](#creating-an-alias)
    - [Common Configuration Examples](#common-configuration-examples)
  - [Usage](#usage)
    - [Command Line Options](#command-line-options)
    - [Usage Examples](#usage-examples)
    - [Viewing Logs](#viewing-logs)
  - [Advanced Features](#advanced-features)
    - [Multiple DNS Queries](#multiple-dns-queries)
    - [Custom DNS Servers](#custom-dns-servers)
      - [Global DNS Servers](#global-dns-servers)
      - [Per-Entry DNS Servers](#per-entry-dns-servers)
      - [DNS Server Priority](#dns-server-priority)
      - [Special Keywords](#special-keywords)
    - [Backward Compatibility](#backward-compatibility)
  - [Troubleshooting](#troubleshooting)
    - [DNS Resolution Issues](#dns-resolution-issues)
    - [Common Issues](#common-issues)
    - [DNS Server Examples](#dns-server-examples)
  - [Internal Details](#internal-details)
    - [Testing](#testing)
    - [Proxmox API Commands](#proxmox-api-commands)
      - [Retrieving Data](#retrieving-data)
      - [Updating Data](#updating-data)
    - [Resources](#resources)


## Overview

### How It Works

The script identifies firewall objects (IPSets and aliases) with special comments containing domain names, then updates them with the resolved IP addresses. Configuration is done by adding comments to firewall objects:

```text
#resolve=example.com
```

### IPSets vs Aliases

| Feature          | IPSets                                  | Aliases                                            |
| ---------------- | --------------------------------------- | -------------------------------------------------- |
| Multiple IPs     | ✅ Supports all resolved IPs            | ❌ Only first IP                                   |
| Multiple domains | ✅ Comma-separated list                 | ❌ Only first domain                               |
| Alias references | ✅ Preserves `dc/` and `guest/` entries | ❌ Not applicable                                  |
| Use case         | Load-balanced services, CDNs            | Single-endpoint APIs, re-use (reference) in IPSets |

### Key Features

- **Automatic DNS synchronization** - Updates only when IP addresses change
- **Multiple query support** - Captures all IPs from DNS round-robin
- **Custom DNS servers** - Per-entry or global DNS configuration
- **Dry-run mode** - Test changes without applying them
- **Comprehensive logging** - Detailed operation logs via syslog

## Installation

### Quick Install

```bash
curl https://raw.githubusercontent.com/base23gmbh/proxmox-firewall-updater/main/update_firewall.py -o update_firewall.py \
  && install -g root -o root -m 750 ./update_firewall.py /usr/local/sbin/pve-firewall-dns-updater \
  && rm ./update_firewall.py
```

### Scheduling Options

#### Option 1: Cron (Simple)

```bash
(crontab -l 2>/dev/null; echo "*/5 * * * * /usr/bin/env python3 /usr/local/sbin/pve-firewall-dns-updater 2>&1 | logger -t pve-firewall-dns-updater") | crontab -
```

#### Option 2: Background Loop (Less Verbose)

```bash
echo "while true; do (python3 /usr/local/sbin/pve-firewall-dns-updater | logger -t pve-firewall-dns-updater); sleep 300; done" > firewall_updater_forever.sh
chmod +x firewall_updater_forever.sh
(crontab -l 2>/dev/null; echo "@reboot /bin/bash -c $(pwd)/firewall_updater_forever.sh &") | crontab -
```

Start immediately without reboot:

```bash
/bin/bash -c ./firewall_updater_forever.sh &
```

## Configuration

### Basic Syntax

Add comments to IPSets or aliases in the Proxmox web interface:

```text
#resolve=domain1.com,domain2.com #queries=3 #delay=5 #dns-servers=8.8.8.8
```

### Configuration Options

| Option          | Data type       | Description                            | Default    | Examples                                                                                                                                                             |
| --------------- | --------------- | -------------------------------------- | ---------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `#resolve=`     | List of Strings | Domain(s) to resolve (comma-separated) | Required   | `example.com,backup.example.com`                                                                                                                                     |
| `#queries=N`    | Integer         | Number of DNS queries per domain       | `1`        | `#queries=3`                                                                                                                                                         |
| `#delay=N(.N)`  | Float           | Delay between queries (seconds)        | `3`        | `#delay=0.1`                                                                                                                                                         |
| `#dns-servers=` | List of Strings | Custom DNS servers (comma-separated)   | System DNS | - Example 1:<br />`8.8.8.8,1.1.1.1`<br /><br />- Example 2:<br />`system`<br />(system is using the system DNS servers, even when other DNS servers have been passed via the cli variable `--dns-servers`) |

### Step-by-Step Setup

#### Creating an IPSet

1. Navigate to **Datacenter → Firewall → IPSets**
2. Click **Create** and enter a name
3. Add comment: `#resolve=example.com`
4. Save the IPSet

#### Creating an Alias

1. Navigate to **Datacenter → Firewall → Aliases**
2. Click **Create** and enter a name
3. Add comment: `#resolve=api.example.com`
4. Save the Alias

### Common Configuration Examples

| Scenario              | Type  | Configuration                                                                              |
| --------------------- | ----- | ------------------------------------------------------------------------------------------ |
| Single API endpoint   | Alias | `#resolve=api.example.com`                                                                 |
| Proxmox APT Mirror    | IPSet | `#resolve=download.proxmox.com #queries=3 #delay=0.1 #dns-servers=1.1.1.1,8.8.8.8,9.9.9.9` |
| Load-balanced service | IPSet | `#resolve=web.example.com #queries=3`                                                      |
| Multi-region service  | IPSet | `#resolve=us.service.com,eu.service.com`                                                   |
| Internal service      | IPSet | `#resolve=internal.service.com #dns-servers=192.168.1.10`                                  |
| CDN with round-robin  | IPSet | `#resolve=cdn.example.com #queries=5 #delay=2`                                             |

## Usage

### Command Line Options

```bash
pve-firewall-dns-updater [OPTIONS]
```

| Option          | Description                        |
| --------------- | ---------------------------------- |
| `--dry-run`     | Show changes without applying them |
| `--verbose`     | Enable detailed logging            |
| `--ipsets`      | Update only IPSets                 |
| `--aliases`     | Update only aliases                |
| `--all`         | Update both (default)              |
| `--version`     | Show version information           |
| `--dns-servers` | Global custom DNS servers          |

### Usage Examples

```bash
# Test run with detailed output
pve-firewall-dns-updater --dry-run --verbose

# Update only IPSets with custom DNS
pve-firewall-dns-updater --ipsets --dns-servers 8.8.8.8 1.1.1.1

# Update aliases only
pve-firewall-dns-updater --aliases --verbose
```

### Viewing Logs

```bash
# Real-time logs
journalctl -xef -t pve-firewall-dns-updater

# Recent logs
journalctl -t pve-firewall-dns-updater --since "1 hour ago"
```

## Advanced Features

### Multiple DNS Queries

For services using DNS round-robin or load balancing:

```text
#resolve=load-balanced.example.com #queries=5 #delay=2
```

This performs 5 DNS queries with 2-second delays, collecting all unique IP addresses.

### Custom DNS Servers

#### Global DNS Servers

```bash
pve-firewall-dns-updater --dns-servers 8.8.8.8 1.1.1.1 9.9.9.9
```

#### Per-Entry DNS Servers

```text
#resolve=internal.company.com #dns-servers=192.168.1.10,192.168.1.11
```

#### DNS Server Priority

1. **Comment DNS servers** (`#dns-servers=`) - Highest priority
2. **CLI DNS servers** (`--dns-servers`) - Medium priority
3. **System DNS servers** - Fallback

#### Special Keywords

- `#dns-servers=system` - Force system DNS, ignore CLI options

### Backward Compatibility

The old syntax is still supported:

```text
# Old syntax (still works)
#resolve: example.com

# New syntax (preferred)
#resolve=example.com
```

## Troubleshooting

### DNS Resolution Issues

1. **Enable verbose logging:**

   ```bash
   pve-firewall-dns-updater --verbose --dry-run
   ```

2. **Test domain resolution:**

   ```bash
   nslookup example.com
   dig @8.8.8.8 example.com A
   ```

3. **Try custom DNS servers:**

   ```bash
   pve-firewall-dns-updater --dns-servers 8.8.8.8 1.1.1.1 --verbose
   ```

### Common Issues

| Problem                | Solution                                                               |
| ---------------------- | ---------------------------------------------------------------------- |
| No IP changes detected | Domain might not use round-robin; try `#queries=3`                     |
| Custom DNS not working | `dig` is required, install `dnsutils`: e.g. `apt-get install dnsutils` |
| Alias references lost  | Ensure using version 3.4.0+                                            |
| Script not running     | Check cron job and file permissions                                    |

### DNS Server Examples

```bash
# Google DNS
pve-firewall-dns-updater --dns-servers 8.8.8.8 8.8.4.4

# Cloudflare DNS
pve-firewall-dns-updater --dns-servers 1.1.1.1 1.0.0.1

# Quad9 DNS
pve-firewall-dns-updater --dns-servers 9.9.9.9 149.112.112.112
```

## Internal Details

### Testing

Run the automated test suite:

```bash
python3 -m unittest update_firewall_test.py
```

### Proxmox API Commands

#### Retrieving Data

```bash
# Get IPSets
pvesh get cluster/firewall/ipset --output-format json

# Get Aliases
pvesh get cluster/firewall/aliases --output-format json
```

#### Updating Data

```bash
# Create IPSet
pvesh create cluster/firewall/ipset --name ipset_example --comment "#resolve=example.com"

# Add IPSet entry
pvesh create cluster/firewall/ipset/ipset_example --cidr 1.2.3.4

# Update alias
pvesh set cluster/firewall/aliases/alias_example --cidr 1.2.3.4 --comment "#resolve=example.com"
```

### Resources

- [Proxmox VE API Documentation](https://pve.proxmox.com/pve-docs/api-viewer/index.html)
- [Proxmox Forum Discussion](https://forum.proxmox.com/threads/ffirewall-alias-with-domainname.43036/)
- [Original script](https://github.com/simonegiacomelli/proxmox-firewall-updater) by @simonegiacomelli

---

> **Note:** The script only updates entries when IP addresses change to minimize logging and system impact.
