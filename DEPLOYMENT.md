# Oracle Cloud Deployment

## Setup Steps

1. **Install dependencies**
```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
```

2. **Configure environment**
```bash
   cp .env.example .env
   # Edit .env with your actual values
   nano .env
```

3. **Create systemd service**
```bash
   sudo nano /etc/systemd/system/dominion-api.service
```
   
   Use the service file content from the README.

4. **Enable and start**
```bash
   sudo systemctl daemon-reload
   sudo systemctl enable dominion-api
   sudo systemctl start dominion-api
```

5. **Setup cron job**
```bash
   crontab -e
   # Add: 7 17 * * * TZ=America/New_York /path/to/run-extractor.sh
```

6. **Open firewall (optional for external access)**
```bash
   sudo ufw allow 5000/tcp
```
   Also configure Oracle Cloud Security List for port 5000.

## Verify
```bash
curl http://localhost:5000/health
```
