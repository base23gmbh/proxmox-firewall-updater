#!/usr/bin/env python3
from __future__ import annotations

import unittest
from typing import Dict, List

from update_firewall_ipsets import Dependencies, IPSetEntry, update_ipsets, ipset_list_to_typed


class update_ipsets_TestCase(unittest.TestCase):

    def setUp(self) -> None:
        self.deps = DependenciesFake()

    def tearDown(self) -> None:
        pass

    def test_stale_entry__should_be_changed(self):
        # GIVEN
        self.deps.ipset_set(IPSetEntry(name='ipset1', cidr='0.0.0.0', comment='#resolve: example.com'))
        self.deps.dns_entries['example.com'] = ['1.2.3.4']

        # WHEN
        update_ipsets(self.deps)

        # THEN
        self.assertEqual(['1.2.3.4'], self.deps.ipset_content['ipset1'])

    def test_stale_entry_and_dry_run__should_not_change(self):
        # GIVEN
        self.deps.dry_run = True
        ipset_entry = IPSetEntry(name='ipset1', cidr='0.0.0.0', comment='#resolve: example.com')
        self.deps.ipset_set(ipset_entry)
        self.deps.dns_entries['example.com'] = ['1.2.3.4']

        # WHEN
        update_ipsets(self.deps)

        # THEN
        # In dry run mode, the ipset content should remain unchanged
        self.assertEqual(['0.0.0.0'], self.deps.ipset_content['ipset1'])

    def test_up_to_date_entry__should_be_changed_only_if_dns_changes(self):
        # GIVEN
        ipset_entry = IPSetEntry(name='ipset1', cidr='0.0.0.0', comment='#resolve: example.com')
        self.deps.ipset_set(ipset_entry)
        self.deps.dns_entries['example.com'] = ['0.0.0.0']

        # WHEN
        update_ipsets(self.deps)

        # THEN
        # No changes should be made since DNS and IPSet contain the same entries
        self.assertEqual(['0.0.0.0'], self.deps.ipset_content['ipset1'])

    def test_no_dns__should_not_change_the_ipset(self):
        # GIVEN
        ipset_entry = IPSetEntry(name='ipset1', cidr='0.0.0.0', comment='#resolve: example.com')
        self.deps.ipset_set(ipset_entry)
        # no dns entry - default is empty list

        # WHEN
        update_ipsets(self.deps)

        # THEN
        # Without DNS entries, the IPSet should remain unchanged
        self.assertEqual(['0.0.0.0'], self.deps.ipset_content['ipset1'])

    def test_confounders(self):
        # GIVEN
        comment = 'confounder 1 #resolve: 1-800-unicorn.party confounder 2'
        self.deps.ipset_set(IPSetEntry(name='ipset1', cidr='0.0.0.0', comment=comment))
        self.deps.dns_entries['1-800-unicorn.party'] = ['1.2.3.4']

        # WHEN
        update_ipsets(self.deps)

        # THEN
        self.assertEqual(['1.2.3.4'], self.deps.ipset_content['ipset1'])

    def test_invalid__should_not_change_the_ipset(self):
        # GIVEN
        comment = '#resolve: '
        ipset_entry = IPSetEntry(name='ipset1', cidr='0.0.0.0', comment=comment)
        self.deps.ipset_set(ipset_entry)

        # WHEN
        update_ipsets(self.deps)

        # THEN
        self.assertEqual(['0.0.0.0'], self.deps.ipset_content['ipset1'])

    def test_no_comment__should_not_change_the_ipset(self):
        # GIVEN
        ipset_entry = IPSetEntry(name='ipset1', cidr='0.0.0.0', comment=None)
        self.deps.ipset_set(ipset_entry)

        # WHEN
        update_ipsets(self.deps)

        # THEN
        self.assertEqual(['0.0.0.0'], self.deps.ipset_content['ipset1'])

    def test_multiple_ips__should_add_and_remove_correctly(self):
        # GIVEN
        # Initial IPSet has two IPs
        self.deps.ipset_set(IPSetEntry(name='ipset1', cidr='192.168.1.1', comment='#resolve: example.com'))
        self.deps.ipset_set(IPSetEntry(name='ipset1', cidr='192.168.1.2', comment='#resolve: example.com'))
        
        # DNS returns different set of IPs - one to keep, one to remove, one to add
        self.deps.dns_entries['example.com'] = ['192.168.1.1', '192.168.1.3']

        # WHEN
        update_ipsets(self.deps)

        # THEN
        # Should keep 192.168.1.1, remove 192.168.1.2, and add 192.168.1.3
        expected_ips = ['192.168.1.1', '192.168.1.3']
        self.assertEqual(sorted(expected_ips), sorted(self.deps.ipset_content['ipset1']))

    def test_empty_dns_results__should_not_clear_ipset(self):
        # GIVEN
        # IPSet has entries
        self.deps.ipset_set(IPSetEntry(name='ipset1', cidr='192.168.1.1', comment='#resolve: example.com'))
        self.deps.ipset_set(IPSetEntry(name='ipset1', cidr='192.168.1.2', comment='#resolve: example.com'))
        
        # DNS returns empty list (could happen on temporary DNS failure)
        self.deps.dns_entries['example.com'] = []

        # WHEN
        update_ipsets(self.deps)

        # THEN
        # Should keep the existing IPs
        expected_ips = ['192.168.1.1', '192.168.1.2']
        self.assertEqual(sorted(expected_ips), sorted(self.deps.ipset_content['ipset1']))


