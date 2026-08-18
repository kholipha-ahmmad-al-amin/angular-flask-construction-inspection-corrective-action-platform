import { CommonModule } from '@angular/common';
import { ChangeDetectorRef, Component, inject } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { HttpClient, HttpHeaders } from '@angular/common/http';

type Snapshot = { inspections: any[]; findings: any[]; actions: any[]; audits: any[]; metrics: { openInspections: number; openFindings: number; awaitingVerification: number } };
const empty: Snapshot = { inspections: [], findings: [], actions: [], audits: [], metrics: { openInspections: 0, openFindings: 0, awaitingVerification: 0 } };

@Component({ selector: 'app-root', standalone: true, imports: [CommonModule, FormsModule], templateUrl: './app.component.html' })
export class AppComponent {
  private http = inject(HttpClient);
  private cdr = inject(ChangeDetectorRef);
  roles = [{ key: 'inspector-local', label: 'Inspector' }, { key: 'action-manager-local', label: 'Action manager' }, { key: 'verifier-local', label: 'Verifier' }, { key: 'auditor-local', label: 'Audit observer' }];
  key = this.roles[0].key; notice = 'Loading inspection register'; data = empty;
  inspection = { siteName: '', location: '', inspectionType: '' }; finding = { inspectionId: '', title: '', severity: 'high', observation: '' }; action = { findingId: '', ownerTeam: '', dueDate: '' }; evidence = { actionId: '', completionEvidence: '' }; verify = { actionId: '', verificationNote: '' };
  ngOnInit() { this.refresh(); }
  headers() { return { headers: new HttpHeaders({ 'X-Access-Key': this.key }) }; }
  refresh() { this.http.get<Snapshot>('/api/snapshot', this.headers()).subscribe({ next: value => { this.data = value; this.notice = `Connected as ${this.roles.find(item => item.key === this.key)?.label}`; this.cdr.detectChanges(); }, error: error => { this.notice = error.error?.error?.message || 'Service unavailable'; this.cdr.detectChanges(); } }); }
  save(route: string, body: any, done: () => void) { this.http.post(route, body, this.headers()).subscribe({ next: () => { done(); this.notice = 'Operational record saved.'; this.cdr.detectChanges(); this.refresh(); }, error: error => { this.notice = error.error?.error?.message || 'Request failed'; this.cdr.detectChanges(); } }); }
  openInspection() { this.save('/api/inspections', this.inspection, () => this.inspection = { siteName: '', location: '', inspectionType: '' }); }
  recordFinding() { this.save(`/api/inspections/${this.finding.inspectionId}/findings`, this.finding, () => this.finding = { inspectionId: '', title: '', severity: 'high', observation: '' }); }
  assignAction() { this.save(`/api/findings/${this.action.findingId}/actions`, this.action, () => this.action = { findingId: '', ownerTeam: '', dueDate: '' }); }
  submitEvidence() { this.save(`/api/actions/${this.evidence.actionId}/evidence`, this.evidence, () => this.evidence = { actionId: '', completionEvidence: '' }); }
  verifyAction() { const action = this.data.actions.find(item => item.status === 'evidence-submitted'); if (!action) { this.notice = 'No action is awaiting verification.'; return; } this.verify.actionId = action.id; this.save(`/api/actions/${this.verify.actionId}/verify`, this.verify, () => this.verify = { actionId: '', verificationNote: '' }); }
}
