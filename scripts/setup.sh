set -e
apt-get update -y
apt-get install -y python3 python3-venv python3-pip curl wget sqlite3
python3 -m venv /opt/truevpn/venv
/opt/truevpn/venv/bin/pip install --upgrade pip
/opt/truevpn/venv/bin/pip install -r /opt/truevpn/requirements.txt
cp /opt/truevpn/systemd/*.service /etc/systemd/system/
cp /opt/truevpn/systemd/*.timer /etc/systemd/system/
systemctl daemon-reload
systemctl enable truevpn-bot.service
systemctl enable truevpn-server.service
systemctl enable truevpn-sync.timer
echo "TrueVPN installation completed successfully."
