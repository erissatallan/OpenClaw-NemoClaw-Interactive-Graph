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

# 3. Copy .env to server
echo "🔑 Setting up environment variables..."
scp .env $SERVER:$REMOTE_DIR/.env

# 4. Build and start containers
echo "🏗️ Building and starting containers on the server..."
ssh $SERVER "cd $REMOTE_DIR && docker compose build && docker compose up -d"

# 5. Install ClawGraph skill into OpenClaw workspace + agent identity
echo "🧠 Installing ClawGraph skill into OpenClaw..."
ssh $SERVER "
  mkdir -p /root/.openclaw/workspace/ClawGraph/scripts
  cp $REMOTE_DIR/openclaw_skill/SKILL.md /root/.openclaw/workspace/ClawGraph/SKILL.md
  cp $REMOTE_DIR/openclaw_skill/scripts/kg.sh /root/.openclaw/workspace/ClawGraph/scripts/kg.sh
  chmod +x /root/.openclaw/workspace/ClawGraph/scripts/kg.sh

  # Install agent identity so the bot knows about ClawGraph with absolute paths
  mkdir -p /root/.openclaw/agents/main/agent
  cp $REMOTE_DIR/openclaw_skill/agent.md /root/.openclaw/agents/main/agent/agent.md

  echo '✅ Skill files installed.'
"

# 6. Restart OpenClaw to pick up the new agent.md
echo "🔄 Restarting OpenClaw..."
ssh $SERVER "pm2 restart all 2>/dev/null || systemctl restart openclaw 2>/dev/null || echo 'ℹ️  Please restart OpenClaw manually (pm2 restart all).'"

# 7. Check health
echo "🩺 Verifying deployment..."
sleep 5
ssh $SERVER "curl -s http://localhost:8000/api/health"
ssh $SERVER "bash /root/.openclaw/workspace/ClawGraph/scripts/kg.sh health"

echo "✅ Deployment complete!"
