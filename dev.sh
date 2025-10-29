#!/bin/bash

# Enter venv
source .venv/bin/activate

# Navigate to Django app directory
cd myapp

# Run Django setup commands
echo "Running collectstatic..."
python manage.py collectstatic --noinput

echo "Running migrations..."
python manage.py migrate

echo "Starting Tailwind CSS watch in new terminal..."
cd ..
x-terminal-emulator -e bash -c "npm run dev:css; echo 'Press Enter to close'; read" &
cd myapp

echo "Starting background worker in new terminal..."
x-terminal-emulator -e bash -c "source $(pwd)/../.venv/bin/activate && cd $(pwd) && python manage.py process_tasks; echo 'Press Enter to close'; read" &

echo "Starting web server in new terminal..."
x-terminal-emulator -e bash -c "source $(pwd)/../.venv/bin/activate && cd $(pwd) && python manage.py runserver; echo 'Press Enter to close'; read" &

echo "================================"
echo "All services started in separate terminals!"
echo ""
echo "To stop all services, run: ./stop_dev.sh"
echo "================================"