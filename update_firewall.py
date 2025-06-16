#!/usr/bin/env python3
from __future__ import annotations

import unittest
from typing import Dict, List

from update_firewall import FirewallEntry, FirewallObjectType, Dependencies, update_firewall_objects, parse_entries_from_json


class UpdateFirewallObjectsTestCase(unittest.TestCase):

    def setUp(self) -> None:
        self.deps = DependenciesFake()

    def tearDown(self) -> None:
        pass

    # IPSet Tests
    def test_ipset_multiple_ips_should_add_and_remove_correctly(self):
        # GIVEN
        # Initial IPSet has two IPs
        self.deps.set_entry(FirewallEntry(name='ipset1', cidr='192.168.1.1', comment='#resolve: example.com', obj_type=FirewallObjectType.IPSET))
        self.deps.set_entry(FirewallEntry(name='ipset1', cidr='192.168.1.2', comment='#resolve: example.com', obj_type=FirewallObjectType.IPSET))
        
        # DNS returns different set of IPs - one to keep, one to remove, one to add
        self.deps.dns_entries['example.com'] = ['192.168.1.1', '192.168.1.3']

        # WHEN
        update_firewall_objects(self.deps, FirewallObjectType.IPSET)

        # THEN
        # Should keep 192.168.1.1, remove 192.168.1.2, and add 192.168.1.3
        expected_ips = ['192.168.1.1', '192.168.1.3']
        self.assertEqual(sorted(expected_ips), sorted(self.deps.object_content[FirewallObjectType.IPSET]['ipset1']))

    def test_ipset_empty_dns_results_should_not_clear_ipset(self):
        # GIVEN
        # IPSet has entries
        self.deps.set_entry(FirewallEntry(name='ipset1', cidr='192.168.1.1', comment='#resolve: example.com', obj_type=FirewallObjectType.IPSET))
        self.deps.set_entry(FirewallEntry(name='ipset1', cidr='192.168.1.2', comment='#resolve: example.com', obj_type=FirewallObjectType.IPSET))
        
        # DNS returns empty list (could happen on temporary DNS failure)
        self.deps.dns_entries['example.com'] = []

        # WHEN
        update_firewall_objects(self.deps, FirewallObjectType.IPSET)

        # THEN
        # Should keep the existing IPs
        expected_ips = ['192.168.1.1', '192.168.1.2']
        self.assertEqual(sorted(expected_ips), sorted(self.deps.object_content[FirewallObjectType.IPSET]['ipset1']))

    def test_ipset_multiple_domains_should_combine_ips(self):
        # GIVEN
        # IPSet with multiple domains in the comment
        self.deps.set_entry(FirewallEntry(
            name='ipset_multi_domain', 
            cidr='192.168.1.1', 
            comment='#resolve: domain1.com,domain2.com', 
            obj_type=FirewallObjectType.IPSET
        ))
        
        # Set DNS entries for both domains
        self.deps.dns_entries['domain1.com'] = ['10.0.0.1', '10.0.0.2']
        self.deps.dns_entries['domain2.com'] = ['10.0.0.3', '10.0.0.4']

        # WHEN
        update_firewall_objects(self.deps, FirewallObjectType.IPSET)

        # THEN
        # Should have IPs from both domains
        expected_ips = ['10.0.0.1', '10.0.0.2', '10.0.0.3', '10.0.0.4']
        self.assertEqual(sorted(expected_ips), sorted(self.deps.object_content[FirewallObjectType.IPSET]['ipset_multi_domain']))

    def test_ipset_multiple_domains_with_duplicate_ips(self):
        # GIVEN
        # IPSet with multiple domains in the comment
        self.deps.set_entry(FirewallEntry(
            name='ipset_duplicate_ips', 
            cidr='192.168.1.1', 
            comment='#resolve: domain1.com,domain2.com,domain3.com', 
            obj_type=FirewallObjectType.IPSET
        ))
        
        # Some domains resolve to the same IPs
        self.deps.dns_entries['domain1.com'] = ['10.0.0.1', '10.0.0.2']
        self.deps.dns_entries['domain2.com'] = ['10.0.0.2', '10.0.0.3']  # Duplicates 10.0.0.2
        self.deps.dns_entries['domain3.com'] = ['10.0.0.4']

        # WHEN
        update_firewall_objects(self.deps, FirewallObjectType.IPSET)

        # THEN
        # Should have unique IPs from all domains (no duplicates)
        expected_ips = ['10.0.0.1', '10.0.0.2', '10.0.0.3', '10.0.0.4']
        self.assertEqual(sorted(expected_ips), sorted(self.deps.object_content[FirewallObjectType.IPSET]['ipset_duplicate_ips']))

    # Alias Tests
    def test_alias_should_be_updated_with_first_ip(self):
        # GIVEN
        self.deps.set_entry(FirewallEntry(name='alias1', cidr='0.0.0.0', comment='#resolve: example.com', obj_type=FirewallObjectType.ALIAS))
        # DNS returns multiple IPs but only the first should be used
        self.deps.dns_entries['example.com'] = ['1.2.3.4', '5.6.7.8']

        # WHEN
        update_firewall_objects(self.deps, FirewallObjectType.ALIAS)

        # THEN
        expect = FirewallEntry(name='alias1', cidr='1.2.3.4', comment='#resolve: example.com', obj_type=FirewallObjectType.ALIAS)
        actual = self.deps.object_entries[FirewallObjectType.ALIAS]['alias1']
        self.assertEqual(expect, actual)

    def test_alias_no_dns_should_not_change(self):
        # GIVEN
        entry = FirewallEntry(name='alias1', cidr='0.0.0.0', comment='#resolve: example.com', obj_type=FirewallObjectType.ALIAS)
        self.deps.set_entry(entry)
        # No DNS entry

        # WHEN
        update_firewall_objects(self.deps, FirewallObjectType.ALIAS)

        # THEN
        actual = self.deps.object_entries[FirewallObjectType.ALIAS]['alias1']
        self.assertEqual(entry, actual)

    def test_alias_with_multiple_domains_uses_only_first(self):
        # GIVEN
        # Alias with multiple domains in the comment (should only use the first one)
        self.deps.set_entry(FirewallEntry(
            name='alias_multi_domain', 
            cidr='0.0.0.0', 
            comment='#resolve: primary.com,secondary.com', 
            obj_type=FirewallObjectType.ALIAS
        ))
        
        # Set DNS entries for both domains
        self.deps.dns_entries['primary.com'] = ['10.0.0.1', '10.0.0.2']
        self.deps.dns_entries['secondary.com'] = ['20.0.0.1', '20.0.0.2']

        # WHEN
        update_firewall_objects(self.deps, FirewallObjectType.ALIAS)

        # THEN
        # Should only use the first IP from the first domain
        expect = FirewallEntry(
            name='alias_multi_domain', 
            cidr='10.0.0.1', 
            comment='#resolve: primary.com,secondary.com', 
            obj_type=FirewallObjectType.ALIAS
        )
        actual = self.deps.object_entries[FirewallObjectType.ALIAS]['alias_multi_domain']
        self.assertEqual(expect, actual)


