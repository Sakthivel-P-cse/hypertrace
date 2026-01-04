# Incident Processing Service
# Receives, deduplicates, and stores incident events for audit and replay
# Save as incident_processing_service.py

from flask import Flask, request, jsonify
import sqlite3
import logging
import hashlib
from datetime import datetime

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
DB_PATH = 'incidents.db'

# Initialize DB
conn = sqlite3.connect(DB_PATH)
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS incidents (
    id TEXT PRIMARY KEY,
    timestamp TEXT,
    incident_json TEXT
)''')
conn.commit()
conn.close()

# Helper: Generate unique ID for deduplication
def incident_id(incident):
    return hashlib.sha256(str(incident).encode()).hexdigest()

@app.route('/incident', methods=['POST'])
def receive_incident():
    incident = request.get_json(force=True)
    inc_id = incident_id(incident)
    timestamp = datetime.utcnow().isoformat()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # Deduplicate
    c.execute('SELECT id FROM incidents WHERE id=?', (inc_id,))
    if c.fetchone():
        conn.close()
        return jsonify({'status': 'duplicate', 'id': inc_id}), 200
    # Store
    c.execute('INSERT INTO incidents (id, timestamp, incident_json) VALUES (?, ?, ?)',
              (inc_id, timestamp, str(incident)))
    conn.commit()
    conn.close()
    logging.info(f"Stored incident {inc_id}")
    return jsonify({'status': 'stored', 'id': inc_id}), 201

@app.route('/incidents', methods=['GET'])
def list_incidents():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT id, timestamp, incident_json FROM incidents ORDER BY timestamp DESC')
    rows = c.fetchall()
    conn.close()
    return jsonify([
        {'id': r[0], 'timestamp': r[1], 'incident': r[2]} for r in rows
    ])

@app.route('/incident/<inc_id>', methods=['GET'])
def get_incident(inc_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT id, timestamp, incident_json FROM incidents WHERE id=?', (inc_id,))
    row = c.fetchone()
    conn.close()
    if not row:
        return jsonify({'error': 'not found'}), 404
    return jsonify({'id': row[0], 'timestamp': row[1], 'incident': row[2]})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