class DependenciesFake(Dependencies):

    def __init__(self):
        super().__init__()
        self.dry_run = False
        self.ipset_entries: Dict[str, IPSetEntry] = {}
        self.dns_entries: Dict[str, List[str]] = {}
        self.ipset_content: Dict[str, List[str]] = {}
        self.domains_entries = []

    def ipset_list(self) -> List[IPSetEntry]:
        return list(self.ipset_entries.values())

    def ipset_set(self, entry: IPSetEntry):
        self.ipset_entries[entry.name] = entry
        # Also add to the content list for that IPSet
        if entry.name not in self.ipset_content:
            self.ipset_content[entry.name] = []
        if entry.cidr not in self.ipset_content[entry.name]:
            self.ipset_content[entry.name].append(entry.cidr)
    
    def ipset_delete(self, entry: IPSetEntry):
        if entry.name in self.ipset_content and entry.cidr in self.ipset_content[entry.name]:
            self.ipset_content[entry.name].remove(entry.cidr)

    def get_ipset_entries(self, ipset_name: str) -> List[str]:
        return self.ipset_content.get(ipset_name, [])

    def dns_resolve(self, domain: str) -> List[str]:
        return self.dns_entries.get(domain, [])


class ipset_list_to_typed_TestCase(unittest.TestCase):

    def test_empty(self):
        # GIVEN
        ipset_list = '[]'

        # WHEN
        actual = ipset_list_to_typed(ipset_list)

        # THEN
        self.assertEqual([], actual)

    def test_one(self):
        # GIVEN
        ipset_list = '[{"name":"ipset_example","comment":"#resolve: example.com","entries":[{"cidr":"1.2.3.4"},{"cidr":"0.0.0.0"}]}]'

        # WHEN
        actual = ipset_list_to_typed(ipset_list)

        # THEN
        expect = [
            IPSetEntry(name='ipset_example', cidr='1.2.3.4', comment='#resolve: example.com'),
            IPSetEntry(name='ipset_example', cidr='0.0.0.0', comment='#resolve: example.com')
        ]
        self.assertEqual(expect, actual)

    def test_entry_with_no_comment_or_null(self):
        # GIVEN
        ipset_list = '[{"name":"ipset_example","entries":[{"cidr":"1.2.3.4"},{"cidr":"0.0.0.0"}]}]'

        # WHEN
        actual = ipset_list_to_typed(ipset_list)

        # THEN
        expect = [
            IPSetEntry(name='ipset_example', cidr='1.2.3.4', comment=None),
            IPSetEntry(name='ipset_example', cidr='0.0.0.0', comment=None)
        ]
        self.assertEqual(expect, actual)