class DependenciesFake(Dependencies):
    """Fake implementation of Dependencies interface for testing."""

    def __init__(self):
        super().__init__()
        self.dry_run = False
        self.object_entries = {
            FirewallObjectType.IPSET: {},
            FirewallObjectType.ALIAS: {}
        }
        self.object_content = {
            FirewallObjectType.IPSET: {},
            FirewallObjectType.ALIAS: {}
        }
        self.dns_entries = {}

    def list_entries(self, obj_type: FirewallObjectType) -> List[FirewallEntry]:
        """List all entries of the specified type."""
        return list(self.object_entries[obj_type].values())

    def set_entry(self, entry: FirewallEntry):
        """Add or update an entry."""
        self.object_entries[entry.obj_type][entry.name] = entry
        
        # Also add to the content list for that object
        if entry.name not in self.object_content[entry.obj_type]:
            self.object_content[entry.obj_type][entry.name] = []
        
        # For IPSets, maintain a list of CIDRs
        if entry.obj_type == FirewallObjectType.IPSET:
            if entry.cidr not in self.object_content[entry.obj_type][entry.name]:
                self.object_content[entry.obj_type][entry.name].append(entry.cidr)
        else:
            # For Aliases, just store the single CIDR
            self.object_content[entry.obj_type][entry.name] = [entry.cidr]

    def delete_entry(self, entry: FirewallEntry):
        """Delete an entry."""
        if entry.obj_type == FirewallObjectType.IPSET:
            if entry.name in self.object_content[entry.obj_type] and entry.cidr in self.object_content[entry.obj_type][entry.name]:
                self.object_content[entry.obj_type][entry.name].remove(entry.cidr)

    def get_object_entries(self, obj_type: FirewallObjectType, name: str) -> List[str]:
        """Get all CIDRs for a specific IPSet or Alias."""
        return self.object_content[obj_type].get(name, [])

    def dns_resolve(self, domain: str) -> List[str]:
        """Resolve a domain to a list of IP addresses."""
        result = self.dns_entries.get(domain, [])
        # Handle both string and list formats for backward compatibility
        if isinstance(result, str):
            return [result]
        return result


class ParseEntriesFromJsonTestCase(unittest.TestCase):
    
    def test_parse_ipset_entries(self):
        # GIVEN
        ipset_json = '[{"name":"ipset_example","comment":"#resolve: example.com","entries":[{"cidr":"1.2.3.4"},{"cidr":"0.0.0.0"}]}]'
        
        # WHEN
        actual = parse_entries_from_json(ipset_json, FirewallObjectType.IPSET)
        
        # THEN
        expect = [
            FirewallEntry(name='ipset_example', cidr='1.2.3.4', comment='#resolve: example.com', obj_type=FirewallObjectType.IPSET),
            FirewallEntry(name='ipset_example', cidr='0.0.0.0', comment='#resolve: example.com', obj_type=FirewallObjectType.IPSET)
        ]
        self.assertEqual(expect, actual)
    
    def test_parse_alias_entries(self):
        # GIVEN
        alias_json = '[{"cidr":"1.2.3.4","comment":"#resolve: example.com","digest":"48ba54e4","ipversion":4,"name":"alias_example_com"}]'
        
        # WHEN
        actual = parse_entries_from_json(alias_json, FirewallObjectType.ALIAS)
        
        # THEN
        expect = [
            FirewallEntry(name='alias_example_com', cidr='1.2.3.4', comment='#resolve: example.com', obj_type=FirewallObjectType.ALIAS)
        ]
        self.assertEqual(expect, actual)


if __name__ == '__main__':
    unittest.main()
