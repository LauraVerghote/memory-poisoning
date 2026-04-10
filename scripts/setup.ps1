# Memory Poisoning Workshop — Environment Setup

Write-Host "Setting up Memory Poisoning Workshop..." -ForegroundColor Cyan

# Create virtual environment
if (-not (Test-Path ".venv")) {
    Write-Host "Creating Python virtual environment..." -ForegroundColor Yellow
    python -m venv .venv
}

# Activate
Write-Host "Activating virtual environment..." -ForegroundColor Yellow
& .venv\Scripts\Activate.ps1

# Install dependencies
Write-Host "Installing dependencies..." -ForegroundColor Yellow
pip install -r requirements.txt

# Create memory_data directory
if (-not (Test-Path "memory_data")) {
    New-Item -ItemType Directory -Path "memory_data" | Out-Null
}

# Check for .env file
if (-not (Test-Path ".env")) {
    Write-Host "`nWARNING: No .env file found!" -ForegroundColor Red
    Write-Host "Create a .env file with your OpenAI API key:" -ForegroundColor Yellow
    Write-Host "  OPENAI_API_KEY=sk-your-key-here" -ForegroundColor White
} else {
    Write-Host ".env file found." -ForegroundColor Green
}

Write-Host "`nSetup complete! Start with Lab 1:" -ForegroundColor Green
Write-Host "  python scripts/run_unsafe_agent.py" -ForegroundColor White
