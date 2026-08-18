from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Literal

Role = Literal['inspector', 'corrective-action-manager', 'verifier', 'auditor']


class DomainError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass
class Actor:
    name: str
    role: Role


@dataclass
class Inspection:
    id: str
    site_name: str
    location: str
    inspection_type: str
    status: str
    opened_at: str


@dataclass
class Finding:
    id: str
    inspection_id: str
    title: str
    severity: str
    observation: str
    status: str
    recorded_by: str
    recorded_at: str


@dataclass
class CorrectiveAction:
    id: str
    finding_id: str
    owner_team: str
    due_date: str
    status: str
    completion_evidence: str | None
    verified_by: str | None
    verified_at: str | None


@dataclass
class AuditEvent:
    id: str
    inspection_id: str
    actor_name: str
    actor_role: str
    action: str
    detail: str
    created_at: str


class InspectionStore:
    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self.sequence = 0
        self.inspections: list[Inspection] = []
        self.findings: list[Finding] = []
        self.actions: list[CorrectiveAction] = []
        self.audits: list[AuditEvent] = []

    def _id(self, prefix: str) -> str:
        self.sequence += 1
        return f'{prefix}-{self.sequence:04d}'

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _text(value: object, field: str, maximum: int = 300) -> str:
        if not isinstance(value, str) or not value.strip():
            raise DomainError('VALIDATION', f'{field} is required')
        value = value.strip()
        if len(value) > maximum:
            raise DomainError('VALIDATION', f'{field} exceeds {maximum} characters')
        return value

    @staticmethod
    def _role(actor: Actor, allowed: set[str]) -> None:
        if not actor or actor.role not in allowed:
            raise DomainError('FORBIDDEN', 'This role cannot perform the requested action')

    def _inspection(self, inspection_id: str) -> Inspection:
        inspection = next((item for item in self.inspections if item.id == inspection_id), None)
        if not inspection:
            raise DomainError('NOT_FOUND', f'Inspection {inspection_id} was not found')
        return inspection

    def _finding(self, finding_id: str) -> Finding:
        finding = next((item for item in self.findings if item.id == finding_id), None)
        if not finding:
            raise DomainError('NOT_FOUND', f'Finding {finding_id} was not found')
        return finding

    def _audit(self, inspection_id: str, actor: Actor, action: str, detail: str) -> None:
        self.audits.append(AuditEvent(self._id('audit'), inspection_id, actor.name, actor.role, action, detail, self._now()))

    def create_inspection(self, actor: Actor, payload: dict) -> Inspection:
        self._role(actor, {'inspector'})
        site_name = self._text(payload.get('siteName'), 'Site name', 180)
        location = self._text(payload.get('location'), 'Location', 300)
        inspection_type = self._text(payload.get('inspectionType'), 'Inspection type', 100)
        if any(item.site_name.lower() == site_name.lower() and item.inspection_type.lower() == inspection_type.lower() and item.status == 'open' for item in self.inspections):
            raise DomainError('CONFLICT', 'An open inspection already exists for this site and inspection type')
        inspection = Inspection(self._id('inspection'), site_name, location, inspection_type, 'open', self._now())
        self.inspections.append(inspection)
        self._audit(inspection.id, actor, 'inspection.opened', f'Opened {inspection_type} inspection at {location}')
        return inspection

    def record_finding(self, actor: Actor, inspection_id: str, payload: dict) -> Finding:
        self._role(actor, {'inspector'})
        inspection = self._inspection(inspection_id)
        if inspection.status != 'open':
            raise DomainError('CONFLICT', 'Findings can only be recorded for an open inspection')
        title = self._text(payload.get('title'), 'Finding title', 180)
        severity = payload.get('severity')
        if severity not in {'low', 'medium', 'high', 'critical'}:
            raise DomainError('VALIDATION', 'Severity must be low, medium, high, or critical')
        observation = self._text(payload.get('observation'), 'Observation', 600)
        finding = Finding(self._id('finding'), inspection_id, title, severity, observation, 'open', actor.name, self._now())
        self.findings.append(finding)
        self._audit(inspection_id, actor, 'finding.recorded', f'{severity} finding: {title}')
        return finding

    def assign_action(self, actor: Actor, finding_id: str, payload: dict) -> CorrectiveAction:
        self._role(actor, {'corrective-action-manager'})
        finding = self._finding(finding_id)
        if finding.status != 'open':
            raise DomainError('CONFLICT', 'Corrective action cannot be assigned to a closed finding')
        if any(item.finding_id == finding_id and item.status in {'assigned', 'evidence-submitted'} for item in self.actions):
            raise DomainError('CONFLICT', 'An active corrective action already exists for this finding')
        owner_team = self._text(payload.get('ownerTeam'), 'Owner team', 180)
        due_date = self._text(payload.get('dueDate'), 'Due date', 40)
        try:
            due = datetime.fromisoformat(due_date.replace('Z', '+00:00'))
            if due.date() < datetime.now(timezone.utc).date():
                raise ValueError
        except ValueError:
            raise DomainError('VALIDATION', 'Due date must be today or later in ISO format')
        action = CorrectiveAction(self._id('action'), finding_id, owner_team, due.isoformat(), 'assigned', None, None, None)
        self.actions.append(action)
        finding.status = 'action-assigned'
        self._audit(finding.inspection_id, actor, 'action.assigned', f'Assigned {action.id} to {owner_team}')
        return action

    def submit_evidence(self, actor: Actor, action_id: str, payload: dict) -> CorrectiveAction:
        self._role(actor, {'corrective-action-manager'})
        action = next((item for item in self.actions if item.id == action_id), None)
        if not action:
            raise DomainError('NOT_FOUND', f'Corrective action {action_id} was not found')
        if action.status != 'assigned':
            raise DomainError('CONFLICT', 'Evidence can only be submitted for an assigned action')
        action.completion_evidence = self._text(payload.get('completionEvidence'), 'Completion evidence', 500)
        action.status = 'evidence-submitted'
        finding = self._finding(action.finding_id)
        self._audit(finding.inspection_id, actor, 'action.evidence-submitted', action.completion_evidence)
        return action

    def verify_action(self, actor: Actor, action_id: str, payload: dict) -> CorrectiveAction:
        self._role(actor, {'verifier'})
        action = next((item for item in self.actions if item.id == action_id), None)
        if not action:
            raise DomainError('NOT_FOUND', f'Corrective action {action_id} was not found')
        if action.status != 'evidence-submitted':
            raise DomainError('CONFLICT', 'Only submitted evidence can be verified')
        note = self._text(payload.get('verificationNote'), 'Verification note', 500)
        action.status = 'verified'; action.verified_by = actor.name; action.verified_at = self._now()
        finding = self._finding(action.finding_id); finding.status = 'closed'
        inspection = self._inspection(finding.inspection_id)
        if not any(item.inspection_id == inspection.id and item.status != 'closed' for item in self.findings):
            inspection.status = 'corrected'
        self._audit(inspection.id, actor, 'action.verified', note)
        return action

    def snapshot(self, actor: Actor) -> dict:
        self._role(actor, {'inspector', 'corrective-action-manager', 'verifier', 'auditor'})
        return {
            'inspections': [asdict(item) for item in self.inspections],
            'findings': [asdict(item) for item in self.findings],
            'actions': [asdict(item) for item in self.actions],
            'audits': [asdict(item) for item in sorted(self.audits, key=lambda item: item.created_at, reverse=True)],
            'metrics': {
                'openInspections': len([item for item in self.inspections if item.status == 'open']),
                'openFindings': len([item for item in self.findings if item.status != 'closed']),
                'awaitingVerification': len([item for item in self.actions if item.status == 'evidence-submitted']),
            },
        }


store = InspectionStore()

