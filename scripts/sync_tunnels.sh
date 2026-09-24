set -e
cd /opt/truevpn
HH=$(date +%H)
cp database.db database.db.hourly_$HH
/opt/truevpn/venv/bin/python3 tunnel.py >> /var/log/truevpn-sync.log 2>&1
