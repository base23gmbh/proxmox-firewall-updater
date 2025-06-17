# System Patterns: Proxmox Firewall Updater

## Architecture Overview
Single-file Python script with clean separation of concerns through dependency injection and object-oriented design.

## Core Design Patterns

### 1. Dependency Injection Pattern
- **Dependencies Interface**: Abstract base class defining all external operations
- **ProdDependencies**: Production implementation using actual Proxmox commands
- **DependenciesFake**: Test implementation for unit testing
- **Benefits**: Testability, modularity, easy mocking

### 2. Data Class Pattern
- **FirewallEntry**: Immutable dataclass representing firewall objects
- **Frozen dataclass**: Ensures immutability and hashability
- **Rich behavior**: Methods for domain extraction and option parsing

### 3. Enum Pattern
- **FirewallObjectType**: Type-safe enumeration for IPSET vs ALIAS
- **Auto-generated values**: Using `auto()` for maintainability

### 4. Command Pattern
- **Run class**: Encapsulates subprocess execution with result handling
- **Consistent interface**: Standardized command execution and logging

## Key Components

### FirewallEntry Class
```python
@dataclass(frozen=True)
class FirewallEntry:
    name: str
    cidr: str
    comment: str | None
    obj_type: FirewallObjectType
```

**Key Methods:**
- `domains()`: Extract domain list from comment
- `get_resolve_options()`: Parse configuration options
- `domain()`: Legacy single-domain support

### Dependencies Interface
**Core Operations:**
- `list_entries()`: Retrieve firewall objects
- `set_entry()`: Create/update firewall entries
- `delete_entry()`: Remove firewall entries
- `get_object_entries()`: Get all IPs for an object
- `dns_resolve()`: Resolve domains with multiple query support and custom DNS servers

**DNS Resolution Features:**
- Multiple query support for round-robin DNS
- Configurable delays between queries
- Custom DNS server support via `dig` command
- Fallback to system DNS on custom server failure
- IP address validation for DNS responses

### Update Logic Flow
1. **Discovery**: List all firewall objects with resolve comments
2. **Resolution**: Resolve domains to IP addresses (with multiple queries if configured)
3. **Comparison**: Compare current IPs with resolved IPs
4. **Preservation**: Keep special alias references (dc/, guest/)
5. **Update**: Add new IPs and remove outdated ones
6. **Logging**: Report all changes

## Critical Implementation Patterns

### Comment Parsing Strategy
- **Dual syntax support**: `#resolve:` (legacy) and `#resolve=` (preferred)
- **Multiple domains**: Comma-separated domain lists
- **Option parsing**: Extract `#queries=N` and `#delay=N` parameters
- **Error resilience**: Graceful handling of malformed comments

### DNS Resolution Strategy
- **Multiple queries**: Support for round-robin DNS scenarios
- **Delay configuration**: Configurable delays between queries
- **Custom DNS servers**: Support for specifying custom DNS servers
- **Fallback mechanism**: Falls back to system DNS if custom servers fail
- **Deduplication**: Remove duplicate IPs while preserving order
- **Error handling**: Continue operation on DNS failures
- **IP validation**: Validates DNS responses to ensure valid IP addresses

### IPSet vs Alias Handling
**IPSets:**
- Support multiple IP addresses
- Support multiple domains
- Preserve alias references (dc/, guest/)
- Support multiple DNS queries

**Aliases:**
- Single IP address only
- Use first domain only
- Use first IP from DNS resolution
- No special reference preservation

### State Management
- **Minimal updates**: Only change what's different
- **Preservation logic**: Keep non-DNS entries in IPSets
- **Atomic operations**: Each IP add/remove is separate operation
- **Dry-run support**: Preview changes without execution

## Error Handling Patterns
- **Graceful degradation**: Continue on individual DNS failures
- **Command failure handling**: Log and continue on pvesh command failures
- **Validation**: Input validation for domains and options
- **Logging**: Comprehensive logging for troubleshooting

## Testing Patterns
- **Fake dependencies**: Complete mock implementation for testing
- **Comprehensive scenarios**: Test multiple domains, queries, alias preservation
- **Edge cases**: Empty DNS results, malformed comments, network failures
- **Backward compatibility**: Test both old and new syntax formats
