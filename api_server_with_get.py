#!/usr/bin/env python3
"""
Dominion Energy Schedule API Receiver with Persistent Storage

This Flask app receives schedule data via POST and serves it via GET endpoints.
Stores data in a JSON file that persists between requests.
"""

from flask import Flask, request, jsonify
from datetime import datetime
import json
import os
from pathlib import Path

app = Flask(__name__)

# Configuration
API_KEY = os.getenv('API_KEY', 'RicService')
DATA_FILE = os.getenv('DATA_FILE', 'latest_schedule.json')

# Ensure data file exists
if not os.path.exists(DATA_FILE):
    with open(DATA_FILE, 'w') as f:
        json.dump({'status': 'no_data', 'message': 'Waiting for first update'}, f)


def load_schedule():
    """Load the latest schedule from file"""
    try:
        with open(DATA_FILE, 'r') as f:
            return json.load(f)
    except Exception as e:
        return {'error': 'Failed to load data', 'message': str(e)}


def save_schedule(data):
    """Save schedule to file"""
    data['received_at'] = datetime.now().isoformat()
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f, indent=2)


@app.route('/dominion-schedule', methods=['POST'])
def receive_schedule():
    """
    POST endpoint - receives schedule data from the extractor
    
    Authorization: Bearer YOUR_API_KEY
    Content-Type: application/json
    """
    
    # Verify API key
    auth_header = request.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer ') or auth_header[7:] != API_KEY:
        return jsonify({
            'error': 'Unauthorized',
            'message': 'Invalid or missing API key'
        }), 401
    
    # Get JSON data
    try:
        data = request.json
    except Exception as e:
        return jsonify({
            'error': 'Invalid JSON',
            'message': str(e)
        }), 400
    
    # Validate required fields
    required_fields = ['fetched_at', 'next_designation', 'upcoming_schedule', 'summary']
    missing_fields = [field for field in required_fields if field not in data]
    
    if missing_fields:
        return jsonify({
            'error': 'Missing required fields',
            'missing': missing_fields
        }), 400
    
    # Save the data
    try:
        save_schedule(data)
        
        next_des = data['next_designation']
        summary = data['summary']
        
        print(f"\n=== Received Schedule Update ===")
        print(f"Fetched at: {data['fetched_at']}")
        if next_des:
            print(f"Next designation: {next_des['designation']} on {next_des['date']}")
        print(f"Upcoming schedule: {summary['total_upcoming']} entries")
        print(f"  A: {summary['A_count']}, B: {summary['B_count']}, C: {summary['C_count']}")
        
        return jsonify({
            'status': 'success',
            'message': 'Schedule data received and stored',
            'next_designation': next_des['designation'] if next_des else None,
            'next_date': next_des['date'] if next_des else None
        }), 200
        
    except Exception as e:
        print(f"Error saving data: {e}")
        return jsonify({
            'error': 'Failed to save data',
            'message': str(e)
        }), 500


@app.route('/dominion-schedule', methods=['GET'])
@app.route('/api/schedule', methods=['GET'])
def get_full_schedule():
    """
    GET endpoint - returns the complete schedule data
    
    Example: curl https://your-api.com/dominion-schedule
    
    Returns:
    {
      "fetched_at": "2026-01-27T18:00:00",
      "next_designation": {...},
      "upcoming_schedule": [...],
      "summary": {...}
    }
    """
    data = load_schedule()
    
    if 'error' in data:
        return jsonify(data), 500
    
    if data.get('status') == 'no_data':
        return jsonify(data), 404
    
    return jsonify(data), 200


@app.route('/api/next', methods=['GET'])
@app.route('/dominion-schedule/next', methods=['GET'])
def get_next_designation():
    """
    GET endpoint - returns only the next designation (simplified)
    
    Example: curl https://your-api.com/api/next
    
    Returns:
    {
      "designation": "A",
      "date": "2026-01-27",
      "day": 27,
      "fetched_at": "2026-01-27T18:00:00"
    }
    """
    data = load_schedule()
    
    if 'error' in data:
        return jsonify(data), 500
    
    if data.get('status') == 'no_data':
        return jsonify({'error': 'No data available'}), 404
    
    next_des = data.get('next_designation')
    
    if not next_des:
        return jsonify({'error': 'No upcoming designation found'}), 404
    
    return jsonify({
        'designation': next_des['designation'],
        'date': next_des['date'],
        'day': next_des['day'],
        'timestamp': next_des['timestamp'],
        'fetched_at': data['fetched_at'],
        'received_at': data.get('received_at')
    }), 200


@app.route('/api/designation', methods=['GET'])
def get_designation_only():
    """
    GET endpoint - returns ONLY the designation letter (A, B, or C)
    
    Example: curl https://your-api.com/api/designation
    
    Returns plain text: "A" or "B" or "C"
    
    This is the simplest endpoint for devices that just need the letter.
    """
    data = load_schedule()
    
    if 'error' in data or data.get('status') == 'no_data':
        return "ERROR", 404
    
    next_des = data.get('next_designation')
    
    if not next_des:
        return "NONE", 404
    
    return next_des['designation'], 200


