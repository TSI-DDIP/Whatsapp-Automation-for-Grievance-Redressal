@echo off
echo Installing required files (first time only)...
pip install -r requirements.txt
echo.
echo Starting WhatsApp Bulk Sender...
echo Your app will open in the browser shortly!
echo.
streamlit run whatsapp_bulk_sender.py
pause