import sys
import unittest
from datetime import datetime, timedelta, timezone

sys.path.insert(0, 'backend')
from domain import Actor, DomainError, store


INSPECTOR = Actor('Samira Khan', 'inspector')
MANAGER = Actor('Nazmul Ahmed', 'corrective-action-manager')
VERIFIER = Actor('Farhana Noor', 'verifier')
AUDITOR = Actor('Tariq Islam', 'auditor')


class InspectionCorrectiveActionTests(unittest.TestCase):
    def setUp(self):
        store.reset()

    def open_finding(self):
        inspection = store.create_inspection(INSPECTOR, {'siteName': 'Northgate Warehouse', 'location': 'Loading dock level 2', 'inspectionType': 'Safety walk'})
        finding = store.record_finding(INSPECTOR, inspection.id, {'title': 'Guardrail opening', 'severity': 'high', 'observation': 'Guardrail opening needs immediate protective closure.'})
        return inspection, finding

    def test_end_to_end_verification_corrects_inspection(self):
        inspection, finding = self.open_finding()
        due = (datetime.now(timezone.utc) + timedelta(days=3)).isoformat()
        action = store.assign_action(MANAGER, finding.id, {'ownerTeam': 'Facilities response', 'dueDate': due})
        store.submit_evidence(MANAGER, action.id, {'completionEvidence': 'Work order WO-281 closed with installation photos.'})
        result = store.verify_action(VERIFIER, action.id, {'verificationNote': 'Field verification confirms the guardrail opening is closed.'})
        self.assertEqual(result.status, 'verified')
        self.assertEqual(store.snapshot(AUDITOR)['inspections'][0]['status'], 'corrected')
        self.assertEqual(len(store.snapshot(AUDITOR)['audits']), 5)

    def test_rejects_blank_site_name(self):
        with self.assertRaisesRegex(DomainError, 'Site name is required'):
            store.create_inspection(INSPECTOR, {'siteName': '', 'location': 'Loading dock', 'inspectionType': 'Safety walk'})

    def test_rejects_unauthorized_finding_assignment(self):
        _, finding = self.open_finding()
        with self.assertRaisesRegex(DomainError, 'This role cannot perform'):
            store.assign_action(INSPECTOR, finding.id, {'ownerTeam': 'Facilities', 'dueDate': (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()})

    def test_blocks_duplicate_open_inspection(self):
        payload = {'siteName': 'Northgate Warehouse', 'location': 'Loading dock level 2', 'inspectionType': 'Safety walk'}
        store.create_inspection(INSPECTOR, payload)
        with self.assertRaisesRegex(DomainError, 'open inspection already exists'):
            store.create_inspection(INSPECTOR, payload)

    def test_reports_missing_finding(self):
        with self.assertRaisesRegex(DomainError, 'Finding finding-404 was not found'):
            store.assign_action(MANAGER, 'finding-404', {'ownerTeam': 'Facilities', 'dueDate': (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()})

    def test_blocks_repeated_evidence_submission(self):
        _, finding = self.open_finding()
        action = store.assign_action(MANAGER, finding.id, {'ownerTeam': 'Facilities response', 'dueDate': (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()})
        store.submit_evidence(MANAGER, action.id, {'completionEvidence': 'Photo evidence INS-20.'})
        with self.assertRaisesRegex(DomainError, 'Evidence can only be submitted'):
            store.submit_evidence(MANAGER, action.id, {'completionEvidence': 'A second evidence package.'})


if __name__ == '__main__':
    unittest.main(verbosity=2)

