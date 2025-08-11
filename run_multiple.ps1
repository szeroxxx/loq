# Multi-Runner PowerShell Script
# Easy execution script for the multi-file runner

param(
    [string]$Pattern = "*.py",
    [string]$Mode = "process",
    [int]$Workers = 0,
    [switch]$Validate,
    [string]$Directory = ".",
    [string[]]$Files = @()
)

Write-Host "Multi-File Dynamic Runner" -ForegroundColor Green
Write-Host "=========================" -ForegroundColor Green

# Check if Python is available
try {
    $pythonVersion = python --version 2>&1
    Write-Host "Python version: $pythonVersion" -ForegroundColor Cyan
} catch {
    Write-Host "ERROR: Python not found. Please install Python first." -ForegroundColor Red
    exit 1
}

# Check if multi_runner.py exists
if (-not (Test-Path "multi_runner.py")) {
    Write-Host "ERROR: multi_runner.py not found in current directory." -ForegroundColor Red
    exit 1
}

# Build command arguments
$args = @("multi_runner.py")
$args += "--directory", $Directory
$args += "--pattern", $Pattern
$args += "--mode", $Mode

if ($Workers -gt 0) {
    $args += "--workers", $Workers
}

if ($Validate) {
    $args += "--validate"
}

if ($Files.Count -gt 0) {
    $args += "--files"
    $args += $Files
}

Write-Host "Executing: python $($args -join ' ')" -ForegroundColor Yellow
Write-Host ""

# Execute the runner
try {
    & python @args
} catch {
    Write-Host "ERROR: Failed to execute multi_runner.py" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "Execution completed!" -ForegroundColor Green
