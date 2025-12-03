# Docker Setup Guide

## Prerequisites

1. **Docker Desktop** must be installed and running
   - Download from: https://www.docker.com/products/docker-desktop
   - Make sure Docker Desktop is fully started before running any commands

## Quick Start

### Step 1: Start Docker Desktop
- Open Docker Desktop from Windows Start Menu
- Wait until the Docker icon appears in the system tray (bottom right)
- The icon should be steady (not animating) when ready

### Step 2: Run Setup Script
```powershell
.\setup-docker.ps1
```

This script will:
- Verify Docker Desktop is running
- Create the required `backend_net` network if it doesn't exist

### Step 3: Start Services

Start services in order:

1. **Start MongoDB:**
   ```powershell
   docker-compose -f docker-compose-db.yaml up -d
   ```

2. **Start RabbitMQ (optional):**
   ```powershell
   docker-compose -f docker-compose-rabbitmq.yaml up -d
   ```

3. **Build and Start Backend:**
   ```powershell
   docker-compose up --build
   ```

## Troubleshooting

### Error: "The system cannot find the file specified"
**Solution:** Docker Desktop is not running. Start Docker Desktop and wait for it to fully initialize.

### Error: "network backend_net not found"
**Solution:** Run the setup script: `.\setup-docker.ps1`

### Error: "unable to get image"
**Solution:** Use `--build` flag to build the image:
```powershell
docker-compose up --build
```

## Manual Network Creation

If the setup script doesn't work, create the network manually:
```powershell
docker network create backend_net
```

## Stopping Services

To stop all services:
```powershell
docker-compose down
docker-compose -f docker-compose-db.yaml down
docker-compose -f docker-compose-rabbitmq.yaml down
```

