#!/usr/bin/env python3
"""
Multi-File Dynamic Runner Script
Runs multiple Python files concurrently with high performance
Supports dynamic import and execution with monitoring
"""

import os
import sys
import time
import glob
import threading
import multiprocessing
import importlib.util
import subprocess
import logging
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, as_completed
from pathlib import Path
import psutil
import signal
import json
from typing import List, Dict, Optional, Tuple
import traceback

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("multi_runner.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class MultiRunner:
    """High-performance multi-file runner with monitoring and management"""
    
    def __init__(self, base_directory: str = ".", max_workers: int = None):
        self.base_directory = Path(base_directory).resolve()
        self.max_workers = max_workers or min(32, (os.cpu_count() or 1) + 4)
        self.running_processes = {}
        self.process_stats = {}
        self.start_time = time.time()
        self.shutdown_event = threading.Event()
        
        # Performance monitoring
        self.monitor_thread = None
        self.stats_file = "runner_stats.json"
        
        logger.info(f"[INIT] MultiRunner initialized with {self.max_workers} max workers")
        logger.info(f"[INIT] Base directory: {self.base_directory}")
        
    def discover_python_files(self, pattern: str = "*.py") -> List[Path]:
        """Discover Python files matching pattern"""
        files = []
        
        # Support multiple patterns
        patterns = pattern.split(',') if ',' in pattern else [pattern]
        
        for pat in patterns:
            pat = pat.strip()
            if os.path.sep in pat:
                # Handle paths with directories
                files.extend(self.base_directory.glob(pat))
            else:
                # Handle simple patterns
                files.extend(self.base_directory.glob(pat))
        
        # Filter out __pycache__ and this script itself
        valid_files = []
        for file in files:
            if file.is_file() and file.suffix == '.py':
                if '__pycache__' not in str(file) and file.name != 'multi_runner.py':
                    valid_files.append(file)
        
        logger.info(f"[DISCOVERY] Found {len(valid_files)} Python files")
        for file in valid_files:
            logger.info(f"  - {file.name}")
            
        return valid_files
    
    def validate_python_file(self, file_path: Path) -> bool:
        """Validate if Python file can be executed"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # Basic validation
            if len(content.strip()) == 0:
                logger.warning(f"[VALIDATION] Empty file: {file_path.name}")
                return False
                
            # Check for main function or main guard
            if 'def main(' in content or 'if __name__ == "__main__"' in content:
                return True
                
            # Check for executable code (not just imports)
            lines = content.split('\n')
            executable_lines = [line for line in lines if line.strip() and not line.strip().startswith('#') and not line.strip().startswith('import') and not line.strip().startswith('from')]
            
            return len(executable_lines) > 0
            
        except Exception as e:
            logger.error(f"[VALIDATION] Error validating {file_path.name}: {e}")
            return False
    
    def run_file_as_process(self, file_path: Path) -> Dict:
        """Run a Python file as a separate process"""
        process_info = {
            'file': file_path.name,
            'start_time': time.time(),
            'status': 'starting',
            'pid': None,
            'memory_usage': 0,
            'cpu_usage': 0,
            'output': [],
            'error': None
        }
        
        try:
            logger.info(f"[PROCESS] Starting {file_path.name}")
            
            # Start process
            process = subprocess.Popen(
                [sys.executable, str(file_path)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=str(file_path.parent),
                env=os.environ.copy()
            )
            
            process_info['pid'] = process.pid
            process_info['status'] = 'running'
            self.running_processes[file_path.name] = process
            
            # Monitor process
            try:
                stdout, stderr = process.communicate(timeout=None)  # No timeout for long-running processes
                
                process_info['status'] = 'completed'
                process_info['return_code'] = process.returncode
                process_info['output'] = stdout.split('\n') if stdout else []
                process_info['error'] = stderr if stderr else None
                
                if process.returncode == 0:
                    logger.info(f"[SUCCESS] {file_path.name} completed successfully")
                else:
                    logger.warning(f"[WARNING] {file_path.name} exited with code {process.returncode}")
                    
            except subprocess.TimeoutExpired:
                logger.info(f"[TIMEOUT] {file_path.name} is long-running, continuing in background")
                process_info['status'] = 'background'
                
        except Exception as e:
            process_info['status'] = 'error'
            process_info['error'] = str(e)
            logger.error(f"[ERROR] Failed to run {file_path.name}: {e}")
            
        finally:
            process_info['end_time'] = time.time()
            process_info['duration'] = process_info['end_time'] - process_info['start_time']
            
        return process_info
    
    def run_file_as_module(self, file_path: Path) -> Dict:
        """Run a Python file as an imported module"""
        module_info = {
            'file': file_path.name,
            'start_time': time.time(),
            'status': 'starting',
            'error': None
        }
        
        try:
            logger.info(f"[MODULE] Importing {file_path.name}")
            
            # Create module spec
            spec = importlib.util.spec_from_file_location(
                file_path.stem, 
                str(file_path)
            )
            
            if spec is None:
                raise ImportError(f"Could not load spec for {file_path.name}")
                
            # Import module
            module = importlib.util.module_from_spec(spec)
            sys.modules[file_path.stem] = module
            
            # Execute module
            spec.loader.exec_module(module)
            
            # Try to call main function if it exists
            if hasattr(module, 'main'):
                logger.info(f"[MODULE] Calling main() for {file_path.name}")
                module.main()
            
            module_info['status'] = 'completed'
            logger.info(f"[SUCCESS] {file_path.name} module executed successfully")
            
        except Exception as e:
            module_info['status'] = 'error'
            module_info['error'] = str(e)
            logger.error(f"[ERROR] Failed to run module {file_path.name}: {e}")
            logger.error(f"[ERROR] Traceback: {traceback.format_exc()}")
            
        finally:
            module_info['end_time'] = time.time()
            module_info['duration'] = module_info['end_time'] - module_info['start_time']
            
        return module_info
    
    def run_file_as_subprocess(self, file_path: Path) -> Dict:
        """Run a Python file as an independent subprocess"""
        subprocess_info = {
            'file': file_path.name,
            'start_time': time.time(),
            'status': 'starting',
            'pid': None,
            'output': [],
            'error': None
        }
        
        try:
            logger.info(f"[SUBPROCESS] Starting {file_path.name}")
            
            # Start subprocess
            process = subprocess.Popen(
                [sys.executable, str(file_path)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=str(file_path.parent),
                env=os.environ.copy(),
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0
            )
            
            subprocess_info['pid'] = process.pid
            subprocess_info['status'] = 'running'
            
            # For long-running processes, don't wait - let them run in background
            # Check if process is still running after a short time
            time.sleep(1)
            if process.poll() is None:
                # Process is still running - it's likely a long-running script
                subprocess_info['status'] = 'background'
                logger.info(f"[BACKGROUND] {file_path.name} is running in background (PID: {process.pid})")
                return subprocess_info
            
            # Process finished quickly - get the output
            stdout, stderr = process.communicate(timeout=30)
            
            subprocess_info['status'] = 'completed'
            subprocess_info['return_code'] = process.returncode
            subprocess_info['output'] = stdout.split('\n') if stdout else []
            subprocess_info['error'] = stderr if stderr else None
            
            if process.returncode == 0:
                logger.info(f"[SUCCESS] {file_path.name} completed successfully")
            else:
                logger.warning(f"[WARNING] {file_path.name} exited with code {process.returncode}")
                if stderr:
                    logger.error(f"[STDERR] {stderr}")
                    
        except subprocess.TimeoutExpired:
            subprocess_info['status'] = 'background'
            logger.info(f"[BACKGROUND] {file_path.name} is taking longer - running in background")
            
        except Exception as e:
            subprocess_info['status'] = 'error'
            subprocess_info['error'] = str(e)
            logger.error(f"[ERROR] Failed to run subprocess {file_path.name}: {e}")
            
        finally:
            subprocess_info['end_time'] = time.time()
            subprocess_info['duration'] = subprocess_info['end_time'] - subprocess_info['start_time']
            
        return subprocess_info

    def monitor_processes(self):
        """Monitor running processes and collect stats"""
        while not self.shutdown_event.is_set():
            try:
                for file_name, process in list(self.running_processes.items()):
                    if process.poll() is not None:
                        # Process has finished
                        del self.running_processes[file_name]
                        continue
                        
                    # Get process stats
                    try:
                        p = psutil.Process(process.pid)
                        self.process_stats[file_name] = {
                            'cpu_percent': p.cpu_percent(),
                            'memory_mb': p.memory_info().rss / 1024 / 1024,
                            'status': p.status(),
                            'create_time': p.create_time()
                        }
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass
                        
                # Save stats periodically
                self.save_stats()
                
                time.sleep(5)  # Monitor every 5 seconds
                
            except Exception as e:
                logger.error(f"[MONITOR] Error in monitor thread: {e}")
                time.sleep(10)
    
    def save_stats(self):
        """Save runtime statistics to file"""
        try:
            stats = {
                'start_time': self.start_time,
                'current_time': time.time(),
                'uptime': time.time() - self.start_time,
                'running_processes': len(self.running_processes),
                'process_stats': self.process_stats,
                'system_stats': {
                    'cpu_percent': psutil.cpu_percent(),
                    'memory_percent': psutil.virtual_memory().percent,
                    'disk_usage': psutil.disk_usage('.').percent
                }
            }
            
            with open(self.stats_file, 'w') as f:
                json.dump(stats, f, indent=2)
                
        except Exception as e:
            logger.error(f"[STATS] Error saving stats: {e}")
    
    def run_files_concurrent(self, files: List[Path], execution_mode: str = "process") -> List[Dict]:
        """Run multiple files concurrently"""
        results = []
        
        # Start monitoring thread
        self.monitor_thread = threading.Thread(target=self.monitor_processes, daemon=True)
        self.monitor_thread.start()
        
        logger.info(f"[CONCURRENT] Starting {len(files)} files in {execution_mode} mode")
        
        if execution_mode == "process":
            # Use ProcessPoolExecutor for true parallelism
            with ProcessPoolExecutor(max_workers=self.max_workers) as executor:
                future_to_file = {
                    executor.submit(self.run_file_as_process, file): file 
                    for file in files
                }
                
                for future in as_completed(future_to_file):
                    file = future_to_file[future]                    try:
                        result = future.result()
                        results.append(result)
                        logger.info(f"[COMPLETE] {file.name} finished")
                    except Exception as e:
                        logger.error(f"[ERROR] {file.name} failed: {e}")
                        results.append({
                            'file': file.name,
                            'status': 'error',
                            'error': str(e)
                        })
        
        elif execution_mode == "thread":
            # Use ThreadPoolExecutor for I/O bound tasks
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                future_to_file = {
                    executor.submit(self.run_file_as_module, file): file 
                    for file in files
                }
                
                for future in as_completed(future_to_file):
                    file = future_to_file[future]
                    try:
                        result = future.result()
                        results.append(result)
                        logger.info(f"[COMPLETE] {file.name} finished")
                    except Exception as e:
                        logger.error(f"[ERROR] {file.name} failed: {e}")
                        results.append({
                            'file': file.name,
                            'status': 'error',
                            'error': str(e)
                        })
        
        elif execution_mode == "subprocess":
            # Use subprocess for independent process execution
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                future_to_file = {
                    executor.submit(self.run_file_as_subprocess, file): file 
                    for file in files
                }
                
                for future in as_completed(future_to_file):
                    file = future_to_file[future]
                    try:
                        result = future.result()
                        results.append(result)
                        logger.info(f"[COMPLETE] {file.name} finished")
                    except Exception as e:
                        logger.error(f"[ERROR] {file.name} failed: {e}")
                        results.append({
                            'file': file.name,
                            'status': 'error',
                            'error': str(e)
                        })
        
        else:  # sequential
            for file in files:
                if execution_mode == "module":
                    result = self.run_file_as_module(file)
                else:
                    result = self.run_file_as_process(file)
                results.append(result)
        
        return results
    
    def print_summary(self, results: List[Dict]):
        """Print execution summary"""
        successful = len([r for r in results if r['status'] == 'completed'])
        failed = len([r for r in results if r['status'] == 'error'])
        background = len([r for r in results if r['status'] == 'background'])
        
        print("\n" + "="*60)
        print("EXECUTION SUMMARY")
        print("="*60)
        print(f"Total files: {len(results)}")
        print(f"Successfully completed: {successful}")
        print(f"Failed: {failed}")
        print(f"Running in background: {background}")
        print(f"Total runtime: {time.time() - self.start_time:.2f} seconds")
        
        if failed > 0:
            print(f"\nFAILED FILES:")
            for result in results:
                if result['status'] == 'error':
                    print(f"  - {result['file']}: {result['error']}")
        
        if background > 0:
            print(f"\nBACKGROUND PROCESSES:")
            for result in results:
                if result['status'] == 'background':
                    print(f"  - {result['file']} (PID: {result.get('pid', 'N/A')})")
        
        print("="*60)
    
    def cleanup(self):
        """Clean up resources and terminate processes"""
        logger.info("[CLEANUP] Stopping all processes...")
        
        # Stop monitoring
        self.shutdown_event.set()
        
        # Terminate running processes
        for file_name, process in self.running_processes.items():
            try:
                if process.poll() is None:  # Still running
                    logger.info(f"[CLEANUP] Terminating {file_name}")
                    process.terminate()
                    time.sleep(2)
                    if process.poll() is None:  # Still running after terminate
                        process.kill()
            except Exception as e:
                logger.error(f"[CLEANUP] Error terminating {file_name}: {e}")
        
        # Save final stats
        self.save_stats()
        
        logger.info("[CLEANUP] Cleanup completed")


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Multi-File Dynamic Runner')
    parser.add_argument('--directory', '-d', default='.', help='Base directory to search for files')
    parser.add_argument('--pattern', '-p', default='*.py', help='File pattern to match (comma-separated)')
    parser.add_argument('--workers', '-w', type=int, help='Max number of workers')
    parser.add_argument('--mode', '-m', choices=['process', 'thread', 'module', 'sequential', 'subprocess'], 
                       default='subprocess', help='Execution mode')
    parser.add_argument('--validate', '-v', action='store_true', help='Validate files before running')
    parser.add_argument('--files', '-f', nargs='+', help='Specific files to run')
    
    args = parser.parse_args()
    
    # Create runner
    runner = MultiRunner(args.directory, args.workers)
    
    try:
        if args.files:
            # Run specific files
            files = [Path(f) for f in args.files if Path(f).exists()]
            logger.info(f"[MAIN] Running specific files: {[f.name for f in files]}")
        else:
            # Discover files
            files = runner.discover_python_files(args.pattern)
        
        if not files:
            logger.error("[MAIN] No files found to run")
            return
        
        # Validate files if requested
        if args.validate:
            logger.info("[MAIN] Validating files...")
            valid_files = [f for f in files if runner.validate_python_file(f)]
            logger.info(f"[MAIN] {len(valid_files)} of {len(files)} files are valid")
            files = valid_files
        
        if not files:
            logger.error("[MAIN] No valid files to run")
            return
        
        # Run files
        logger.info(f"[MAIN] Starting execution of {len(files)} files in {args.mode} mode")
        results = runner.run_files_concurrent(files, args.mode)
        
        # Print summary
        runner.print_summary(results)
        
    except KeyboardInterrupt:
        logger.info("[MAIN] Interrupted by user")
    except Exception as e:
        logger.error(f"[MAIN] Fatal error: {e}")
        logger.error(f"[MAIN] Traceback: {traceback.format_exc()}")
    finally:
        runner.cleanup()


if __name__ == "__main__":
    main()
