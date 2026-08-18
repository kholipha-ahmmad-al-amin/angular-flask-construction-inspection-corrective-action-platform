import os
from flask import Flask, jsonify, request
from domain import Actor, DomainError, store

KEYS = {
    os.getenv('INSPECTOR_API_KEY', 'inspector-local'): Actor('Samira Khan', 'inspector'),
    os.getenv('ACTION_MANAGER_API_KEY', 'action-manager-local'): Actor('Nazmul Ahmed', 'corrective-action-manager'),
    os.getenv('VERIFIER_API_KEY', 'verifier-local'): Actor('Farhana Noor', 'verifier'),
    os.getenv('AUDITOR_API_KEY', 'auditor-local'): Actor('Tariq Islam', 'auditor'),
}


def actor() -> Actor:
    value = request.headers.get('X-Access-Key') or request.headers.get('Authorization', '').removeprefix('Bearer ')
    if value not in KEYS:
        raise DomainError('FORBIDDEN', 'A valid access key is required')
    return KEYS[value]


def create_app() -> Flask:
    app = Flask(__name__)

    @app.after_request
    def cors(response):
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, X-Access-Key, Authorization'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
        return response

    @app.errorhandler(DomainError)
    def domain_error(error):
        status = {'VALIDATION': 400, 'FORBIDDEN': 403, 'NOT_FOUND': 404, 'CONFLICT': 409, 'FAILURE': 500}[error.code]
        return jsonify(error={'code': error.code, 'message': str(error)}), status

    @app.errorhandler(Exception)
    def unexpected_error(error):
        return jsonify(error={'code': 'FAILURE', 'message': 'The request could not be completed'}), 500

    @app.get('/api/health')
    def health():
        return jsonify(status='ok', service='inspection-corrective-action-control')

    @app.get('/api/snapshot')
    def snapshot():
        return jsonify(store.snapshot(actor()))

    @app.post('/api/inspections')
    def create_inspection():
        return jsonify(store.create_inspection(actor(), request.get_json(silent=True) or {})), 201

    @app.post('/api/inspections/<inspection_id>/findings')
    def create_finding(inspection_id):
        return jsonify(store.record_finding(actor(), inspection_id, request.get_json(silent=True) or {})), 201

    @app.post('/api/findings/<finding_id>/actions')
    def assign_action(finding_id):
        return jsonify(store.assign_action(actor(), finding_id, request.get_json(silent=True) or {})), 201

    @app.post('/api/actions/<action_id>/evidence')
    def evidence(action_id):
        return jsonify(store.submit_evidence(actor(), action_id, request.get_json(silent=True) or {}))

    @app.post('/api/actions/<action_id>/verify')
    def verify(action_id):
        return jsonify(store.verify_action(actor(), action_id, request.get_json(silent=True) or {}))

    return app


if __name__ == '__main__':
    create_app().run(host='0.0.0.0', port=int(os.getenv('PORT', '11500')), debug=False)

