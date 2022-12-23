set -e

echo "Preparing for launch!"
python manage.py collectstatic --no-input
python manage.py migrate

python -c 'from solcx import install_solc; print(f"""Solidity Version installed: {install_solc(version="0.8.7")}""");'
echo "Release phase complete"
