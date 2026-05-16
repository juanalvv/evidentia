# Quickstart script for python env and pkgs.

cat << 'EOF'
    _______    __________  _______   _______________ 
   / ____/ |  / /  _/ __ \/ ____/ | / /_  __/  _/   |
  / __/  | | / // // / / / __/ /  |/ / / /  / // /| |
 / /___  | |/ // // /_/ / /___/ /|  / / / _/ // ___ |
/_____/  |___/___/_____/_____/_/ |_/ /_/ /___/_/  |_|
EOF

echo "-> Starting environment..."

if [ ! -f "venv/bin/activate" ]; then
    python3 -m venv venv
fi

echo "  activating venv..."
source venv/bin/activate

echo "  installing required packages..."
pip install -r requirements.txt