@app.route('/api/today', methods=['GET'])
def get_today_designation():
    """
    GET endpoint - returns today's designation (if available)
    
    Example: curl https://your-api.com/api/today
    
    Returns:
    {
      "date": "2026-01-27",
      "designation": "A",
      "day": 27
    }
    """
    data = load_schedule()
    
    if 'error' in data or data.get('status') == 'no_data':
        return jsonify({'error': 'No data available'}), 404
    
    today = datetime.now().date().isoformat()
    
    # Search in upcoming schedule for today
    upcoming = data.get('upcoming_schedule', [])
    
    for entry in upcoming:
        if entry['date'] == today:
            return jsonify({
                'date': entry['date'],
                'designation': entry['designation'],
                'day': entry['day'],
                'is_today': True
            }), 200
    
    return jsonify({
        'error': 'No designation for today',
        'message': 'Today might not have a designation or data needs update'
    }), 404


@app.route('/api/upcoming', methods=['GET'])
def get_upcoming_days():
    """
    GET endpoint - returns upcoming schedule with optional limit
    
    Query params:
      - limit: number of days to return (default: all)
      - designation: filter by A, B, or C
    
    Example: curl https://your-api.com/api/upcoming?limit=3&designation=A
    
    Returns:
    {
      "upcoming": [
        {"date": "2026-01-27", "designation": "A", "day": 27},
        {"date": "2026-01-28", "designation": "B", "day": 28}
      ],
      "count": 2
    }
    """
    data = load_schedule()
    
    if 'error' in data or data.get('status') == 'no_data':
        return jsonify({'error': 'No data available'}), 404
    
    upcoming = data.get('upcoming_schedule', [])
    
    # Apply filters
    limit = request.args.get('limit', type=int)
    designation_filter = request.args.get('designation', '').upper()
    
    if designation_filter and designation_filter in ['A', 'B', 'C']:
        upcoming = [e for e in upcoming if e['designation'] == designation_filter]
    
    if limit and limit > 0:
        upcoming = upcoming[:limit]
    
    return jsonify({
        'upcoming': upcoming,
        'count': len(upcoming),
        'total_available': len(data.get('upcoming_schedule', []))
    }), 200


@app.route('/api/summary', methods=['GET'])
def get_summary():
    """
    GET endpoint - returns summary statistics
    
    Example: curl https://your-api.com/api/summary
    
    Returns:
    {
      "total_upcoming": 7,
      "A_count": 1,
      "B_count": 4,
      "C_count": 2,
      "next_designation": "A",
      "next_date": "2026-01-27"
    }
    """
    data = load_schedule()
    
    if 'error' in data or data.get('status') == 'no_data':
        return jsonify({'error': 'No data available'}), 404
    
    summary = data.get('summary', {})
    next_des = data.get('next_designation', {})
    
    return jsonify({
        'total_upcoming': summary.get('total_upcoming', 0),
        'A_count': summary.get('A_count', 0),
        'B_count': summary.get('B_count', 0),
        'C_count': summary.get('C_count', 0),
        'next_designation': next_des.get('designation') if next_des else None,
        'next_date': next_des.get('date') if next_des else None,
        'fetched_at': data.get('fetched_at'),
        'received_at': data.get('received_at')
    }), 200


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    data = load_schedule()
    
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'has_data': 'next_designation' in data,
        'last_update': data.get('received_at', 'never')
    }), 200


@app.route('/', methods=['GET'])
def index():
    """Root endpoint with API documentation"""
    return jsonify({
        'name': 'Dominion Energy Schedule API',
        'version': '1.0',
        'endpoints': {
            'GET /api/designation': 'Returns just the letter (A, B, or C) - simplest',
            'GET /api/next': 'Returns next designation with details',
            'GET /api/today': 'Returns today\'s designation',
            'GET /api/upcoming': 'Returns upcoming schedule (supports ?limit=N&designation=A)',
            'GET /api/summary': 'Returns summary statistics',
            'GET /dominion-schedule': 'Returns complete schedule data',
            'POST /dominion-schedule': 'Receives data from extractor (requires API key)',
            'GET /health': 'Health check'
        },
        'examples': {
            'Simple GET': 'curl https://your-api.com/api/designation',
            'Next designation': 'curl https://your-api.com/api/next',
            'Today only': 'curl https://your-api.com/api/today',
            'Next 3 days': 'curl https://your-api.com/api/upcoming?limit=3',
            'All A days': 'curl https://your-api.com/api/upcoming?designation=A'
        }
    }), 200


if __name__ == '__main__':
    print("=== Dominion Energy Schedule API ===")
    print("\nEndpoints for your device to call:")
    print("  Simplest: GET /api/designation       → Returns: A, B, or C")
    print("  Details:  GET /api/next              → Returns: JSON with date/designation")
    print("  Today:    GET /api/today             → Returns: Today's designation")
    print("  Upcoming: GET /api/upcoming          → Returns: All upcoming days")
    print("  Summary:  GET /api/summary           → Returns: Statistics")
    print("\nReceive endpoint (for extractor):")
    print("  POST /dominion-schedule              → Receives schedule updates")
    print(f"\nAPI Key: {API_KEY}")
    print(f"Data file: {DATA_FILE}")
    print("\nStarting server on http://0.0.0.0:5000")
    print("Press Ctrl+C to stop\n")
    
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)), debug=False)
