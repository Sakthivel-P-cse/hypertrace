# Step 1: How to Export Incident Signals

## 1. Configure Prometheus Alertmanager
- Use the provided `alertmanager-webhook-example.yml` snippet.
- Add it to your Alertmanager config under `receivers`.
- Set the webhook URL to your incident processing service endpoint.

## 2. Run the Incident Receiver Service
- Use the provided `incident_receiver.py` (Flask app).
- Start with: `python3 incident_receiver.py`
- The service listens on port 5000 for POST requests at `/incident`.

## 3. Test the Integration
- Trigger an alert in Prometheus.
- Alertmanager will POST a JSON payload to the receiver.
- The receiver logs and acknowledges the incident.

## Next Steps
- Extend the receiver to deduplicate and store incidents (Step 2).
- Integrate with your monitoring stack for end-to-end flow.

---

**Files Added:**
- `docker/configs/alertmanager-webhook-example.yml`: Alertmanager webhook config example.
- `examples/incident_receiver.py`: Python Flask service to receive incident signals.
