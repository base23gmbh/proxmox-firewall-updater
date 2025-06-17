# Product Context: Proxmox Firewall Updater

## Problem Statement
Proxmox VE firewall configurations become outdated when external services change their IP addresses. Manual updates are time-consuming, error-prone, and don't scale in environments with many firewall rules that reference dynamic external services.

## Why This Project Exists
- **Dynamic IP Management**: External services frequently change IP addresses due to load balancing, CDN updates, or infrastructure changes
- **Security Compliance**: Firewall rules must stay current to maintain security posture
- **Operational Efficiency**: Eliminate manual firewall rule maintenance
- **Scalability**: Handle multiple domains and firewall objects automatically

## Target Users
- **Proxmox VE Administrators**: Managing virtualized infrastructure
- **Network Security Teams**: Maintaining firewall configurations
- **DevOps Engineers**: Automating infrastructure management
- **System Administrators**: Reducing manual maintenance tasks

## How It Should Work

### User Experience
1. **Setup**: Administrator configures firewall objects with domain names in comments
2. **Automation**: Script runs automatically every 5 minutes via cron
3. **Updates**: IP addresses are resolved and firewall rules updated when changes occur
4. **Monitoring**: Changes are logged for audit and troubleshooting

### Configuration Method
Users add special comments to firewall objects:
```
#resolve=example.com,backup.example.com #queries=3 #delay=5
```

### Expected Behavior
- **IPSets**: Support multiple IP addresses from multiple domains
- **Aliases**: Use first IP address from first domain only
- **Preservation**: Keep special alias references (dc/, guest/) intact
- **Efficiency**: Only update when IP addresses actually change
- **Reliability**: Handle DNS failures gracefully without clearing existing rules

## Value Proposition
- **Reduced Manual Work**: Eliminates need for manual IP address updates
- **Improved Security**: Ensures firewall rules stay current with external services
- **Better Reliability**: Automated updates reduce human error
- **Enhanced Monitoring**: Centralized logging of all firewall changes
- **Flexible Configuration**: Support for complex DNS scenarios (round-robin, multiple domains)

## Success Metrics
- Zero manual firewall IP updates required
- Firewall rules stay synchronized with external service changes
- No security incidents due to outdated firewall rules
- Reduced administrative overhead for network management
