@echo off
echo Skapar pokerstrategi-databas...
echo.

echo Steg 1: Skapar databasschema...
python create_database.py
if %ERRORLEVEL% NEQ 0 (
    echo Fel vid skapande av databas!
    pause
    exit /b %ERRORLEVEL%
)
echo.

echo Steg 2: Importerar data från traed...
python populate_database.py
if %ERRORLEVEL% NEQ 0 (
    echo Fel vid import av data!
    pause
    exit /b %ERRORLEVEL%
)
echo.

echo Databas framgångsrikt skapad och population klar!
echo Se database_readme.md för mer information om hur databasen kan användas.
echo.

pause 