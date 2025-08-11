#!/usr/bin/env python3
"""
Multi-File Dynamic Runner with Real-Time Log Display
Runs multiple Python files concurrently and shows their output in real-time.
"""

import subprocess
import threading
import time
import glob
import sys
import os
from datetime import datetime
import queue
import select
from colorama import init, Fore, Back, Style
import json

# Initialize colorama for cross-platform colored output
init(autoreset=True)

class Colors:
    """Color scheme for different files"""
    COLORS = [
        Fore.CYAN,
        Fore.GREEN, 
        Fore.YELLOW,
        Fore.MAGENTA,
        Fore.BLUE,
        Fore.RED,
        Fore.WHITE
    ]
    
    @classmethod
    def get_color(cls, index):
        return cls.COLORS[index % len(cls.COLORS)]

class RealTimeMultiRunner:
    def __init__(self):
        self.processes = {}
        self.threads = {}
        self.output_queues = {}
        self.running = True
        self.file_colors = {}
        
    def assign_colors(self, filenames):
        """Assign unique colors to each file"""
        for i, filename in enumerate(filenames):
            self.file_colors[filename] = Colors.get_color(i)
    
    def read_output(self, process, filename, stream_type='stdout'):
        """Read output from a process in a separate thread"""
        try:
            if stream_type == 'stdout':
                stream = process.stdout
            else:
                stream = process.stderr
                
            while self.running and process.poll() is None:
                line = stream.readline()
                if line:
                    # Decode and clean the line
                    try:
                        line_text = line.decode('utf-8', errors='ignore').rstrip()
                    except:
                        line_text = str(line).rstrip()
                    
                    if line_text:
                        timestamp = datetime.now().strftime("%H:%M:%S")
                        color = self.file_colors.get(filename, Fore.WHITE)
                        
                        # Format the output with colors
                        if stream_type == 'stderr':
                            prefix = f"{color}[{filename}:{timestamp}] {Fore.RED}ERROR: "
                        else:
                            prefix = f"{color}[{filename}:{timestamp}] "
                        
                        formatted_line = f"{prefix}{line_text}{Style.RESET_ALL}"
                        print(formatted_line, flush=True)
                        
        except Exception as e:
            error_msg = f"{Fore.RED}[{filename}] Output reading error: {e}{Style.RESET_ALL}"
            print(error_msg, flush=True)
    
    def start_process(self, filepath):
        """Start a Python process and capture its output"""
        filename = os.path.basename(filepath)
        
        try:
            # Start the process with pipes for stdout and stderr
            process = subprocess.Popen(
                [sys.executable, filepath],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=1,  # Line buffered
                universal_newlines=False,
                cwd=os.path.dirname(filepath) or os.getcwd()
            )
            
            self.processes[filename] = process
            
            # Start threads to read stdout and stderr
            stdout_thread = threading.Thread(
                target=self.read_output,
                args=(process, filename, 'stdout'),
                daemon=True
            )
            stderr_thread = threading.Thread(
                target=self.read_output,
                args=(process, filename, 'stderr'),
                daemon=True
            )
            
            stdout_thread.start()
            stderr_thread.start()
            
            self.threads[f"{filename}_stdout"] = stdout_thread
            self.threads[f"{filename}_stderr"] = stderr_thread
            
            color = self.file_colors.get(filename, Fore.WHITE)
            print(f"{color}[RUNNER] Started {filename} (PID: {process.pid}){Style.RESET_ALL}")
            
            return True
            
        except Exception as e:
            print(f"{Fore.RED}[RUNNER] Failed to start {filename}: {e}{Style.RESET_ALL}")
            return False
    
    def monitor_processes(self):
        """Monitor all running processes"""
        while self.running and self.processes:
            finished_processes = []
            
            for filename, process in self.processes.items():
                if process.poll() is not None:  # Process has finished
                    color = self.file_colors.get(filename, Fore.WHITE)
                    return_code = process.returncode
                    
                    if return_code == 0:
                        status_msg = f"{color}[RUNNER] {filename} completed successfully{Style.RESET_ALL}"
                    else:
                        status_msg = f"{Fore.RED}[RUNNER] {filename} exited with code {return_code}{Style.RESET_ALL}"
                    
                    print(status_msg)
                    finished_processes.append(filename)
            
            # Remove finished processes
            for filename in finished_processes:
                if filename in self.processes:
                    del self.processes[filename]
            
            time.sleep(1)  # Check every second
    
    def run_files(self, file_patterns, max_files=None):
        """Run multiple files matching the patterns"""
        # Collect all matching files
        all_files = []
        for pattern in file_patterns:
            if os.path.isfile(pattern):
                all_files.append(pattern)
            else:
                matched_files = glob.glob(pattern)
                all_files.extend([f for f in matched_files if f.endswith('.py')])
        
        # Remove duplicates and sort
        all_files = sorted(list(set(all_files)))
        
        if not all_files:
            print(f"{Fore.RED}[RUNNER] No Python files found matching patterns: {file_patterns}{Style.RESET_ALL}")
            return
        
        # Limit number of files if specified
        if max_files:
            all_files = all_files[:max_files]
        
        print(f"{Fore.GREEN}[RUNNER] Found {len(all_files)} Python files to run:{Style.RESET_ALL}")
        for f in all_files:
            print(f"  → {f}")
        
        # Assign colors to files
        self.assign_colors([os.path.basename(f) for f in all_files])
        
        print(f"\n{Fore.YELLOW}[RUNNER] Starting all processes...{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}{'='*60}{Style.RESET_ALL}\n")
        
        # Start all processes
        started_count = 0
        for filepath in all_files:
            if self.start_process(filepath):
                started_count += 1
                time.sleep(0.5)  # Small delay between starts
        
        if started_count == 0:
            print(f"{Fore.RED}[RUNNER] No processes started successfully{Style.RESET_ALL}")
            return
        
        print(f"\n{Fore.GREEN}[RUNNER] Started {started_count} processes. Real-time output:{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}{'='*60}{Style.RESET_ALL}\n")
        
        # Start monitoring in a separate thread
        monitor_thread = threading.Thread(target=self.monitor_processes, daemon=True)
        monitor_thread.start()
        
        # Main loop - just wait and handle keyboard interrupt
        try:
            while self.running and self.processes:
                time.sleep(1)
        except KeyboardInterrupt:
            print(f"\n{Fore.YELLOW}[RUNNER] Keyboard interrupt received. Stopping all processes...{Style.RESET_ALL}")
            self.stop_all()
    
    def stop_all(self):
        """Stop all running processes"""
        self.running = False
        
        for filename, process in self.processes.items():
            try:
                if process.poll() is None:  # Process is still running
                    color = self.file_colors.get(filename, Fore.WHITE)
                    print(f"{color}[RUNNER] Terminating {filename}...{Style.RESET_ALL}")
                    process.terminate()
                    
                    # Wait a bit for graceful termination
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        print(f"{Fore.RED}[RUNNER] Force killing {filename}...{Style.RESET_ALL}")
                        process.kill()
                        
            except Exception as e:
                print(f"{Fore.RED}[RUNNER] Error stopping {filename}: {e}{Style.RESET_ALL}")
        
        print(f"\n{Fore.GREEN}[RUNNER] All processes stopped.{Style.RESET_ALL}")

