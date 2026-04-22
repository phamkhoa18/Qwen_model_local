@echo off
REM ============================================
REM Upload VKS AI code to Vast.ai server
REM ============================================
REM
REM USAGE:
REM   deploy_to_vastai.bat <SSH_PORT>
REM
REM EXAMPLE:
REM   deploy_to_vastai.bat 12345
REM
REM Get SSH port from Vast.ai dashboard > Instance > Connect
REM ============================================

set SERVER_IP=175.28.230.22
set SERVER_USER=root
set REMOTE_DIR=/root/vks-ai-platform
set SSH_PORT=%1

if "%SSH_PORT%"=="" (
    echo.
    echo ERROR: Please provide SSH port!
    echo Usage: deploy_to_vastai.bat ^<SSH_PORT^>
    echo.
    echo Get SSH port from Vast.ai dashboard
    echo   Instance ^> Connect ^> SSH command
    echo.
    pause
    exit /b 1
)

echo.
echo ==============================================
echo   Deploying VKS AI to Vast.ai
echo   Server: %SERVER_IP%:%SSH_PORT%
echo ==============================================
echo.

REM 1. Upload setup script
echo [1/4] Uploading setup script...
scp -P %SSH_PORT% setup_vastai.sh %SERVER_USER%@%SERVER_IP%:/root/

REM 2. Upload backend
echo [2/4] Uploading backend code...
scp -P %SSH_PORT% -r backend %SERVER_USER%@%SERVER_IP%:%REMOTE_DIR%/

REM 3. Upload frontend
echo [3/4] Uploading frontend...
scp -P %SSH_PORT% -r frontend %SERVER_USER%@%SERVER_IP%:%REMOTE_DIR%/

REM 4. Upload config files
echo [4/4] Uploading config files...
scp -P %SSH_PORT% requirements.txt %SERVER_USER%@%SERVER_IP%:%REMOTE_DIR%/
scp -P %SSH_PORT% .env %SERVER_USER%@%SERVER_IP%:%REMOTE_DIR%/

echo.
echo ==============================================
echo   Upload complete!
echo.
echo   Now SSH into server and run:
echo     ssh -p %SSH_PORT% %SERVER_USER%@%SERVER_IP%
echo     chmod +x /root/setup_vastai.sh
echo     /root/setup_vastai.sh
echo     cd %REMOTE_DIR% ^&^& ./start.sh
echo ==============================================
echo.
pause
