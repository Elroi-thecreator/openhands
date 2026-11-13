from flask import Flask, render_template, jsonify, request
import json
import os

app = Flask(__name__)

# Simple persistence or in-memory state for stats if needed
STATS_FILE = os.path.join(os.path.dirname(__file__), 'stats.json')

def load_stats():
    if os.path.exists(STATS_FILE):
        try:
            with open(STATS_FILE, 'r') as f:
                return json.load(f)
        except Exception:
            pass
    return {"total_minutes": 0, "completed_sessions": 0, "history": []}

def save_stats(stats):
    try:
        with open(STATS_FILE, 'w') as f:
            json.dump(stats, f)
    except Exception:
        pass

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/stats', methods=['GET', 'POST'])
def handle_stats():
    if request.method == 'POST':
        data = request.json or {}
        stats = load_stats()
        stats['total_minutes'] += data.get('minutes', 0)
        stats['completed_sessions'] += 1
        stats['history'].append(data)
        save_stats(stats)
        return jsonify({"status": "success", "stats": stats})
    else:
        return jsonify(load_stats())

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 53029))
    app.run(host='0.0.0.0', port=port, debug=False)
