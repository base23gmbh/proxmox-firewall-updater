# Active Context: Proxmox Firewall Updater

## Current Work Focus
**DNS Server Override Feature Complete**: Successfully implemented and tested the per-entry DNS server override feature for the Proxmox Firewall Updater project. This mature, production-ready Python utility (version 3.6.0) now supports custom DNS servers per firewall entry via the `#dns-servers=` comment option.

## Recent Changes
- **DNS Server Override Feature**: Added `#dns-servers=` comment option for per-entry DNS server configuration
- **Priority System**: Implemented DNS server priority (comment > CLI > system)
- **System DNS Override**: Added `#dns-servers=system` keyword to force system DNS
- **Comprehensive Testing**: Added 8 new test cases covering all DNS server override scenarios
- **Documentation Update**: Enhanced README with detailed DNS server override examples and use cases
- **Version Bump**: Updated to version 3.6.0 to reflect new functionality

## Next Steps
1. **Memory Bank Complete**: All memory bank files are now accurate and up-to-date
2. **Ready for Tasks**: Memory bank is ready for any future development, maintenance, or enhancement tasks
3. **No Active Development**: Project is stable and feature-complete

## Active Decisions and Considerations

### Project Maturity
- **Production Ready**: Version 3.5.0 with comprehensive features
- **Well Tested**: Extensive test suite with 15+ test cases
- **Clean Architecture**: Proper separation of concerns with dependency injection
- **Backward Compatible**: Supports both legacy and new configuration syntax

### Key Implementation Insights
- **Comment-based Configuration**: Firewall objects configured via special comments
- **Dual Object Support**: IPSets (multiple IPs) vs Aliases (single IP)
- **DNS Round-robin Support**: Multiple queries with configurable delays
- **Alias Reference Preservation**: Special handling for `dc/` and `guest/` entries
- **Minimal Update Strategy**: Only changes what's actually different

### Important Patterns and Preferences
- **Type Safety**: Full type hints throughout codebase
- **Immutable Data**: Frozen dataclasses for data integrity
- **Dependency Injection**: Clean separation for testability
- **Error Resilience**: Graceful handling of DNS and command failures
- **Comprehensive Logging**: Detailed logging for operations and troubleshooting

### Configuration Syntax Understanding
```
# New preferred syntax
#resolve=domain1.com,domain2.com #queries=3 #delay=5

# Legacy syntax (still supported)
#resolve: domain1.com,domain2.com
```

### Critical Behavioral Differences
- **IPSets**: Support multiple domains, multiple IPs, preserve alias references
- **Aliases**: Use first domain only, first IP only, no special preservation
- **DNS Failures**: Don't clear existing entries, continue with other objects
- **Special Entries**: Preserve `dc/` and `guest/` prefixed entries in IPSets

## Learnings and Project Insights
- **Single File Design**: Entire functionality in one deployable script
- **Standard Library Focus**: Minimal external dependencies for reliability
- **Proxmox Integration**: Uses `pvesh` commands for all firewall operations
- **Production Deployment**: Installed as system command with cron scheduling
- **Comprehensive Testing**: Mock implementation enables thorough unit testing

## Current Project State
- **Stable and Complete**: No active development needed
- **Well Documented**: Comprehensive README with examples and troubleshooting
- **Memory Bank Initialized**: Ready for future maintenance or enhancement tasks
