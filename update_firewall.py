#!/usr/bin/env python3
# for more information see https://github.com/base23gmbh/proxmox-firewall-updater

from __future__ import annotations

import argparse
import json
import shlex
import socket
import subprocess
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path
from typing import List, Dict

VERSION_STRING = f'{Path(__file__).name} version 3.5.0'


class FirewallObjectType(Enum):
    """Enum for different types of firewall objects."""
    IPSET = auto()
    ALIAS = auto()


@dataclass(frozen=True)
class FirewallEntry:
    """Base class for firewall entries that can be resolved via DNS."""
    name: str
    cidr: str
    comment: str | None
    obj_type: FirewallObjectType

    def domains(self) -> List[str]:
        """Extract domain(s) from comment if it contains #resolve= directive.
        
        Returns:
            A list of domain names to resolve. For aliases, only the first domain is used.
            For IPSets, multiple comma-separated domains can be specified.
        """
        try:
            # Try the new style #resolve= (preferred)
            if self.comment and '#resolve=' in self.comment:
                res = self.comment.split('#resolve=')[1].split(' ')[0]
                if res:
                    # Split by comma to support multiple domains
                    domains = [domain.strip() for domain in res.split(',')]
                    return [domain for domain in domains if domain]  # Filter out empty domains
            
            # Fallback to legacy #resolve: style for backward compatibility
            elif self.comment and '#resolve:' in self.comment:
                res = self.comment.split('#resolve: ')[1].split(' ')[0]
                if res:
                    # Split by comma to support multiple domains
                    domains = [domain.strip() for domain in res.split(',')]
                    return [domain for domain in domains if domain]  # Filter out empty domains
                
            return []
        except:
            return []
            
    def get_resolve_options(self) -> dict:
        """Extract resolve options from comment.
        
        Comment format can include options:
        #resolve=domain1.com,domain2.com #queries=3 #delay=5
        
        Returns:
            Dictionary with the following keys:
            - queries: Number of times to query each domain (default: 1)
            - delay: Delay in seconds between queries (default: 3)
        """
        options = {
            'queries': 1,  # Default to 1 query
            'delay': 3     # Default to 3 seconds delay
        }
        
        try:
            if not self.comment:
                return options
                
            # Look for #queries= option
            if '#queries=' in self.comment:
                queries_str = self.comment.split('#queries=')[1].split(' ')[0]
                try:
                    queries = int(queries_str)
                    if queries > 0:
                        options['queries'] = queries
                except ValueError:
                    pass
            
            # Look for #delay= option
            if '#delay=' in self.comment:
                delay_str = self.comment.split('#delay=')[1].split(' ')[0]
                try:
                    delay = float(delay_str)
                    if delay > 0:
                        options['delay'] = delay
                except ValueError:
                    pass
                    
        except:
            pass
            
        return options
            
    def domain(self) -> str | None:
        """Legacy method for backward compatibility. Returns the first domain or None."""
        domains = self.domains()
        return domains[0] if domains else None


class Dependencies:
    """Interface for managing actions on Proxmox firewall objects and DNS entries."""

    def __init__(self):
        self.verbose = True
        self.dry_run = True

    def list_entries(self, obj_type: FirewallObjectType) -> List[FirewallEntry]:
        """List all entries of the specified type."""
        ...

    def set_entry(self, entry: FirewallEntry):
        """Add or update an entry."""
        ...

    def delete_entry(self, entry: FirewallEntry):
        """Delete an entry."""
        ...

    def get_object_entries(self, obj_type: FirewallObjectType, name: str) -> List[str]:
        """Get all CIDRs for a specific IPSet or Alias."""
        ...

    def dns_resolve(self, domain: str, queries: int = 1, delay: float = 3.0) -> List[str]:
        """Resolve a domain to a list of IP addresses.
        
        Args:
            domain: The domain to resolve
            queries: Number of times to query the domain
            delay: Delay in seconds between queries
        
        Returns:
            A list of IP addresses from all queries combined
        """
        ...


