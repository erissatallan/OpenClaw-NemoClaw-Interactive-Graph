#!/bin/bash
# Deployment script for ClawGraph to root@77.68.100.188

SERVER="root@77.68.100.188"
REMOTE_DIR="/root/ClawGraph"

echo "🚀 Preparing deployment for ClawGraph..."

# 1. Create remote directory
ssh $SERVER "mkdir -p $REMOTE_DIR"

# 2. Sync files (excluding unnecessary ones)
echo "📦 Syncing files via rsync..."
rsync -avz --exclude '.git' --exclude '.pytest_cache' --exclude '__pycache__' \
      --exclude '.venv' --exclude 'logs' --exclude 'neo4j_data' \
      ./ $SERVER:$REMOTE_DIR/

# 3. Create .env on server if it doesn't exist (copying local one as base)
echo "🔑 Setting up environment variables..."
scp .env $SERVER:$REMOTE_DIR/.env

# 4. Build and start containers
echo "🏗️ Building and starting containers on the server..."
ssh $SERVER "cd $REMOTE_DIR && docker compose build && docker compose up -d"

# 5. Check health
echo "🩺 Verifying deployment..."
sleep 5
ssh $SERVER "curl -s http://localhost:8000/api/health"

echo "✅ Deployment complete!"
