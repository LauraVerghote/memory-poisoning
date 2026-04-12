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

# Check for .env file
if (-not (Test-Path ".env")) {
    Write-Host "`nWARNING: No .env file found!" -ForegroundColor Red
    Write-Host "Copy .env.template to .env and fill in your Foundry project details:" -ForegroundColor Yellow
    Write-Host "  cp .env.template .env" -ForegroundColor White
    Write-Host "Required variables:" -ForegroundColor Yellow
    Write-Host "  FOUNDRY_PROJECT_ENDPOINT=https://<account>.services.ai.azure.com/api/projects/<project>" -ForegroundColor White
    Write-Host "  FOUNDRY_MODEL_DEPLOYMENT_NAME=gpt-4o" -ForegroundColor White
} else {
    Write-Host ".env file found." -ForegroundColor Green
}

# Azure login check
Write-Host "`nChecking Azure CLI login..." -ForegroundColor Yellow
$azAccount = az account show 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "WARNING: Not logged into Azure CLI. Run 'az login' first." -ForegroundColor Red
} else {
    Write-Host "Azure CLI authenticated." -ForegroundColor Green
}

Write-Host "`nNext steps:" -ForegroundColor Green
Write-Host "  1. Ensure .env is configured" -ForegroundColor White
Write-Host "  2. Run: python scripts/setup_memory_stores.py" -ForegroundColor White
Write-Host "  3. Start with: python scripts/run_unsafe_agent.py" -ForegroundColor White
