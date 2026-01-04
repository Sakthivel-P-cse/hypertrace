# Incident Processing Service (Step 1 Receiver)
# Save as incident_receiver.py
from flask import Flask, request, jsonify
import logging

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

@app.route('/incident', methods=['POST'])
def receive_incident():
    data = request.get_json(force=True)
    logging.info(f"Received incident: {data}")
    # For now, just log and echo back
    return jsonify({'status': 'received', 'incident': data}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
