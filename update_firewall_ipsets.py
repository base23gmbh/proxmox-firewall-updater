#!/usr/bin/env python3
# for more information see https://github.com/simonegiacomelli/proxmox-firewall-updater

from __future__ import annotations

import argparse
import json
import shlex
import socket
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import List

VERSION_STRING = f'{Path(__file__).name} version 3.0.0'


@dataclass(frozen=True)
class IPSetEntry:
    name: str
    cidr: str
    comment: str | None

    def domain(self) -> str | None:
        try:
            res = self.comment.split('#resolve: ')[1].split(' ')[0]
            if len(res) > 0:
                return res
        except:
            return None


class Dependencies:
    """Interface for managing actions on pve firewall ipsets and dns entries."""

    def __init__(self):
        self.verbose = True
        self.dry_run = True

    def ipset_list(self) -> List[IPSetEntry]: ...

    def ipset_set(self, entry: IPSetEntry): ...
    
    def ipset_delete(self, entry: IPSetEntry): ...

    def get_ipset_entries(self, ipset_name: str) -> List[str]: ...

    def dns_resolve(self, domain: str) -> List[str]: ...


def update_ipsets(deps: Dependencies):
    if deps.verbose:
        log(VERSION_STRING)

    entries = [entry for entry in deps.ipset_list() if entry.domain() is not None]

    if deps.verbose:
        log(f'found {len(entries)} ipset entries to check. dry-run={deps.dry_run}')
        for ipset_entry in entries:
            log(f'  {ipset_entry.name} {ipset_entry.domain()} cidr={ipset_entry.cidr} {ipset_entry.comment}')

    for ipset_entry in entries:
        # Get all IP addresses from DNS
        dns_ips = deps.dns_resolve(ipset_entry.domain())
        
        if dns_ips:
            # Get current entries in the IPSet
            current_ips = deps.get_ipset_entries(ipset_entry.name)
            
            if deps.verbose:
                log(f'IPSet {ipset_entry.name} has {len(current_ips)} entries, DNS returned {len(dns_ips)} addresses')
                
            # Find addresses to add (in DNS but not in IPSet)
            to_add = [ip for ip in dns_ips if ip not in current_ips]
            
            # Find addresses to remove (in IPSet but not in DNS)
            to_remove = [ip for ip in current_ips if ip not in dns_ips]
            
            # Update IPSet with changes
            if to_add or to_remove:
                log(f'Updating IPSet {ipset_entry.name}:')
                
                # Remove old entries
                for ip in to_remove:
                    log(f'  Removing {ip}')
                    if not deps.dry_run:
                        deps.ipset_delete(IPSetEntry(name=ipset_entry.name, cidr=ip, comment=ipset_entry.comment))
                
                # Add new entries
                for ip in to_add:
                    log(f'  Adding {ip}')
                    if not deps.dry_run:
                        deps.ipset_set(IPSetEntry(name=ipset_entry.name, cidr=ip, comment=ipset_entry.comment))
            else:
                if deps.verbose:
                    log(f'IPSet {ipset_entry.name} is up to date with DNS entries')
        else:
            if deps.verbose:
                log(f'Cannot resolve domain `{ipset_entry.domain()}` for IPSet `{ipset_entry.name}`')


def log(msg):
    print(msg)


class Run:
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


def ipset_list_to_typed(ipset_list: str) -> List[IPSetEntry]:
    j = json.loads(ipset_list)
    result = []
    for ipset in j:
        # Get the IPSet level comment and name
        name = ipset['name']
        comment = ipset.get('comment', None)

        # Check if the IPSet has entries field (detailed query)
        if 'entries' in ipset:
            # Process entries if they exist
            entries = ipset.get('entries', [])
            for entry in entries:
                result.append(IPSetEntry(
                    name=name,
                    cidr=entry.get('cidr', ''),
                    comment=comment  # Use the IPSet level comment
                ))
        else:
            # If no entries field, create an IPSetEntry with the top-level info
            # This handles the case where we only have the IPSet overview
            # We'll populate with an empty cidr which will be updated later if needed
            result.append(IPSetEntry(
                name=name,
                cidr=ipset.get('cidr', ''),  # Try to get cidr from top level if available
                comment=comment
            ))
    return result


class ProdDependencies(Dependencies):

    def __init__(self, args):
        super().__init__()
        self.verbose = args.verbose
        self.dry_run = args.dry_run

    def ipset_list(self) -> List[IPSetEntry]:
        cmd = f'pvesh get cluster/firewall/ipset --output-format json'.split(' ')
        run = self._run(cmd, skip=False)
        if not run.success:
            return []
        else:
            return ipset_list_to_typed(run.stdout)

    def get_ipset_entries(self, ipset_name: str) -> List[str]:
        cmd = f'pvesh get cluster/firewall/ipset/{ipset_name} --output-format json'.split(' ')
        run = self._run(cmd, skip=False)
        if not run.success:
            return []
        else:
            entries = json.loads(run.stdout)
            return [entry.get('cidr', '') for entry in entries]

    def ipset_delete(self, entry: IPSetEntry):
        cmd = f'pvesh delete cluster/firewall/ipset/{entry.name}/{entry.cidr}'.split(' ')
        self._run(cmd, skip=self.dry_run)

    def ipset_set(self, entry: IPSetEntry):
        # Then add/update the entry
        cmd = f'pvesh create cluster/firewall/ipset/{entry.name} --cidr {entry.cidr}'.split(' ')
        self._run(cmd, skip=self.dry_run)

    def dns_resolve(self, domain: str) -> List[str]:
        try:
            (_, _, ipaddrlist) = socket.gethostbyname_ex(domain)
            if self.verbose:
                log(f'{domain} resolved to `{ipaddrlist}`')
            return ipaddrlist
        except:
            return []

    def _run(self, cmd, skip: bool) -> Run | None:
        if self.verbose and skip:
            log(f'dry-run: {shlex.join(cmd)}')
        if not skip:
            run = Run(cmd)
            if self.verbose:
                log(str(run))
            return run


def main():
    parser = argparse.ArgumentParser(description='Update firewall ipset entries.')
    parser.add_argument('--dry-run', action='store_true', help='run the script without making any changes')
    parser.add_argument('--verbose', action='store_true', help='print detailed operations information')

    args = parser.parse_args()
    update_ipsets(ProdDependencies(args))


if __name__ == '__main__':
    main()