def main():
    """Main function"""
    if len(sys.argv) < 2:
        print(f"{Fore.YELLOW}Usage: python multi_runner_realtime.py <file_pattern1> [file_pattern2] ... [--max N]{Style.RESET_ALL}")
        print(f"\nExamples:")
        print(f"  python multi_runner_realtime.py '[1-4].py'")
        print(f"  python multi_runner_realtime.py '*.py' --max 4")
        print(f"  python multi_runner_realtime.py 1.py 2.py 3.py 4.py")
        print(f"  python multi_runner_realtime.py 'bot_*.py' 'scanner_*.py'")
        return
    
    # Parse arguments
    file_patterns = []
    max_files = None
    
    i = 1
    while i < len(sys.argv):
        if sys.argv[i] == '--max' and i + 1 < len(sys.argv):
            max_files = int(sys.argv[i + 1])
            i += 2
        else:
            file_patterns.append(sys.argv[i])
            i += 1
    
    if not file_patterns:
        print(f"{Fore.RED}[RUNNER] No file patterns provided{Style.RESET_ALL}")
        return
    
    # Create and run the multi-runner
    runner = RealTimeMultiRunner()
    
    try:
        runner.run_files(file_patterns, max_files)
    except Exception as e:
        print(f"{Fore.RED}[RUNNER] Unexpected error: {e}{Style.RESET_ALL}")
    finally:
        runner.stop_all()

if __name__ == "__main__":
    main()
