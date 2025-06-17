# Project Brief: Proxmox Firewall Updater

## Overview
A Python utility for automatically updating Proxmox VE firewall rules by fetching IP addresses from external sources and applying them to security groups.

## Core Requirements
- Fetch IP addresses from external APIs/DNS resolution for domain names
- Update Proxmox firewall IPSets and Aliases automatically
- Support for multiple domains per firewall object
- Preserve special alias references (dc/, guest/) in IPSets
- Support multiple DNS queries for round-robin scenarios
- Provide dry-run and verbose modes for testing
- Minimize logging by only updating when IP addresses change

## Key Features
1. **DNS-based IP Resolution**: Automatically resolve domain names to IP addresses
2. **Dual Object Support**: Handle both IPSets (multiple IPs) and Aliases (single IP)
3. **Comment-based Configuration**: Use firewall object comments to specify domains to resolve
4. **Multiple Domain Support**: Support comma-separated domains in configuration
5. **Advanced Query Options**: Multiple DNS queries with configurable delays for round-robin
6. **Custom DNS Servers**: Support for specifying custom DNS servers with fallback to system DNS
7. **Alias Reference Preservation**: Keep special entries like `dc/` and `guest/` in IPSets
8. **Backward Compatibility**: Support both old (`#resolve:`) and new (`#resolve=`) syntax

## Target Environment
- Proxmox VE servers
- Python 3 environment
- Access to `pvesh` command-line tool
- Scheduled execution via cron or custom loop

## Installation Method
- Single Python script deployment
- Installed to `/usr/local/sbin/pve-firewall-dns-updater`
- Scheduled execution every 5 minutes

## Configuration Syntax
```
#resolve=domain1.com,domain2.com #queries=3 #delay=5
```

## Success Criteria
- Firewall objects automatically updated when DNS changes
- No manual intervention required for IP address changes
- Minimal system impact and logging
- Reliable operation in production Proxmox environments
