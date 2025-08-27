#!/usr/bin/env python3
"""
Recall.ai Bot Management Script
Handles creation, management, and termination of Recall.ai bots for Google Meet
"""

import os
import sys
import json
import time
import requests
import argparse
from typing import Dict, Any, Optional
from dotenv import load_dotenv

script_dir = os.path.dirname(os.path.abspath(__file__))
server_env_path = os.path.join(script_dir, '..', 'server', '.env')
load_dotenv(server_env_path)

class RecallBotManager:
    """Manager for Recall.ai bot operations"""
    
    def __init__(self):
        self.api_key = os.getenv("RECALL_API_KEY")
        if not self.api_key:
            raise ValueError("RECALL_API_KEY not found in environment variables")
        
        self.base_url = "https://api.recall.ai/api/v1"
        self.headers = {
            "Authorization": f"Token {self.api_key}",
            "Content-Type": "application/json"
        }
        
        self.bot_name = os.getenv("RECALL_BOT_NAME", "VoiceBot")
        self.webpage_url = os.getenv("WEBPAGE_URL", "http://localhost:3000")
        
    def create_bot(self, meeting_url: str, bot_name: Optional[str] = None) -> Dict[str, Any]:
        """Create a new Recall.ai bot for the specified meeting"""
        
        if not meeting_url:
            raise ValueError("Meeting URL is required")
        
        bot_name = bot_name or self.bot_name
        
        payload = {
            "meeting_url": meeting_url,
            "bot_name": bot_name,
            "transcription_options": {
                "provider": "meeting_captions"
            },
            "chat_options": {
                "on_bot_join": {
                    "send_to": "everyone",
                    "message": f"こんにちは！{bot_name}が会議に参加しました。音声で話しかけてください。"
                }
            },
            "recording_mode": "speaker_view",
            "recording_mode_options": {
                "participant_video_when_screenshare": "hide"
            },
            "automatic_leave": {
                "waiting_room_timeout": 1200,
                "noone_joined_timeout": 1200
            },
            "real_time_media": {
                "rtmp_destination_url": None,
                "websocket_video_destination_url": None,
                "websocket_audio_destination_url": None,
                "websocket_speaker_timeline_destination_url": None,
                "webhook_call_events_destination_url": None
            },
            "calendar_meetings": [],
            "automatic_video_output": {
                "in_call_recording": {
                    "b64_data": None,
                    "kind": "jpeg"
                },
                "automated_video_output": {
                    "webpage": {
                        "url": self.webpage_url,
                        "display_name": bot_name,
                        "width": 1280,
                        "height": 720
                    }
                }
            }
        }
        
        try:
            print(f"Creating bot '{bot_name}' for meeting: {meeting_url}")
            response = requests.post(
                f"{self.base_url}/bot",
                headers=self.headers,
                json=payload,
                timeout=30
            )
            
            if response.status_code == 201:
                bot_data = response.json()
                print(f"✅ Bot created successfully!")
                print(f"Bot ID: {bot_data['id']}")
                print(f"Status: {bot_data['status_changes'][-1]['code'] if bot_data.get('status_changes') else 'unknown'}")
                
                self._save_bot_info(bot_data)
                
                return bot_data
            else:
                error_msg = f"Failed to create bot: {response.status_code} - {response.text}"
                print(f"❌ {error_msg}")
                raise Exception(error_msg)
                
        except requests.exceptions.RequestException as e:
            error_msg = f"Network error creating bot: {str(e)}"
            print(f"❌ {error_msg}")
            raise Exception(error_msg)
    
    def get_bot_status(self, bot_id: str) -> Dict[str, Any]:
        """Get current status of a bot"""
        try:
            response = requests.get(
                f"{self.base_url}/bot/{bot_id}",
                headers=self.headers,
                timeout=10
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                raise Exception(f"Failed to get bot status: {response.status_code} - {response.text}")
                
        except requests.exceptions.RequestException as e:
            raise Exception(f"Network error getting bot status: {str(e)}")
    
    def list_bots(self) -> Dict[str, Any]:
        """List all active bots"""
        try:
            response = requests.get(
                f"{self.base_url}/bot",
                headers=self.headers,
                timeout=10
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                raise Exception(f"Failed to list bots: {response.status_code} - {response.text}")
                
        except requests.exceptions.RequestException as e:
            raise Exception(f"Network error listing bots: {str(e)}")
    
    def delete_bot(self, bot_id: str) -> bool:
        """Delete/terminate a bot"""
        try:
            print(f"Terminating bot: {bot_id}")
            response = requests.delete(
                f"{self.base_url}/bot/{bot_id}",
                headers=self.headers,
                timeout=10
            )
            
            if response.status_code == 204:
                print(f"✅ Bot {bot_id} terminated successfully")
                self._remove_bot_info(bot_id)
                return True
            else:
                error_msg = f"Failed to delete bot: {response.status_code} - {response.text}"
                print(f"❌ {error_msg}")
                return False
                
        except requests.exceptions.RequestException as e:
            error_msg = f"Network error deleting bot: {str(e)}"
            print(f"❌ {error_msg}")
            return False
    
    def wait_for_bot_ready(self, bot_id: str, timeout: int = 60) -> bool:
        """Wait for bot to be ready and join the meeting"""
        print(f"Waiting for bot {bot_id} to join meeting...")
        
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                bot_status = self.get_bot_status(bot_id)
                current_status = bot_status.get('status_changes', [])
                
                if current_status:
                    latest_status = current_status[-1]['code']
                    print(f"Bot status: {latest_status}")
                    
                    if latest_status == 'in_call_recording':
                        print(f"✅ Bot successfully joined the meeting!")
                        return True
                    elif latest_status in ['call_ended', 'fatal']:
                        print(f"❌ Bot failed to join: {latest_status}")
                        return False
                
                time.sleep(2)
                
            except Exception as e:
                print(f"Error checking bot status: {e}")
                time.sleep(2)
        
        print(f"❌ Timeout waiting for bot to join meeting")
        return False
    
    def _save_bot_info(self, bot_data: Dict[str, Any]):
        """Save bot information to local file"""
        try:
            bots_file = "active_bots.json"
            
            if os.path.exists(bots_file):
                with open(bots_file, 'r') as f:
                    bots = json.load(f)
            else:
                bots = {}
            
            bots[bot_data['id']] = {
                'id': bot_data['id'],
                'meeting_url': bot_data.get('meeting_url'),
                'bot_name': bot_data.get('bot_name'),
                'created_at': bot_data.get('created_at'),
                'status': bot_data.get('status_changes', [])[-1]['code'] if bot_data.get('status_changes') else 'unknown'
            }
            
            with open(bots_file, 'w') as f:
                json.dump(bots, f, indent=2)
                
        except Exception as e:
            print(f"Warning: Failed to save bot info: {e}")
    
    def _remove_bot_info(self, bot_id: str):
        """Remove bot information from local file"""
        try:
            bots_file = "active_bots.json"
            
            if os.path.exists(bots_file):
                with open(bots_file, 'r') as f:
                    bots = json.load(f)
                
                if bot_id in bots:
                    del bots[bot_id]
                    
                    with open(bots_file, 'w') as f:
                        json.dump(bots, f, indent=2)
                        
        except Exception as e:
            print(f"Warning: Failed to remove bot info: {e}")

def main():
    """Main CLI interface"""
    parser = argparse.ArgumentParser(description="Recall.ai Bot Manager")
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    create_parser = subparsers.add_parser('create', help='Create a new bot')
    create_parser.add_argument('meeting_url', help='Google Meet URL')
    create_parser.add_argument('--name', help='Bot name (optional)')
    create_parser.add_argument('--wait', action='store_true', help='Wait for bot to join meeting')
    
    list_parser = subparsers.add_parser('list', help='List all active bots')
    
    status_parser = subparsers.add_parser('status', help='Get bot status')
    status_parser.add_argument('bot_id', help='Bot ID')
    
    delete_parser = subparsers.add_parser('delete', help='Delete/terminate a bot')
    delete_parser.add_argument('bot_id', help='Bot ID')
    
    cleanup_parser = subparsers.add_parser('cleanup', help='Delete all active bots')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    try:
        manager = RecallBotManager()
        
        if args.command == 'create':
            bot_data = manager.create_bot(args.meeting_url, args.name)
            
            if args.wait:
                success = manager.wait_for_bot_ready(bot_data['id'])
                if not success:
                    print("Bot creation completed but failed to join meeting properly")
                    sys.exit(1)
        
        elif args.command == 'list':
            bots = manager.list_bots()
            print(f"Active bots: {len(bots.get('results', []))}")
            for bot in bots.get('results', []):
                status = bot.get('status_changes', [])[-1]['code'] if bot.get('status_changes') else 'unknown'
                print(f"  {bot['id']}: {bot.get('bot_name', 'Unknown')} - {status}")
        
        elif args.command == 'status':
            bot_status = manager.get_bot_status(args.bot_id)
            print(f"Bot {args.bot_id}:")
            print(f"  Name: {bot_status.get('bot_name', 'Unknown')}")
            print(f"  Meeting: {bot_status.get('meeting_url', 'Unknown')}")
            status = bot_status.get('status_changes', [])[-1]['code'] if bot_status.get('status_changes') else 'unknown'
            print(f"  Status: {status}")
        
        elif args.command == 'delete':
            success = manager.delete_bot(args.bot_id)
            if not success:
                sys.exit(1)
        
        elif args.command == 'cleanup':
            bots = manager.list_bots()
            for bot in bots.get('results', []):
                print(f"Deleting bot: {bot['id']}")
                manager.delete_bot(bot['id'])
    
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
