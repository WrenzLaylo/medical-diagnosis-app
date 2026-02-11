@echo off
echo ====================================
echo Django Database Reset and Migration
echo ====================================
echo.

echo Step 1: Stopping any running Django servers...
taskkill /F /IM python.exe 2>nul
timeout /t 2 >nul
echo.

echo Step 2: Backing up current database...
if exist db.sqlite3 (
    copy db.sqlite3 db.sqlite3.backup
    echo Backup created: db.sqlite3.backup
) else (
    echo No existing database found.
)
echo.

echo Step 3: Deleting old database...
if exist db.sqlite3 (
    del db.sqlite3
    echo Database deleted.
)
echo.

echo Step 4: Cleaning migration files...
cd diagnosis\migrations
for %%f in (*.py) do (
    if not "%%f"=="__init__.py" (
        del "%%f"
        echo Deleted: %%f
    )
)
cd ..\..
echo.

echo Step 5: Creating __init__.py if missing...
type nul > diagnosis\migrations\__init__.py
echo.

echo Step 6: Creating new migrations...
python manage.py makemigrations
echo.

echo Step 7: Applying migrations...
python manage.py migrate
echo.

echo ====================================
echo Migration Complete!
echo ====================================
echo.
echo You can now start your server with:
echo python manage.py runserver
echo.
pause