#!/bin/bash
# Script to enable I2C on Raspberry Pi

echo "Enabling I2C interface..."

# Enable I2C in config
if ! grep -q "^dtparam=i2c_arm=on" /boot/config.txt; then
    echo "dtparam=i2c_arm=on" | sudo tee -a /boot/config.txt
    echo "Added I2C to /boot/config.txt"
else
    echo "I2C already enabled in /boot/config.txt"
fi

# Load I2C kernel modules
sudo modprobe i2c-dev
sudo modprobe i2c-bcm2835

# Add modules to load at boot
if ! grep -q "^i2c-dev" /etc/modules; then
    echo "i2c-dev" | sudo tee -a /etc/modules
fi

echo ""
echo "I2C setup complete!"
echo ""
echo "IMPORTANT WIRING INFO:"
echo "====================="
echo ""
echo "For OLED (SSD1306 - as per your gpio_connections.txt):"
echo "  VCC  -> 3.3V (Pin 1 or 17)"
echo "  GND  -> Ground"
echo "  SDA  -> GPIO2 (Pin 3)"
echo "  SCL  -> GPIO3 (Pin 5)"
echo ""
echo "For LCD (HD44780 with PCF8574 backpack):"
echo "  VCC  -> 5V (Pin 2 or 4) **NOT 3.3V**"
echo "  GND  -> Ground"
echo "  SDA  -> GPIO2 (Pin 3)"
echo "  SCL  -> GPIO3 (Pin 5)"
echo ""
echo "Installing required packages..."
sudo pip3 install adafruit-circuitpython-ssd1306 pillow

echo ""
echo "Please REBOOT your Raspberry Pi for changes to take effect:"
echo "  sudo reboot"
echo ""
echo "After reboot, check I2C devices with:"
echo "  i2cdetect -y 1"
echo ""
echo "Common I2C addresses:"
echo "  OLED SSD1306: 0x3C or 0x3D"
echo "  LCD PCF8574:  0x27 or 0x3F"
