#!/usr/bin/env python3
"""
Dominion Energy Extractor - Render.com Compatible Version
Uses environment variables for configuration
"""

import requests
import json
import os
from datetime import datetime, timedelta
from typing import Optional, Dict, List
import sys


class DominionEnergyExtractor:
    def __init__(self):
        """
        Initialize the extractor with environment variables
        """
        self.api_endpoint = os.getenv('API_ENDPOINT')
        self.api_key = os.getenv('API_KEY')
        self.days_ahead = int(os.getenv('DAYS_AHEAD', '7'))
        self.base_url = "https://www.dominionenergy.com/api/sched10/years/{year}/months/{month}"
        
        print(f"Initialized with API endpoint: {self.api_endpoint or 'None (test mode)'}")
    
    def get_dominion_data(self, year: int, month: str) -> Dict:
        """
        Fetch data from Dominion Energy API
        """
        url = self.base_url.format(year=year, month=month)
        
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error fetching data from Dominion Energy: {e}")
            raise
    
    def parse_date(self, date_str: str) -> Optional[datetime]:
        """
        Parse the Microsoft JSON date format /Date(timestamp)/
        """
        if not date_str or date_str == "null":
            return None
        
        try:
            timestamp_ms = int(date_str.split('(')[1].split(')')[0])
            timestamp_s = timestamp_ms / 1000
            return datetime.fromtimestamp(timestamp_s)
        except (ValueError, IndexError) as e:
            print(f"Error parsing date {date_str}: {e}")
            return None
    
    def extract_schedule_data(self, data: Dict) -> List[Dict]:
        """
        Extract schedule data from the API response
        """
        schedule = []
        
        if 'Weeks' not in data:
            return schedule
        
        for week in data['Weeks']:
            if 'Days' not in week:
                continue
                
            for day_data in week['Days']:
                if day_data.get('Date') and day_data['Date'] != "null":
                    date_obj = self.parse_date(day_data['Date'])
                    if not date_obj:
                        continue
                    
                    designation = day_data.get('Designation')
                    
                    if designation and designation in ['A', 'B', 'C']:
                        schedule.append({
                            'date': date_obj.strftime('%Y-%m-%d'),
                            'day': int(day_data['Day']),
                            'designation': designation,
                            'timestamp': date_obj.isoformat()
                        })
        
        return sorted(schedule, key=lambda x: x['date'])
    
    def get_next_designation(self, schedule: List[Dict]) -> Optional[Dict]:
        """
        Get the designation for the next upcoming date
        """
        today = datetime.now().date()
        
        for entry in schedule:
            entry_date = datetime.fromisoformat(entry['timestamp']).date()
            if entry_date >= today:
                return entry
        
        return None
    
    def publish_to_api(self, data: Dict) -> bool:
        """
        Publish extracted data to your API endpoint
        """
        if not self.api_endpoint:
            print("No API endpoint configured. Skipping publish.")
            return False
        
        headers = {
            'Content-Type': 'application/json'
        }
        
        if self.api_key:
            headers['Authorization'] = f'Bearer {self.api_key}'
        
        try:
            response = requests.post(
                self.api_endpoint,
                json=data,
                headers=headers,
                timeout=10
            )
            response.raise_for_status()
            print(f"✓ Successfully published data to API: {response.status_code}")
            return True
        except requests.exceptions.RequestException as e:
            print(f"✗ Error publishing to API: {e}")
            return False
    
    def run(self) -> Dict:
        """
        Main execution method
        """
        now = datetime.now()
        current_year = now.year
        current_month = now.strftime('%B')
        
        print(f"[{now.strftime('%Y-%m-%d %H:%M:%S')}] Fetching data for {current_month} {current_year}...")
        
        try:
            # Fetch current month data
            data = self.get_dominion_data(current_year, current_month)
            schedule = self.extract_schedule_data(data)
            
            # Check if we need next month's data
            end_date = (now + timedelta(days=self.days_ahead)).date()
            last_schedule_date = datetime.fromisoformat(schedule[-1]['timestamp']).date() if schedule else now.date()
            
            if end_date > last_schedule_date:
                next_month_date = now.replace(day=28) + timedelta(days=4)
                next_month = next_month_date.strftime('%B')
                next_year = next_month_date.year
                
                print(f"Fetching data for {next_month} {next_year}...")
                next_data = self.get_dominion_data(next_year, next_month)
                next_schedule = self.extract_schedule_data(next_data)
                schedule.extend(next_schedule)
            
            # Get upcoming schedule
            upcoming_schedule = []
            for entry in schedule:
                entry_date = datetime.fromisoformat(entry['timestamp']).date()
                if now.date() <= entry_date <= end_date:
                    upcoming_schedule.append(entry)
            
            # Get next designation
            next_entry = self.get_next_designation(schedule)
            
            if not next_entry:
                print("Warning: No upcoming designation found!")
            
            # Prepare payload
            payload = {
                'fetched_at': now.isoformat(),
                'next_designation': next_entry,
                'upcoming_schedule': upcoming_schedule,
                'summary': {
                    'total_upcoming': len(upcoming_schedule),
                    'A_count': sum(1 for e in upcoming_schedule if e['designation'] == 'A'),
                    'B_count': sum(1 for e in upcoming_schedule if e['designation'] == 'B'),
                    'C_count': sum(1 for e in upcoming_schedule if e['designation'] == 'C')
                }
            }
            
            # Print summary
            if next_entry:
                print(f"\n✓ Next designation: {next_entry['designation']} on {next_entry['date']}")
            print(f"✓ Upcoming schedule ({self.days_ahead} days): {len(upcoming_schedule)} entries")
            print(f"  A: {payload['summary']['A_count']}")
            print(f"  B: {payload['summary']['B_count']}")
            print(f"  C: {payload['summary']['C_count']}")
            
            # Publish to API
            if self.publish_to_api(payload):
                print("✓ Data published successfully")
            
            return payload
            
        except Exception as e:
            error_msg = f"Error during extraction: {e}"
            print(f"✗ {error_msg}")
            raise


def main():
    """Main entry point"""
    print("=== Dominion Energy Extractor (Render.com) ===\n")
    
    try:
        extractor = DominionEnergyExtractor()
        payload = extractor.run()
        print("\n=== Extraction completed successfully ===")
        sys.exit(0)
        
    except Exception as e:
        print(f"\n=== Extraction failed: {e} ===")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
