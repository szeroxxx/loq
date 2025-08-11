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
        """Discover Python files matching the pattern"""
        files = []
        
        # Handle multiple patterns separated by comma
        patterns = [p.strip() for p in pattern.split(',')]
        
        for pat in patterns:
            if pat.startswith('[') and pat.endswith('].py'):
                # Handle range patterns like [1-4].py
                range_part = pat[1:-4]  # Remove [ and ].py
                if '-' in range_part:
                    start, end = range_part.split('-')
                    try:
                        start_num = int(start)
                        end_num = int(end)
                        for i in range(start_num, end_num + 1):
                            file_path = self.base_directory / f"{i}.py"
                            if file_path.exists():
                                files.append(file_path)
                    except ValueError:
                        logger.warning(f"[WARNING] Invalid range pattern: {pat}")
                continue
            
            # Standard glob pattern
            if '/' in pat or '\\' in pat:
                # Absolute or relative path
                file_paths = glob.glob(pat)
            else:
                # Pattern in base directory
                file_paths = glob.glob(str(self.base_directory / pat))
            
            for file_path in file_paths:
                path_obj = Path(file_path)
                if path_obj.is_file() and path_obj.suffix == '.py':
                    files.append(path_obj)
        
        # Remove duplicates while preserving order
        seen = set()
        unique_files = []
        for file in files:
            if file not in seen:
                seen.add(file)
                unique_files.append(file)
        
        logger.info(f"[DISCOVERY] Found {len(unique_files)} Python files")
        for file in unique_files:
            logger.info(f"  - {file.name}")
            
        return unique_files
    
    def validate_python_file(self, file_path: Path) -> bool:
        """Validate if a Python file can be executed"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Check if file has executable content
            lines = content.split('\n')
            executable_lines = [line for line in lines if line.strip() and not line.strip().startswith('#') and not line.strip().startswith('import') and not line.strip().startswith('from')]
            
            return len(executable_lines) > 0
            
        except Exception as e:
            logger.error(f"[VALIDATION] Error validating {file_path.name}: {e}")
            return False
    
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
            time.sleep(2)
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
    
    def run_file_as_process(self, file_path: Path) -> Dict:
        """Run a Python file as a separate process using multiprocessing"""
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
            
            # Import and execute the file
            spec = importlib.util.spec_from_file_location("__main__", file_path)
            if spec is None or spec.loader is None:
                raise ImportError(f"Cannot load spec from {file_path}")
            
            module = importlib.util.module_from_spec(spec)
            
            process_info['status'] = 'running'
            spec.loader.exec_module(module)
            process_info['status'] = 'completed'
            logger.info(f"[SUCCESS] {file_path.name} completed successfully")
            
        except Exception as e:
            process_info['status'] = 'error'
            process_info['error'] = str(e)
            logger.error(f"[ERROR] Failed to run process {file_path.name}: {e}")
            
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
            logger.info(f"[MODULE] Starting {file_path.name}")
            
            # Import and execute the file
            spec = importlib.util.spec_from_file_location("dynamic_module", file_path)
            if spec is None or spec.loader is None:
                raise ImportError(f"Cannot load spec from {file_path}")
            
            module = importlib.util.module_from_spec(spec)
            
            module_info['status'] = 'running'
            spec.loader.exec_module(module)
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
    
    def run_files_concurrent(self, files: List[Path], execution_mode: str = "subprocess") -> List[Dict]:
        """Run multiple files concurrently"""
        results = []
        
        logger.info(f"[CONCURRENT] Starting {len(files)} files in {execution_mode} mode")
        
        if execution_mode == "subprocess":
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
        
        elif execution_mode == "process":
            # Use ProcessPoolExecutor for true parallelism
            with ProcessPoolExecutor(max_workers=self.max_workers) as executor:
                future_to_file = {
                    executor.submit(self.run_file_as_process, file): file 
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
        
        else:  # sequential
            for file in files:
                if execution_mode == "module":
                    result = self.run_file_as_module(file)
                else:
                    result = self.run_file_as_subprocess(file)
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
                    print(f"  - {result['file']}: {result.get('error', 'Unknown error')}")
        
        if background > 0:
            print(f"\nBACKGROUND PROCESSES:")
            for result in results:
                if result['status'] == 'background':
                    pid = result.get('pid', 'Unknown')
                    print(f"  - {result['file']} (PID: {pid})")
        
        print("="*60)

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
            if len(valid_files) != len(files):
                logger.warning(f"[MAIN] {len(files) - len(valid_files)} files failed validation")
            files = valid_files
        
        if not files:
            logger.error("[MAIN] No valid files to run")
            return
        
        logger.info(f"[MAIN] Starting execution of {len(files)} files in {args.mode} mode")
        
        # Run files
        results = runner.run_files_concurrent(files, args.mode)
        
        # Print summary
        runner.print_summary(results)
        
    except KeyboardInterrupt:
        logger.info("[MAIN] Execution interrupted by user")
    except Exception as e:
        logger.error(f"[MAIN] Fatal error: {e}")
        logger.error(f"[MAIN] Traceback: {traceback.format_exc()}")

if __name__ == "__main__":
    main()
