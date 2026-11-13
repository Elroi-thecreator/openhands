#!/usr/bin/env python3
"""
CLI Live Status Monitor for OpenHands (Antigravity Style)
Streams real-time agent actions, thoughts, and LLM load in the terminal.
"""

import time
import os
import sys

# Add gateway to path to reuse get_live_status_data
sys.path.append("/home/ubuntu/openhand/gateway")
from main import get_live_status_data

def main():
    print("\033[2J\033[H", end="") # Clear screen
    print("🚀 Antigravity OpenHands Live Monitor (Press Ctrl+C to exit)\n")
    
    last_id = None
    try:
        while True:
            data = get_live_status_data()
            state = data["agent_state"].upper()
            action = data["last_action"]
            ollama = f"{data['ollama_cpu']:.1f}% CPU" if data["ollama_active"] else "Idle"
            ram = f"{data['mem_avail_mb']/1024:.2f} GB free"
            
            # ANSI colors
            color = "\033[93m" if state == "THINKING" else ("\033[92m" if state == "RUNNING_ACTION" else "\033[95m")
            reset = "\033[0m"
            
            status_line = f"[{time.strftime('%H:%M:%S')}] {color}● {state}{reset} | Action: {action} | LLM: {ollama} | RAM: {ram}"
            print(f"\r{status_line}", end="", flush=True)
            
            # Print new events if any
            events = data.get("recent_events", [])
            if events:
                top_ev = events[0]
                if top_ev.get("id") != last_id:
                    last_id = top_ev.get("id")
                    print(f"\n  ↳ [{top_ev.get('source').upper()}] {top_ev.get('action')}: {top_ev.get('content')[:90]}")
            
            time.sleep(1.5)
    except KeyboardInterrupt:
        print("\n\nMonitor stopped.")

if __name__ == "__main__":
    main()
