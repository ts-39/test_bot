#!/usr/bin/env python3
"""
Local Development Runner
Starts both server and client for local development and testing
"""

import os
import sys
import time
import signal
import subprocess
import threading
from pathlib import Path

class LocalRunner:
    """Manages local development environment"""
    
    def __init__(self):
        self.processes = []
        self.project_root = Path(__file__).parent.parent
        self.server_dir = self.project_root / "server"
        self.client_dir = self.project_root / "client"
        
    def check_requirements(self):
        """Check if all requirements are met"""
        print("🔍 Checking requirements...")
        
        if sys.version_info < (3, 10):
            raise Exception("Python 3.10+ is required")
        print("✅ Python version OK")
        
        try:
            result = subprocess.run(["node", "--version"], capture_output=True, text=True)
            if result.returncode != 0:
                raise Exception("Node.js not found")
            node_version = result.stdout.strip()
            print(f"✅ Node.js version: {node_version}")
        except FileNotFoundError:
            raise Exception("Node.js is not installed")
        
        venv_path = self.server_dir / "venv"
        if not venv_path.exists():
            print("⚠️  Virtual environment not found, creating...")
            self.setup_server_env()
        else:
            print("✅ Virtual environment exists")
        
        node_modules = self.client_dir / "node_modules"
        if not node_modules.exists():
            print("⚠️  Node modules not found, installing...")
            self.setup_client_env()
        else:
            print("✅ Node modules exist")
    
    def setup_server_env(self):
        """Set up Python server environment"""
        print("🔧 Setting up server environment...")
        
        os.chdir(self.server_dir)
        
        subprocess.run([sys.executable, "-m", "venv", "venv"], check=True)
        
        if os.name == 'nt':  # Windows
            pip_path = self.server_dir / "venv" / "Scripts" / "pip"
        else:  # Unix/Linux
            pip_path = self.server_dir / "venv" / "bin" / "pip"
        
        subprocess.run([str(pip_path), "install", "-r", "requirements.txt"], check=True)
        print("✅ Server environment setup complete")
    
    def setup_client_env(self):
        """Set up Node.js client environment"""
        print("🔧 Setting up client environment...")
        
        os.chdir(self.client_dir)
        subprocess.run(["npm", "install"], check=True)
        print("✅ Client environment setup complete")
    
    def start_server(self):
        """Start the FastAPI server"""
        print("🚀 Starting server...")
        
        os.chdir(self.server_dir)
        
        if os.name == 'nt':  # Windows
            python_path = self.server_dir / "venv" / "Scripts" / "python"
        else:  # Unix/Linux
            python_path = self.server_dir / "venv" / "bin" / "python"
        
        server_process = subprocess.Popen(
            [str(python_path), "main.py"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            bufsize=1
        )
        
        self.processes.append(("Server", server_process))
        
        def monitor_server():
            for line in server_process.stdout:
                print(f"[SERVER] {line.strip()}")
        
        server_thread = threading.Thread(target=monitor_server, daemon=True)
        server_thread.start()
        
        time.sleep(3)
        
        if server_process.poll() is None:
            print("✅ Server started successfully on http://localhost:8000")
        else:
            raise Exception("Server failed to start")
    
    def start_client(self):
        """Start the Vite development server"""
        print("🚀 Starting client...")
        
        os.chdir(self.client_dir)
        
        client_process = subprocess.Popen(
            ["npm", "run", "dev"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            bufsize=1
        )
        
        self.processes.append(("Client", client_process))
        
        def monitor_client():
            for line in client_process.stdout:
                print(f"[CLIENT] {line.strip()}")
        
        client_thread = threading.Thread(target=monitor_client, daemon=True)
        client_thread.start()
        
        time.sleep(5)
        
        if client_process.poll() is None:
            print("✅ Client started successfully on http://localhost:3000")
        else:
            raise Exception("Client failed to start")
    
    def run(self):
        """Run the complete local development environment"""
        try:
            print("🎯 Starting Google Meet Voice Bot - Local Development")
            print("=" * 60)
            
            self.check_requirements()
            
            self.start_server()
            
            self.start_client()
            
            print("\n" + "=" * 60)
            print("🎉 Local development environment is ready!")
            print("📱 Client: http://localhost:3000")
            print("🔧 Server: http://localhost:8000")
            print("📚 API Docs: http://localhost:8000/docs")
            print("\n💡 Tips:")
            print("  - Make sure to configure your .env files")
            print("  - Use scripts/recall_bot_manager.py to create bots")
            print("  - Press Ctrl+C to stop all services")
            print("=" * 60)
            
            try:
                while True:
                    time.sleep(1)
                    for name, process in self.processes:
                        if process.poll() is not None:
                            print(f"❌ {name} process died unexpectedly")
                            self.cleanup()
                            sys.exit(1)
            except KeyboardInterrupt:
                print("\n🛑 Shutting down...")
                self.cleanup()
        
        except Exception as e:
            print(f"❌ Error: {e}")
            self.cleanup()
            sys.exit(1)
    
    def cleanup(self):
        """Clean up all processes"""
        print("🧹 Cleaning up processes...")
        
        for name, process in self.processes:
            if process.poll() is None:
                print(f"  Stopping {name}...")
                process.terminate()
                
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    print(f"  Force killing {name}...")
                    process.kill()
        
        print("✅ Cleanup complete")

def main():
    """Main entry point"""
    runner = LocalRunner()
    
    def signal_handler(signum, frame):
        print("\n🛑 Received interrupt signal")
        runner.cleanup()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    runner.run()

if __name__ == "__main__":
    main()