def log(msg):
    """Print a log message to stdout."""
    print(msg)


class Run:
    """Wrapper for subprocess execution."""
    def __init__(self, cmd, cwd=None):
        self.cmd = cmd
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=cwd)
        self.returncode = res.returncode
        self.success = res.returncode == 0
        self.stdout = res.stdout.decode("utf-8")
        self.stderr = res.stderr.decode("utf-8")

    def __str__(self):
        st = 'OK' if self.success else f'FAILED status={self.returncode}'
        return \
            f'command={shlex.join(self.cmd)}\n' \
            f'status={st}\n' \
            f'stdout: ------------------------------\n' \
            f'{self.stdout}\n' \
            f'stderr: ------------------------------\n' \
            f'{self.stderr}' \
            f'end ----------------------------------\n'


def parse_entries_from_json(json_str: str, obj_type: FirewallObjectType) -> List[FirewallEntry]:
    """Convert JSON response to a list of FirewallEntry objects."""
    j = json.loads(json_str)
    result = []
    
    for obj in j:
        # Get object level comment and name
        name = obj['name']
        comment = obj.get('comment', None)
        
        # Check if the object has entries field (detailed query for IPSets)
        if 'entries' in obj and obj_type == FirewallObjectType.IPSET:
            # Process entries if they exist
            entries = obj.get('entries', [])
            for entry in entries:
                result.append(FirewallEntry(
                    name=name,
                    cidr=entry.get('cidr', ''),
                    comment=comment,
                    obj_type=obj_type
                ))
        else:
            # Handle direct entries (aliases) or top-level IPSet info
            result.append(FirewallEntry(
                name=name,
                cidr=obj.get('cidr', ''),
                comment=comment,
                obj_type=obj_type
            ))
    
    return result


