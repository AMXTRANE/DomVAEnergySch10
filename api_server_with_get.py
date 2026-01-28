#!/usr/bin/env python3
"""
API Server with JSONBin.io Storage
"""

from flask import Flask, request, jsonify
from datetime import datetime
import json
import os
import requests

app = Flask(__name__)

# Configuration
API_KEY = os.getenv('API_KEY', 'your-secret-api-key-here')
JSONBIN_API_KEY = os.getenv('JSONBIN_API_KEY')
JSONBIN_BIN_ID = os.getenv('JSONBIN_BIN_ID')


def load_schedule():
    """Load the latest schedule from JSONBin.io"""
    if not JSONBIN_API_KEY or not JSONBIN_BIN_ID:
        return {'error': 'JSONBin not configured'}
    
    try:
        url = f'https://api.jsonbin.io/v3/b/{JSONBIN_BIN_ID}/latest'
        headers = {
            'X-Access-Key': JSONBIN_API_KEY
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        return data.get('record', {})
        
    except Exception as e:
        print(f"Error loading from JSONBin: {e}")
        return {'error': 'Failed to load data', 'message': str(e)}


def save_schedule(data):
    """Save schedule to JSONBin.io"""
    if not JSONBIN_API_KEY or not JSONBIN_BIN_ID:
        print("JSONBin not configured")
        return False
    
    try:
        data['received_at'] = datetime.now().isoformat()
        
        url = f'https://api.jsonbin.io/v3/b/{JSONBIN_BIN_ID}'
        headers = {
            'Content-Type': 'application/json',
            'X-Access-Key': JSONBIN_API_KEY
        }
        
        response = requests.put(url, json=data, headers=headers, timeout=10)
        response.raise_for_status()
        
        print("✓ Data saved to JSONBin")
        return True
        
    except Exception as e:
        print(f"✗ Error saving to JSONBin: {e}")
        return False


@app.route('/dominion-schedule', methods=['POST'])
def receive_schedule():
    """POST endpoint - receives schedule data"""
    
    # Verify API key
    auth_header = request.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer ') or auth_header[7:] != API_KEY:
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        data = request.json
    except Exception as e:
        return jsonify({'error': 'Invalid JSON'}), 400
    
    # Validate
    required_fields = ['fetched_at', 'next_designation', 'upcoming_schedule', 'summary']
    missing_fields = [field for field in required_fields if field not in data]
    
    if missing_fields:
        return jsonify({'error': 'Missing required fields', 'missing': missing_fields}), 400
    
    # Save the data
    try:
        if save_schedule(data):
            next_des = data['next_designation']
            
            print(f"\n=== Received Schedule Update ===")
            print(f"Next: {next_des['designation'] if next_des else 'None'} on {next_des['date'] if next_des else 'N/A'}")
            
            return jsonify({
                'status': 'success',
                'message': 'Schedule data received and stored',
                'next_designation': next_des['designation'] if next_des else None,
                'next_date': next_des['date'] if next_des else None
            }), 200
        else:
            return jsonify({'error': 'Failed to save data'}), 500
            
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({'error': 'Processing failed', 'message': str(e)}), 500


@app.route('/api/designation', methods=['GET'])
def get_designation_only():
    """Returns just the letter: A, B, or C"""
    data = load_schedule()
    
    if 'error' in data or data.get('status') == 'no_data':
        return "ERROR", 404
    
    next_des = data.get('next_designation')
    if not next_des:
        return "NONE", 404
    
    return next_des['designation'], 200


@app.route('/api/next', methods=['GET'])
def get_next_designation():
    """Returns next designation with details"""
    data = load_schedule()
    
    if 'error' in data or data.get('status') == 'no_data':
        return jsonify({'error': 'No data available'}), 404
    
    next_des = data.get('next_designation')
    if not next_des:
        return jsonify({'error': 'No upcoming designation found'}), 404
    
    return jsonify({
        'designation': next_des['designation'],
        'date': next_des['date'],
        'day': next_des['day'],
        'timestamp': next_des['timestamp'],
        'fetched_at': data.get('fetched_at'),
        'received_at': data.get('received_at')
    }), 200


@app.route('/api/today', methods=['GET'])
def get_today_designation():
    """Returns today's designation"""
    data = load_schedule()
    
    if 'error' in data or data.get('status') == 'no_data':
        return jsonify({'error': 'No data available'}), 404
    
    today = datetime.now().date().isoformat()
    upcoming = data.get('upcoming_schedule', [])
    
    for entry in upcoming:
        if entry['date'] == today:
            return jsonify({
                'date': entry['date'],
                'designation': entry['designation'],
                'day': entry['day'],
                'is_today': True
            }), 200
    
    return jsonify({'error': 'No designation for today'}), 404


@app.route('/api/upcoming', methods=['GET'])
def get_upcoming_days():
    """Returns upcoming schedule"""
    data = load_schedule()
    
    if 'error' in data or data.get('status') == 'no_data':
        return jsonify({'error': 'No data available'}), 404
    
    upcoming = data.get('upcoming_schedule', [])
    
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
    """Returns summary statistics"""
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
        'has_data': 'next_designation' in data and data.get('status') != 'no_data',
        'last_update': data.get('received_at', 'never'),
        'storage': 'jsonbin.io'
    }), 200


@app.route('/', methods=['GET'])
def index():
    """API documentation"""
    return jsonify({
        'name': 'Dominion Energy Schedule API',
        'version': '3.0',
        'storage': 'JSONBin.io',
        'endpoints': {
            'GET /api/designation': 'Returns just the letter (A, B, or C)',
            'GET /api/next': 'Returns next designation with details',
            'GET /api/today': 'Returns today\'s designation',
            'GET /api/upcoming': 'Returns upcoming schedule',
            'GET /api/summary': 'Returns summary statistics',
            'POST /dominion-schedule': 'Receives data from extractor (requires API key)',
            'GET /health': 'Health check'
        }
    }), 200


if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    print("=== Dominion Energy API with JSONBin.io ===")
    print(f"Storage: JSONBin.io")
    print(f"Port: {port}\n")
    
    app.run(host='0.0.0.0', port=port, debug=False)
