@echo off
REM ============================================
REM VKS AI Platform - Setup Script (Windows)
REM ============================================

echo.
echo  ===== VKS AI Platform - Auto Setup =====
echo.

REM 1. Install Python dependencies
echo [1/3] Cai dat Python dependencies...
pip install -r requirements.txt

REM 2. Create .env if not exists
echo.
echo [2/3] Kiem tra .env...
if not exist .env (
    copy .env.example .env
    echo Da tao .env tu .env.example
    echo Hay sua SECRET_KEY va ADMIN_PASSWORD trong .env!
) else (
    echo .env da ton tai
)

REM 3. Done
echo.
echo =============================================
echo   Setup hoan tat!
echo.
echo   Chay server:
echo     python -m uvicorn backend.main:app --reload
echo.
echo   Truy cap: http://localhost:8000
echo   Admin:    admin / vks@2024
echo =============================================
echo.

pause