def update_firewall_objects(deps: Dependencies, obj_type: FirewallObjectType):
    """Update firewall objects of the specified type based on DNS resolution."""
    type_name = "IPSet" if obj_type == FirewallObjectType.IPSET else "Alias"
    
    if deps.verbose:
        log(f"Processing {type_name}s...")
    
    # Get entries with domain info
    entries = [entry for entry in deps.list_entries(obj_type) if entry.domains()]
    
    if deps.verbose:
        log(f'Found {len(entries)} {type_name.lower()} entries to check. dry-run={deps.dry_run}')
        for entry in entries:
            domains_str = ','.join(entry.domains())
            log(f'  {entry.name} {domains_str} cidr={entry.cidr} {entry.comment}')
    
    for entry in entries:
        domains = entry.domains()
        
        if obj_type == FirewallObjectType.IPSET:
            # For IPSets, collect IPs from all domains
            all_dns_ips = []
            
            # Get the resolve options for this entry
            options = entry.get_resolve_options()
            queries = options['queries']
            delay = options['delay']
            
            if queries > 1 and deps.verbose:
                log(f'Will perform {queries} queries for each domain with {delay} seconds delay')
                
            # Resolve each domain and collect all unique IPs
            for domain in domains:
                dns_ips = deps.dns_resolve(domain, queries=queries, delay=delay)
                if dns_ips:
                    if deps.verbose and queries <= 1:
                        log(f'Domain {domain} resolved to {len(dns_ips)} IP(s): {dns_ips}')
                    all_dns_ips.extend(dns_ips)
                else:
                    if deps.verbose:
                        log(f'Cannot resolve domain `{domain}` for {type_name} `{entry.name}`')
            
            # Remove duplicates while preserving order
            unique_dns_ips = []
            for ip in all_dns_ips:
                if ip not in unique_dns_ips:
                    unique_dns_ips.append(ip)
            
            if unique_dns_ips:
                # Get current entries in the IPSet
                current_ips = deps.get_object_entries(obj_type, entry.name)
                
                if deps.verbose:
                    log(f'{type_name} {entry.name} has {len(current_ips)} entries, DNS returned {len(unique_dns_ips)} unique addresses')
                
                # Identify special alias reference entries that should be preserved
                alias_refs = [ip for ip in current_ips if ip.startswith("dc/") or ip.startswith("guest/")]
                if alias_refs and deps.verbose:
                    log(f'Found {len(alias_refs)} alias references that will be preserved: {alias_refs}')
                
                # Find addresses to add (in DNS but not in IPSet)
                to_add = [ip for ip in unique_dns_ips if ip not in current_ips]
                
                # Find addresses to remove (in IPSet but not in DNS)
                # Exclude alias reference entries (starting with dc/ or guest/)
                to_remove = [ip for ip in current_ips if ip not in unique_dns_ips and not (ip.startswith("dc/") or ip.startswith("guest/"))]
                
                # Update IPSet with changes
                if to_add or to_remove:
                    log(f'Updating {type_name} {entry.name}:')
                    
                    # Remove old entries
                    for ip in to_remove:
                        log(f'  Removing {ip}')
                        if not deps.dry_run:
                            deps.delete_entry(FirewallEntry(
                                name=entry.name, 
                                cidr=ip, 
                                comment=entry.comment,
                                obj_type=obj_type
                            ))
                    
                    # Add new entries
                    for ip in to_add:
                        log(f'  Adding {ip}')
                        if not deps.dry_run:
                            deps.set_entry(FirewallEntry(
                                name=entry.name, 
                                cidr=ip, 
                                comment=entry.comment,
                                obj_type=obj_type
                            ))
                else:
                    if deps.verbose:
                        log(f'{type_name} {entry.name} is up to date with DNS entries')
            elif deps.verbose:
                log(f'No IP addresses could be resolved for any domains in {type_name} `{entry.name}`')
                
        else:  # Alias objects only support a single IP and single domain
            # For Aliases, use only the first domain and its first IP address
            domain = domains[0]
            dns_ips = deps.dns_resolve(domain)
            
            if dns_ips:
                # For Aliases, use the first IP address only
                ip = dns_ips[0]
                if ip != entry.cidr:
                    log(f'Updating {type_name} {entry.name} from {entry.cidr} to {ip}')
                    if not deps.dry_run:
                        deps.set_entry(FirewallEntry(
                            name=entry.name, 
                            cidr=ip, 
                            comment=entry.comment,
                            obj_type=obj_type
                        ))
                else:
                    if deps.verbose:
                        log(f'{type_name} {entry.name} is already up to date with {ip} from {domain}')
            else:
                if deps.verbose:
                    log(f'Cannot resolve domain `{domain}` for {type_name} `{entry.name}`')


