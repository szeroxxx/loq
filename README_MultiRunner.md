# Multi-File Dynamic Runner

A high-performance Python script that can dynamically import and run multiple Python files concurrently. Perfect for running multiple wallet scanners, bots, or any Python scripts simultaneously.

## Features

- 🚀 **High Performance**: Concurrent execution using multiprocessing/threading
- 📊 **Real-time Monitoring**: Process monitoring with CPU/memory usage tracking
- 🔧 **Flexible Execution**: Multiple execution modes (process, thread, module, sequential)
- 📝 **Comprehensive Logging**: Detailed logging with file rotation
- 🎯 **Smart Discovery**: Automatic file discovery with pattern matching
- ✅ **Validation**: Pre-execution file validation
- 📈 **Statistics**: Runtime statistics and performance metrics
- 🛡️ **Error Handling**: Robust error handling and recovery

## Quick Start

### Method 1: Using Batch File (Easiest)
```cmd
# Run all .py files in current directory
run_multiple.bat

# Run specific files
run_multiple.bat "1.py,2.py,3.py,4.py"

# Run with different mode
run_multiple.bat "*.py" thread
```

### Method 2: Using PowerShell Script
```powershell
# Run all .py files
./run_multiple.ps1

# Run with specific pattern and validation
./run_multiple.ps1 -Pattern "*.py" -Mode "process" -Validate

# Run specific files
./run_multiple.ps1 -Files @("1.py", "2.py", "3.py", "4.py")
```

### Method 3: Direct Python Execution
```bash
# Basic usage - run all .py files
python multi_runner.py

# Run specific pattern
python multi_runner.py --pattern "1.py,2.py,3.py,4.py"

# Run with validation and custom workers
python multi_runner.py --pattern "*.py" --validate --workers 8

# Run in thread mode
python multi_runner.py --mode thread --pattern "*.py"
```

## Command Line Options

```
--directory, -d    Base directory to search for files (default: current directory)
--pattern, -p      File pattern to match, comma-separated (default: *.py)
--workers, -w      Maximum number of concurrent workers
--mode, -m         Execution mode: process|thread|module|sequential (default: process)
--validate, -v     Validate files before running
--files, -f        Specific files to run (space-separated)
```

## Execution Modes

### 1. Process Mode (Default - Recommended)
- Runs each file as a separate Python process
- True parallelism with isolated memory spaces
- Best for CPU-intensive tasks
- Fault isolation - one crash won't affect others

### 2. Thread Mode
- Runs files in separate threads within the same process
- Good for I/O-bound tasks
- Shared memory space
- Lower resource overhead

### 3. Module Mode
- Imports and executes files as Python modules
- Fastest startup time
- Shared global state
- Good for lightweight scripts

### 4. Sequential Mode
- Runs files one after another
- No concurrency
- Useful for debugging

## Configuration

Edit `runner_config.json` to customize default settings:

```json
{
  "runner_config": {
    "max_workers": null,
    "execution_mode": "process",
    "validate_files": true,
    "monitor_interval": 5
  },
  "file_patterns": [
    "*.py",
    "[0-9].py",
    "[0-9][0-9].py"
  ],
  "excluded_files": [
    "multi_runner.py",
    "__pycache__",
    "*.pyc"
  ]
}
```

## Examples for Your Use Case

### Running Wallet Scanners (1.py, 2.py, 3.py, 4.py)
```bash
# Run all numbered scanner files
python multi_runner.py --pattern "[0-9].py" --validate

# Run with maximum performance
python multi_runner.py --pattern "1.py,2.py,3.py,4.py" --mode process --workers 4

# Monitor performance while running
python multi_runner.py --pattern "*.py" --validate
# Check runner_stats.json for real-time statistics
```

### Running Large Numbers of Files
```bash
# Run all files matching pattern
python multi_runner.py --pattern "scanner_*.py" --workers 16

# Run with automatic validation
python multi_runner.py --pattern "bot_[0-9][0-9].py" --validate --mode process
```

## Monitoring and Statistics

The runner automatically creates:
- `multi_runner.log` - Detailed execution logs
- `runner_stats.json` - Real-time performance statistics
- Individual log files for each executed script

### Real-time Monitoring
```bash
# View live statistics
tail -f multi_runner.log

# Check runner statistics
cat runner_stats.json
```

## Performance Tips

1. **Use Process Mode** for CPU-intensive tasks (like wallet scanning)
2. **Adjust Workers** based on your CPU cores (`--workers 8` for 8-core system)
3. **Enable Validation** to catch issues early (`--validate`)
4. **Monitor Resources** using the generated statistics
5. **Use Specific Patterns** to avoid running unnecessary files

## Troubleshooting

### Common Issues

1. **"No files found"**
   - Check your file pattern: `--pattern "*.py"`
   - Verify directory: `--directory "path/to/files"`

2. **"Process failed to start"**
   - Enable validation: `--validate`
   - Check file permissions
   - Verify Python syntax in target files

3. **High memory usage**
   - Reduce workers: `--workers 4`
   - Use thread mode: `--mode thread`

4. **Files not executing properly**
   - Ensure files have `if __name__ == "__main__":` guard
   - Or define a `main()` function

### Logs and Debugging
- Check `multi_runner.log` for detailed execution information
- Individual script outputs are captured and logged
- Use `--mode sequential` for step-by-step debugging

## Safety Features

- Automatic process cleanup on exit
- Memory and CPU monitoring
- Graceful shutdown handling
- Error isolation between processes
- Comprehensive logging for troubleshooting

## Requirements

- Python 3.6+
- Required packages: `psutil` (installed automatically)
- Windows/Linux/macOS compatible

## Installation

```bash
# Clone or download the files
# No installation required - just run!

# Optional: Install psutil for enhanced monitoring
pip install psutil
```

---

**Perfect for running multiple wallet scanners, trading bots, or any Python automation scripts concurrently!**
