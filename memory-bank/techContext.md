# Tech Context: Proxmox Firewall Updater

## Technology Stack

### Core Language
- **Python 3**: Modern Python with type hints and dataclasses
- **Version**: Compatible with Python 3.7+ (uses `from __future__ import annotations`)
- **Standard Library**: Minimal external dependencies, uses built-in modules

### Key Python Features Used
- **Type Hints**: Full type annotation for better code quality
- **Dataclasses**: Immutable data structures with `@dataclass(frozen=True)`
- **Enums**: Type-safe enumeration with `auto()` values
- **Union Types**: Modern `str | None` syntax for optional types
- **Context Managers**: Proper resource handling

### Standard Library Modules
```python
import argparse      # Command-line argument parsing
import json         # JSON data handling for Proxmox API responses
import shlex        # Safe shell command construction
import socket       # DNS resolution via gethostbyname_ex
import subprocess   # External command execution (pvesh)
import time         # Delays between DNS queries
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path
from typing import List, Dict
```

## External Dependencies

### Proxmox VE Integration
- **pvesh command**: Proxmox VE shell for API access
- **Required access**: Root or equivalent permissions for firewall management
- **API endpoints used**:
  - `cluster/firewall/ipset` - IPSet management
  - `cluster/firewall/aliases` - Alias management

### System Requirements
- **Operating System**: Linux (Proxmox VE host)
- **Python**: Version 3.7 or higher
- **Network**: DNS resolution capability
- **Permissions**: Root access for firewall modifications

## Development Setup

### File Structure
```
proxmox-firewall-updater/
├── update_firewall.py      # Main script
├── update_firewall_test.py # Comprehensive test suite
├── README.md              # Documentation
├── LICENSE                # MIT License
├── .gitignore            # Git ignore rules
└── memory-bank/          # Memory bank documentation
```

### Testing Framework
- **unittest**: Python's built-in testing framework
- **Comprehensive coverage**: 15+ test cases covering all scenarios
- **Mock implementation**: `DependenciesFake` for isolated testing
- **Test scenarios**:
  - Multiple domains and IPs
  - DNS round-robin with multiple queries
  - Alias reference preservation
  - Backward compatibility
  - Error handling

### Code Quality Standards
- **Type hints**: Full type annotation throughout
- **Immutable data**: Frozen dataclasses for data integrity
- **Clean architecture**: Dependency injection for testability
- **Error handling**: Graceful degradation on failures
- **Logging**: Comprehensive logging for operations

## Deployment Architecture

### Installation Method
```bash
# Download and install
curl https://raw.githubusercontent.com/base23gmbh/proxmox-firewall-updater/main/update_firewall.py -o update_firewall.py
install -g root -o root -m 750 ./update_firewall.py /usr/local/sbin/pve-firewall-dns-updater
```

### Execution Patterns
1. **Cron-based scheduling**:
   ```bash
   */5 * * * * /usr/bin/env python3 /usr/local/sbin/pve-firewall-dns-updater 2>&1 | logger -t pve-firewall-dns-updater
   ```

2. **Loop-based scheduling** (alternative):
   ```bash
   while true; do 
     (python3 /usr/local/sbin/pve-firewall-dns-updater | logger -t pve-firewall-dns-updater)
     sleep 300
   done
   ```

### Command Line Interface
```bash
pve-firewall-dns-updater [OPTIONS]

Options:
  --dry-run         # Preview changes without execution
  --verbose         # Detailed logging
  --ipsets          # Process IPSets only
  --aliases         # Process Aliases only
  --all             # Process both (default)
  --version         # Show version information
  --dns-servers     # Custom DNS servers (space-separated list)
```

### Custom DNS Server Support
- **dig command integration**: Uses `dig` for custom DNS server queries
- **Fallback mechanism**: Falls back to system DNS if custom servers fail
- **Multiple server support**: Can specify multiple DNS servers for redundancy
- **Validation**: Validates IP address format from DNS responses
- **Error handling**: Graceful handling of DNS server failures

## Technical Constraints

### Proxmox API Limitations
- **pvesh commands**: Must use subprocess calls, no direct API library
- **JSON parsing**: Manual parsing of pvesh JSON output
- **Error handling**: Limited error information from pvesh commands
- **Atomic operations**: Each IP add/remove is separate pvesh call

### DNS Resolution Constraints
- **Standard library only**: Uses `socket.gethostbyname_ex()`
- **No advanced DNS features**: No custom DNS servers or record types
- **IPv4 only**: Current implementation focuses on IPv4 addresses
- **Timeout handling**: Limited control over DNS timeouts

### Performance Considerations
- **Sequential processing**: DNS queries and firewall updates are sequential
- **Rate limiting**: Configurable delays between DNS queries
- **Minimal caching**: No DNS result caching between runs
- **Log volume**: Verbose mode can generate significant logs

## Security Considerations
- **Root privileges**: Requires root access for firewall modifications
- **Command injection**: Uses `shlex` for safe command construction
- **Input validation**: Validates domain names and configuration options
- **Logging**: Sensitive information handling in logs

## Version Management
- **Current version**: 3.5.0
- **Version string**: Embedded in script for tracking
- **Backward compatibility**: Maintains support for legacy syntax
- **Migration path**: Clear upgrade instructions in documentation