class ProdDependencies(Dependencies):
    """Production implementation of Dependencies interface."""
    
    def __init__(self, args):
        super().__init__()
        self.verbose = args.verbose
        self.dry_run = args.dry_run
    
    def list_entries(self, obj_type: FirewallObjectType) -> List[FirewallEntry]:
        """List all entries of the specified type."""
        endpoint = 'ipset' if obj_type == FirewallObjectType.IPSET else 'aliases'
        cmd = f'pvesh get cluster/firewall/{endpoint} --output-format json'.split(' ')
        run = self._run(cmd, skip=False)
        if not run.success:
            return []
        return parse_entries_from_json(run.stdout, obj_type)
    
    def set_entry(self, entry: FirewallEntry):
        """Add or update an entry."""
        if entry.obj_type == FirewallObjectType.IPSET:
            # For IPSets
            # Add the entry
            cmd = f'pvesh create cluster/firewall/ipset/{entry.name} --cidr {entry.cidr}'.split(' ')
            self._run(cmd, skip=self.dry_run)
        else:
            # For Aliases
            cmd = f'pvesh set cluster/firewall/aliases/{entry.name} --cidr {entry.cidr}'.split(' ')
            if entry.comment:
                cmd += ['--comment', entry.comment]
            self._run(cmd, skip=self.dry_run)
    
    def delete_entry(self, entry: FirewallEntry):
        """Delete an entry."""
        if entry.obj_type == FirewallObjectType.IPSET:
            cmd = f'pvesh delete cluster/firewall/ipset/{entry.name}/{entry.cidr}'.split(' ')
            self._run(cmd, skip=self.dry_run)
        else:
            # Note: Aliases don't have separate entries to delete,
            # you would update the entire alias instead
            pass
    
    def get_object_entries(self, obj_type: FirewallObjectType, name: str) -> List[str]:
        """Get all CIDRs for a specific IPSet or Alias."""
        if obj_type == FirewallObjectType.IPSET:
            cmd = f'pvesh get cluster/firewall/ipset/{name} --output-format json'.split(' ')
            run = self._run(cmd, skip=False)
            if not run.success:
                return []
            entries = json.loads(run.stdout)
            return [entry.get('cidr', '') for entry in entries]
        else:
            # Aliases only have one CIDR
            cmd = f'pvesh get cluster/firewall/aliases/{name} --output-format json'.split(' ')
            run = self._run(cmd, skip=False)
            if not run.success:
                return []
            obj = json.loads(run.stdout)
            return [obj.get('cidr', '')]
    
    def dns_resolve(self, domain: str, queries: int = 1, delay: float = 3.0) -> List[str]:
        """Resolve a domain to a list of IP addresses.
        
        Args:
            domain: The domain to resolve
            queries: Number of times to query the domain
            delay: Delay in seconds between queries
            
        Returns:
            A list of IP addresses from all queries combined
        """
        all_ips = []
        
        for i in range(queries):
            if i > 0 and delay > 0:
                if self.verbose:
                    log(f'Waiting {delay} seconds before next query for {domain}...')
                import time
                time.sleep(delay)
                
            try:
                (_, _, ipaddrlist) = socket.gethostbyname_ex(domain)
                if self.verbose:
                    log(f'Query {i+1}/{queries}: {domain} resolved to {ipaddrlist}')
                all_ips.extend(ipaddrlist)
            except Exception as e:
                if self.verbose:
                    log(f'Query {i+1}/{queries}: Failed to resolve {domain}: {str(e)}')
        
        # Remove duplicates while preserving order
        unique_ips = []
        for ip in all_ips:
            if ip not in unique_ips:
                unique_ips.append(ip)
                
        if self.verbose and queries > 1:
            log(f'All queries for {domain} returned {len(all_ips)} IPs, {len(unique_ips)} unique: {unique_ips}')
            
        return unique_ips
    
    def _run(self, cmd, skip: bool) -> Run | None:
        """Run a command and return the result."""
        if self.verbose and skip:
            log(f'dry-run: {shlex.join(cmd)}')
        if not skip:
            run = Run(cmd)
            if self.verbose:
                log(str(run))
            return run


def main():
    parser = argparse.ArgumentParser(description='Update Proxmox firewall IPSet and Alias entries using DNS resolution.')
    parser.add_argument('--dry-run', action='store_true', help='run the script without making any changes')
    parser.add_argument('--verbose', action='store_true', help='print detailed operations information')
    parser.add_argument('--ipsets', action='store_true', help='update IPSet entries')
    parser.add_argument('--aliases', action='store_true', help='update Alias entries')
    parser.add_argument('--all', action='store_true', help='update both IPSet and Alias entries')
    parser.add_argument('--version', action='store_true', help='show version information and exit')
    
    args = parser.parse_args()
    
    if args.version:
        log(VERSION_STRING)
        return
    
    deps = ProdDependencies(args)
    
    if args.verbose:
        log(VERSION_STRING)
    
    # If no specific option is provided, default to --all
    if not (args.ipsets or args.aliases or args.all):
        args.all = True
    
    if args.ipsets or args.all:
        update_firewall_objects(deps, FirewallObjectType.IPSET)
    
    if args.aliases or args.all:
        update_firewall_objects(deps, FirewallObjectType.ALIAS)


if __name__ == '__main__':
    main()
