#!/bin/bash
# Install raspi-looper systemd service

echo "Installing raspi-looper service..."

# Copy service file to systemd directory
sudo cp raspi-looper.service /etc/systemd/system/

# Reload systemd to recognize the new service
sudo systemctl daemon-reload

# Enable the service to start on boot
sudo systemctl enable raspi-looper.service

# Start the service now
sudo systemctl start raspi-looper.service

# Show status
sudo systemctl status raspi-looper.service

echo ""
echo "Service installed and started!"
echo ""
echo "Useful commands:"
echo "  sudo systemctl status raspi-looper   # Check status"
echo "  sudo systemctl stop raspi-looper     # Stop service"
echo "  sudo systemctl start raspi-looper    # Start service"
echo "  sudo systemctl restart raspi-looper  # Restart service"
echo "  sudo systemctl disable raspi-looper  # Disable autostart"
echo "  sudo journalctl -u raspi-looper -f   # View live logs"
