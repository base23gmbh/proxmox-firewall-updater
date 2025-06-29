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
            comment='#resolve=domain1.com,domain2.com', 
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
            comment='#resolve=domain1.com,domain2.com,domain3.com', 
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
            comment='#resolve=primary.com,secondary.com', 
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
            comment='#resolve=primary.com,secondary.com', 
            obj_type=FirewallObjectType.ALIAS
        )
        actual = self.deps.object_entries[FirewallObjectType.ALIAS]['alias_multi_domain']
        self.assertEqual(expect, actual)

    def test_ipset_preserves_alias_references(self):
        # GIVEN
        # IPSet with DNS entries and alias references
        self.deps.set_entry(FirewallEntry(
            name='ipset_with_alias_refs', 
            cidr='192.168.1.1', 
            comment='#resolve=domain1.com', 
            obj_type=FirewallObjectType.IPSET
        ))
        
        # Add special alias references that should be preserved
        self.deps.set_entry(FirewallEntry(
            name='ipset_with_alias_refs', 
            cidr='dc/some-datacenter', 
            comment='#resolve: domain1.com', 
            obj_type=FirewallObjectType.IPSET
        ))
        self.deps.set_entry(FirewallEntry(
            name='ipset_with_alias_refs', 
            cidr='guest/vm-100-disk-0', 
            comment='#resolve: domain1.com', 
            obj_type=FirewallObjectType.IPSET
        ))
        
        # Set DNS entries for the domain
        self.deps.dns_entries['domain1.com'] = ['10.0.0.1', '10.0.0.2']

        # WHEN
        update_firewall_objects(self.deps, FirewallObjectType.IPSET)

        # THEN
        # Should have IPs from DNS plus preserved alias references
        expected_ips = ['10.0.0.1', '10.0.0.2', 'dc/some-datacenter', 'guest/vm-100-disk-0']
        self.assertEqual(sorted(expected_ips), sorted(self.deps.object_content[FirewallObjectType.IPSET]['ipset_with_alias_refs']))
        
        # 192.168.1.1 should be removed, but the alias refs should be preserved
        self.assertNotIn('192.168.1.1', self.deps.object_content[FirewallObjectType.IPSET]['ipset_with_alias_refs'])

    def test_get_resolve_options(self):
        # Test default options with new style
        entry = FirewallEntry(
            name='ipset1', 
            cidr='192.168.1.1', 
            comment='#resolve=example.com', 
            obj_type=FirewallObjectType.IPSET
        )
        options = entry.get_resolve_options()
        self.assertEqual(1, options['queries'])
        self.assertEqual(3, options['delay'])
        
        # Test with custom queries
        entry = FirewallEntry(
            name='ipset2', 
            cidr='192.168.1.1', 
            comment='#resolve=example.com #queries=5', 
            obj_type=FirewallObjectType.IPSET
        )
        options = entry.get_resolve_options()
        self.assertEqual(5, options['queries'])
        self.assertEqual(3, options['delay'])
        
        # Test with custom delay
        entry = FirewallEntry(
            name='ipset3', 
            cidr='192.168.1.1', 
            comment='#resolve=example.com #delay=1.5', 
            obj_type=FirewallObjectType.IPSET
        )
        options = entry.get_resolve_options()
        self.assertEqual(1, options['queries'])
        self.assertEqual(1.5, options['delay'])
        
        # Test with both custom options
        entry = FirewallEntry(
            name='ipset4', 
            cidr='192.168.1.1', 
            comment='#resolve=example.com #queries=3 #delay=2', 
            obj_type=FirewallObjectType.IPSET
        )
        options = entry.get_resolve_options()
        self.assertEqual(3, options['queries'])
        self.assertEqual(2, options['delay'])

    def test_multiple_dns_queries(self):
        # GIVEN
        # IPSet with multiple query configuration
        self.deps.set_entry(FirewallEntry(
            name='ipset_multi_query', 
            cidr='192.168.1.1', 
            comment='#resolve=rotating.example.com #queries=3 #delay=0.1', 
            obj_type=FirewallObjectType.IPSET
        ))
        
        # Mock DNS resolver to return different IPs on each call
        original_dns_resolve = self.deps.dns_resolve
        query_count = 0
        
        def mock_dns_resolve(domain, queries=1, delay=3.0, custom_dns_servers=None):
            nonlocal query_count
            if domain == 'rotating.example.com':
                all_ips = []
                # Simulate multiple queries returning different IPs
                for i in range(queries):
                    query_count += 1
                    if i == 0:
                        all_ips.extend(['10.0.0.1', '10.0.0.2'])
                    elif i == 1:
                        all_ips.extend(['10.0.0.3', '10.0.0.4'])
                    else:
                        all_ips.extend(['10.0.0.5', '10.0.0.6'])
                return all_ips
            return original_dns_resolve(domain, queries, delay, custom_dns_servers)
        
        # Replace the DNS resolver with our mock
        self.deps.dns_resolve = mock_dns_resolve
        
        try:
            # WHEN
            update_firewall_objects(self.deps, FirewallObjectType.IPSET)
            
            # THEN
            # Should have all IPs from all queries
            expected_ips = ['10.0.0.1', '10.0.0.2', '10.0.0.3', '10.0.0.4', '10.0.0.5', '10.0.0.6']
            self.assertEqual(sorted(expected_ips), 
                           sorted(self.deps.object_content[FirewallObjectType.IPSET]['ipset_multi_query']))
            
            # Should have made 3 queries as configured
            self.assertEqual(3, query_count)
        finally:
            # Restore the original DNS resolver
            self.deps.dns_resolve = original_dns_resolve

    def test_custom_dns_servers_configuration(self):
        # Test that DNS servers can be configured
        custom_dns_servers = ['8.8.8.8', '1.1.1.1']
        deps = DependenciesFake(dns_servers=custom_dns_servers)
        
        self.assertEqual(custom_dns_servers, deps.dns_servers)
        
        # Test with no custom DNS servers (should use system default)
        deps_default = DependenciesFake()
        self.assertIsNone(deps_default.dns_servers)

    def test_dns_resolution_with_custom_servers_in_comment(self):
        # Test that the feature works end-to-end with custom DNS servers
        custom_dns_servers = ['8.8.8.8', '1.1.1.1']
        self.deps.dns_servers = custom_dns_servers
        
        # GIVEN
        self.deps.set_entry(FirewallEntry(
            name='ipset_custom_dns', 
            cidr='192.168.1.1', 
            comment='#resolve=example.com Custom DNS test', 
            obj_type=FirewallObjectType.IPSET
        ))
        
        # Set DNS entries for the domain
        self.deps.dns_entries['example.com'] = ['10.0.0.1', '10.0.0.2']

        # WHEN
        update_firewall_objects(self.deps, FirewallObjectType.IPSET)

        # THEN
        # Should have IPs from DNS resolution
        expected_ips = ['10.0.0.1', '10.0.0.2']
        self.assertEqual(sorted(expected_ips), sorted(self.deps.object_content[FirewallObjectType.IPSET]['ipset_custom_dns']))

    def test_legacy_resolve_syntax(self):
        # Test legacy #resolve: syntax
        entry = FirewallEntry(
            name='ipset_legacy', 
            cidr='192.168.1.1', 
            comment='#resolve: example.com #queries=3', 
            obj_type=FirewallObjectType.IPSET
        )
        # Check domains extraction
        domains = entry.domains()
        self.assertEqual(['example.com'], domains)
        
        # Check options
        options = entry.get_resolve_options()
        self.assertEqual(3, options['queries'])
        
        # Test with multiple domains
        entry = FirewallEntry(
            name='ipset_legacy_multi', 
            cidr='192.168.1.1', 
            comment='#resolve: domain1.com,domain2.com', 
            obj_type=FirewallObjectType.IPSET
        )
        domains = entry.domains()
        self.assertEqual(['domain1.com', 'domain2.com'], domains)

    def test_new_resolve_syntax_with_multiple_domains(self):
        # Test new #resolve= syntax with multiple domains
        entry = FirewallEntry(
            name='ipset_new_multi', 
            cidr='192.168.1.1', 
            comment='#resolve=domain1.com,domain2.com,domain3.com #queries=2', 
            obj_type=FirewallObjectType.IPSET
        )
        # Check domains extraction
        domains = entry.domains()
        self.assertEqual(['domain1.com', 'domain2.com', 'domain3.com'], domains)
        
        # Check options
        options = entry.get_resolve_options()
        self.assertEqual(2, options['queries'])

    def test_comprehensive_feature_set(self):
        """Test that combines multiple domains, alias references, and multiple queries."""
        # GIVEN
        # IPSet with multiple domains, multiple queries, and alias references
        self.deps.set_entry(FirewallEntry(
            name='ipset_comprehensive', 
            cidr='192.168.1.1', 
            comment='#resolve=domain1.com,domain2.com #queries=2 #delay=0.1', 
            obj_type=FirewallObjectType.IPSET
        ))
        
        # Add special alias references that should be preserved
        self.deps.set_entry(FirewallEntry(
            name='ipset_comprehensive', 
            cidr='dc/alias-ref', 
            comment='#resolve=domain1.com,domain2.com #queries=2 #delay=0.1', 
            obj_type=FirewallObjectType.IPSET
        ))
        
        # Mock DNS resolver to return different IPs on each query
        original_dns_resolve = self.deps.dns_resolve
        
        def mock_dns_resolve(domain, queries=1, delay=3.0, custom_dns_servers=None):
            if domain == 'domain1.com':
                # First query returns two IPs, second query returns one more
                if queries > 1:
                    return ['10.0.0.1', '10.0.0.2', '10.0.0.5']
                return ['10.0.0.1', '10.0.0.2']
            elif domain == 'domain2.com':
                # First query returns two IPs, second query returns one more
                if queries > 1:
                    return ['10.0.0.3', '10.0.0.4', '10.0.0.6']
                return ['10.0.0.3', '10.0.0.4']
            return original_dns_resolve(domain, queries, delay, custom_dns_servers)
        
        # Replace the DNS resolver with our mock
        self.deps.dns_resolve = mock_dns_resolve
        
        try:
            # WHEN
            update_firewall_objects(self.deps, FirewallObjectType.IPSET)
            
            # THEN
            # Should have all IPs from all domains plus the alias reference
            expected_ips = [
                '10.0.0.1', '10.0.0.2', '10.0.0.3', 
                '10.0.0.4', '10.0.0.5', '10.0.0.6',
                'dc/alias-ref'
            ]
            self.assertEqual(
                sorted(expected_ips), 
                sorted(self.deps.object_content[FirewallObjectType.IPSET]['ipset_comprehensive'])
            )
            
            # 192.168.1.1 should be removed, but the alias ref should be preserved
            self.assertNotIn('192.168.1.1', self.deps.object_content[FirewallObjectType.IPSET]['ipset_comprehensive'])
            self.assertIn('dc/alias-ref', self.deps.object_content[FirewallObjectType.IPSET]['ipset_comprehensive'])
            
        finally:
            # Restore the original DNS resolver
            self.deps.dns_resolve = original_dns_resolve

    # DNS Server Override Tests
    def test_dns_servers_extraction_from_comment(self):
        # Test extracting DNS servers from comment
        entry = FirewallEntry(
            name='ipset_custom_dns', 
            cidr='192.168.1.1', 
            comment='#resolve=example.com #dns-servers=8.8.8.8,1.1.1.1', 
            obj_type=FirewallObjectType.IPSET
        )
        dns_servers = entry.dns_servers()
        self.assertEqual(['8.8.8.8', '1.1.1.1'], dns_servers)
        
        # Test single DNS server
        entry = FirewallEntry(
            name='ipset_single_dns', 
            cidr='192.168.1.1', 
            comment='#resolve=example.com #dns-servers=8.8.8.8', 
            obj_type=FirewallObjectType.IPSET
        )
        dns_servers = entry.dns_servers()
        self.assertEqual(['8.8.8.8'], dns_servers)
        
        # Test system keyword
        entry = FirewallEntry(
            name='ipset_system_dns', 
            cidr='192.168.1.1', 
            comment='#resolve=example.com #dns-servers=system', 
            obj_type=FirewallObjectType.IPSET
        )
        dns_servers = entry.dns_servers()
        self.assertEqual([], dns_servers)  # Empty list means force system DNS
        
        # Test no DNS servers specified
        entry = FirewallEntry(
            name='ipset_no_dns', 
            cidr='192.168.1.1', 
            comment='#resolve=example.com', 
            obj_type=FirewallObjectType.IPSET
        )
        dns_servers = entry.dns_servers()
        self.assertIsNone(dns_servers)  # None means use default

    def test_ipset_with_custom_dns_servers_in_comment(self):
        # GIVEN
        # IPSet with custom DNS servers in comment
        self.deps.set_entry(FirewallEntry(
            name='ipset_comment_dns', 
            cidr='192.168.1.1', 
            comment='#resolve=example.com #dns-servers=8.8.8.8,1.1.1.1', 
            obj_type=FirewallObjectType.IPSET
        ))
        
        # Mock DNS resolver to track which DNS servers were used
        original_dns_resolve = self.deps.dns_resolve
        used_dns_servers = []
        
        def mock_dns_resolve(domain, queries=1, delay=3.0, custom_dns_servers=None):
            nonlocal used_dns_servers
            used_dns_servers = custom_dns_servers
            if domain == 'example.com':
                return ['10.0.0.1', '10.0.0.2']
            return original_dns_resolve(domain, queries, delay, custom_dns_servers)
        
        self.deps.dns_resolve = mock_dns_resolve
        
        try:
            # WHEN
            update_firewall_objects(self.deps, FirewallObjectType.IPSET)
            
            # THEN
            # Should have used the custom DNS servers from the comment
            self.assertEqual(['8.8.8.8', '1.1.1.1'], used_dns_servers)
            
            # Should have IPs from DNS resolution
            expected_ips = ['10.0.0.1', '10.0.0.2']
            self.assertEqual(sorted(expected_ips), sorted(self.deps.object_content[FirewallObjectType.IPSET]['ipset_comment_dns']))
            
        finally:
            self.deps.dns_resolve = original_dns_resolve

    def test_ipset_with_system_dns_override(self):
        # GIVEN
        # Set CLI DNS servers
        self.deps.dns_servers = ['9.9.9.9', '1.0.0.1']
        
        # IPSet with system DNS override in comment
        self.deps.set_entry(FirewallEntry(
            name='ipset_system_override', 
            cidr='192.168.1.1', 
            comment='#resolve=example.com #dns-servers=system', 
            obj_type=FirewallObjectType.IPSET
        ))
        
        # Mock DNS resolver to track which DNS servers were used
        original_dns_resolve = self.deps.dns_resolve
        used_dns_servers = None
        force_system_dns = False
        
        def mock_dns_resolve(domain, queries=1, delay=3.0, custom_dns_servers=None):
            nonlocal used_dns_servers, force_system_dns
            used_dns_servers = custom_dns_servers
            force_system_dns = custom_dns_servers is not None and len(custom_dns_servers) == 0
            if domain == 'example.com':
                return ['10.0.0.3', '10.0.0.4']
            return original_dns_resolve(domain, queries, delay, custom_dns_servers)
        
        self.deps.dns_resolve = mock_dns_resolve
        
        try:
            # WHEN
            update_firewall_objects(self.deps, FirewallObjectType.IPSET)
            
            # THEN
            # Should have forced system DNS (empty list)
            self.assertEqual([], used_dns_servers)
            self.assertTrue(force_system_dns)
            
            # Should have IPs from DNS resolution
            expected_ips = ['10.0.0.3', '10.0.0.4']
            self.assertEqual(sorted(expected_ips), sorted(self.deps.object_content[FirewallObjectType.IPSET]['ipset_system_override']))
            
        finally:
            self.deps.dns_resolve = original_dns_resolve

    def test_alias_with_custom_dns_servers_in_comment(self):
        # GIVEN
        # Alias with custom DNS servers in comment
        self.deps.set_entry(FirewallEntry(
            name='alias_comment_dns', 
            cidr='0.0.0.0', 
            comment='#resolve=example.com #dns-servers=8.8.8.8', 
            obj_type=FirewallObjectType.ALIAS
        ))
        
        # Mock DNS resolver to track which DNS servers were used
        original_dns_resolve = self.deps.dns_resolve
        used_dns_servers = []
        
        def mock_dns_resolve(domain, queries=1, delay=3.0, custom_dns_servers=None):
            nonlocal used_dns_servers
            used_dns_servers = custom_dns_servers
            if domain == 'example.com':
                return ['10.0.0.5']
            return original_dns_resolve(domain, queries, delay, custom_dns_servers)
        
        self.deps.dns_resolve = mock_dns_resolve
        
        try:
            # WHEN
            update_firewall_objects(self.deps, FirewallObjectType.ALIAS)
            
            # THEN
            # Should have used the custom DNS server from the comment
            self.assertEqual(['8.8.8.8'], used_dns_servers)
            
            # Should have updated the alias
            expect = FirewallEntry(
                name='alias_comment_dns', 
                cidr='10.0.0.5', 
                comment='#resolve=example.com #dns-servers=8.8.8.8', 
                obj_type=FirewallObjectType.ALIAS
            )
            actual = self.deps.object_entries[FirewallObjectType.ALIAS]['alias_comment_dns']
            self.assertEqual(expect, actual)
            
        finally:
            self.deps.dns_resolve = original_dns_resolve

    def test_dns_server_priority_comment_overrides_cli(self):
        # GIVEN
        # Set CLI DNS servers
        self.deps.dns_servers = ['9.9.9.9', '1.0.0.1']
        
        # IPSet with different DNS servers in comment (should override CLI)
        self.deps.set_entry(FirewallEntry(
            name='ipset_priority_test', 
            cidr='192.168.1.1', 
            comment='#resolve=example.com #dns-servers=8.8.8.8,1.1.1.1', 
            obj_type=FirewallObjectType.IPSET
        ))
        
        # Mock DNS resolver to track which DNS servers were used
        original_dns_resolve = self.deps.dns_resolve
        used_dns_servers = []
        
        def mock_dns_resolve(domain, queries=1, delay=3.0, custom_dns_servers=None):
            nonlocal used_dns_servers
            used_dns_servers = custom_dns_servers
            if domain == 'example.com':
                return ['10.0.0.6', '10.0.0.7']
            return original_dns_resolve(domain, queries, delay, custom_dns_servers)
        
        self.deps.dns_resolve = mock_dns_resolve
        
        try:
            # WHEN
            update_firewall_objects(self.deps, FirewallObjectType.IPSET)
            
            # THEN
            # Should have used the comment DNS servers, not the CLI ones
            self.assertEqual(['8.8.8.8', '1.1.1.1'], used_dns_servers)
            self.assertNotEqual(['9.9.9.9', '1.0.0.1'], used_dns_servers)
            
            # Should have IPs from DNS resolution
            expected_ips = ['10.0.0.6', '10.0.0.7']
            self.assertEqual(sorted(expected_ips), sorted(self.deps.object_content[FirewallObjectType.IPSET]['ipset_priority_test']))
            
        finally:
            self.deps.dns_resolve = original_dns_resolve

    def test_mixed_dns_configurations(self):
        # GIVEN
        # Set CLI DNS servers
        self.deps.dns_servers = ['9.9.9.9']
        
        # Multiple IPSets with different DNS configurations
        self.deps.set_entry(FirewallEntry(
            name='ipset_cli_dns', 
            cidr='192.168.1.1', 
            comment='#resolve=domain1.com',  # No DNS override, should use CLI
            obj_type=FirewallObjectType.IPSET
        ))
        
        self.deps.set_entry(FirewallEntry(
            name='ipset_comment_dns', 
            cidr='192.168.1.2', 
            comment='#resolve=domain2.com #dns-servers=8.8.8.8',  # Should use comment DNS
            obj_type=FirewallObjectType.IPSET
        ))
        
        self.deps.set_entry(FirewallEntry(
            name='ipset_system_dns', 
            cidr='192.168.1.3', 
            comment='#resolve=domain3.com #dns-servers=system',  # Should force system DNS
            obj_type=FirewallObjectType.IPSET
        ))
        
        # Mock DNS resolver to track which DNS servers were used for each domain
        original_dns_resolve = self.deps.dns_resolve
        dns_calls = {}
        
        def mock_dns_resolve(domain, queries=1, delay=3.0, custom_dns_servers=None):
            nonlocal dns_calls
            dns_calls[domain] = custom_dns_servers
            
            if domain == 'domain1.com':
                return ['10.0.1.1']
            elif domain == 'domain2.com':
                return ['10.0.2.1']
            elif domain == 'domain3.com':
                return ['10.0.3.1']
            return original_dns_resolve(domain, queries, delay, custom_dns_servers)
        
        self.deps.dns_resolve = mock_dns_resolve
        
        try:
            # WHEN
            update_firewall_objects(self.deps, FirewallObjectType.IPSET)
            
            # THEN
            # domain1.com should use None (default to CLI servers)
            self.assertIsNone(dns_calls['domain1.com'])
            
            # domain2.com should use comment DNS servers
            self.assertEqual(['8.8.8.8'], dns_calls['domain2.com'])
            
            # domain3.com should force system DNS (empty list)
            self.assertEqual([], dns_calls['domain3.com'])
            
            # All IPSets should have their respective IPs
            self.assertEqual(['10.0.1.1'], self.deps.object_content[FirewallObjectType.IPSET]['ipset_cli_dns'])
            self.assertEqual(['10.0.2.1'], self.deps.object_content[FirewallObjectType.IPSET]['ipset_comment_dns'])
            self.assertEqual(['10.0.3.1'], self.deps.object_content[FirewallObjectType.IPSET]['ipset_system_dns'])
            
        finally:
            self.deps.dns_resolve = original_dns_resolve

    def test_complex_comment_parsing_with_dns_servers(self):
        # Test complex comment with all options
        entry = FirewallEntry(
            name='ipset_complex', 
            cidr='192.168.1.1', 
            comment='#resolve=domain1.com,domain2.com #queries=3 #delay=1.5 #dns-servers=8.8.8.8,1.1.1.1 Additional comment text', 
            obj_type=FirewallObjectType.IPSET
        )
        
        # Test domains extraction
        domains = entry.domains()
        self.assertEqual(['domain1.com', 'domain2.com'], domains)
        
        # Test options extraction
        options = entry.get_resolve_options()
        self.assertEqual(3, options['queries'])
        self.assertEqual(1.5, options['delay'])
        
        # Test DNS servers extraction
        dns_servers = entry.dns_servers()
        self.assertEqual(['8.8.8.8', '1.1.1.1'], dns_servers)


class DependenciesFake(Dependencies):
    """Fake implementation of Dependencies interface for testing."""

    def __init__(self, dns_servers=None):
        super().__init__()
        self.dry_run = False
        self.dns_servers = dns_servers
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

    def dns_resolve(self, domain: str, queries: int = 1, delay: float = 3.0, custom_dns_servers: List[str] | None = None) -> List[str]:
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
