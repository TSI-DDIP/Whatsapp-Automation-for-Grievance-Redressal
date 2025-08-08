import streamlit as st
import pandas as pd
import requests
import time
import logging
import io
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.keys import Keys
from webdriver_manager.chrome import ChromeDriverManager
import urllib.parse
import os
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class WhatsAppSender:
    def __init__(self):
        self.driver = None
        self.setup_driver()
    
    def setup_driver(self):
        """Setup Chrome WebDriver with persistent profile"""
        chrome_options = Options()
        
        # Create user data directory for persistent login
        user_data_dir = os.path.join(os.getcwd(), "chrome_profile")
        if not os.path.exists(user_data_dir):
            os.makedirs(user_data_dir)
        
        # More stable Chrome options
        chrome_options.add_argument(f"--user-data-dir={user_data_dir}")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--disable-web-security")
        chrome_options.add_argument("--disable-features=VizDisplayCompositor")
        chrome_options.add_argument("--remote-debugging-port=9222")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        # Install and setup ChromeDriver
        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=chrome_options)
        self.driver.maximize_window()
        self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    
    def login_whatsapp(self):
        """Navigate to WhatsApp Web and handle login"""
        self.driver.get("https://web.whatsapp.com")
        
        try:
            # Wait for either QR code or chat interface
            WebDriverWait(self.driver, 10).until(
                lambda driver: driver.find_elements(By.CSS_SELECTOR, "[data-testid='qr-code']") or
                             driver.find_elements(By.CSS_SELECTOR, "[data-testid='chat-list']")
            )
            
            # Check if QR code is present (not logged in)
            if self.driver.find_elements(By.CSS_SELECTOR, "[data-testid='qr-code']"):
                return "qr_needed"
            else:
                return "logged_in"
        except:
            return "error"
    
    def send_message(self, phone_number, message, progress_callback=None):
        """Send message to a specific phone number"""
        try:
            # Clean phone number (remove + and spaces)
            clean_number = phone_number.replace("+", "").replace(" ", "").replace("-", "")
            
            # Encode message for URL
            encoded_message = urllib.parse.quote(message)
            
            # Create WhatsApp URL
            whatsapp_url = f"https://web.whatsapp.com/send?phone={clean_number}&text={encoded_message}"
            
            if progress_callback:
                progress_callback(f"Opening chat for {clean_number}...")
            
            # Navigate to WhatsApp chat
            self.driver.get(whatsapp_url)
            
            # Wait for chat to load with multiple fallback selectors
            chat_loaded = False
            wait_selectors = [
                "[data-testid='conversation-compose-box-input']",
                "[contenteditable='true'][data-tab='10']",
                "div[contenteditable='true']",
                ".selectable-text[contenteditable='true']"
            ]
            
            for selector in wait_selectors:
                try:
                    WebDriverWait(self.driver, 15).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                    )
                    chat_loaded = True
                    break
                except:
                    continue
            
            if not chat_loaded:
                raise Exception("Could not load WhatsApp chat interface")
            
            time.sleep(3)  # Additional wait for stability
            
            if progress_callback:
                progress_callback(f"Sending message to {clean_number}...")
            
            # Try multiple methods to send the message
            message_sent = False
            
            # Method 1: Look for send button
            try:
                send_button = WebDriverWait(self.driver, 5).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "[data-testid='send']"))
                )
                send_button.click()
                message_sent = True
            except:
                pass
            
            # Method 2: Press Enter key in message box
            if not message_sent:
                try:
                    message_box = self.driver.find_element(By.CSS_SELECTOR, "[data-testid='conversation-compose-box-input']")
                    message_box.send_keys(Keys.ENTER)
                    message_sent = True
                except:
                    pass
            
            # Method 3: Alternative send button selector
            if not message_sent:
                try:
                    send_button = self.driver.find_element(By.CSS_SELECTOR, "button[aria-label*='Send']")
                    send_button.click()
                    message_sent = True
                except:
                    pass
            
            if not message_sent:
                raise Exception("Could not find send button or message box")
            
            if progress_callback:
                progress_callback(f"✅ Message sent to {clean_number}")
            
            return True
            
        except Exception as e:
            error_msg = f"❌ Failed to send to {clean_number}: {str(e)}"
            if progress_callback:
                progress_callback(error_msg)
            logger.error(error_msg)
            return False
    
    def close(self):
        """Close the WebDriver"""
        if self.driver:
            self.driver.quit()

def read_google_sheet(sheet_url):
    """Read data from Google Sheets CSV export URL"""
    try:
        # Convert Google Sheets URL to CSV export URL if needed
        if "docs.google.com/spreadsheets" in sheet_url and "export" not in sheet_url:
            # Extract sheet ID from URL
            if "/d/" in sheet_url:
                sheet_id = sheet_url.split("/d/")[1].split("/")[0]
                sheet_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"
        
        # Fetch the CSV data
        response = requests.get(sheet_url)
        response.raise_for_status()
        
        # Read CSV into pandas DataFrame
        df = pd.read_csv(io.StringIO(response.text))
        
        # Clean column names
        df.columns = df.columns.str.strip()
        
        return df
    except Exception as e:
        st.error(f"Error reading Google Sheet: {str(e)}")
        return None

def read_excel_file(uploaded_file):
    """Read data from uploaded Excel file"""
    try:
        df = pd.read_excel(uploaded_file)
        df.columns = df.columns.str.strip()
        return df
    except Exception as e:
        st.error(f"Error reading Excel file: {str(e)}")
        return None

def main():
    st.set_page_config(
        page_title="WhatsApp Bulk Sender",
        page_icon="📱",
        layout="wide"
    )
    
    st.title("📱 WhatsApp Bulk Message Sender")
    st.markdown("---")
    
    # Sidebar for configuration
    with st.sidebar:
        st.header("⚙️ Configuration")
        
        # Data source selection
        data_source = st.radio(
            "Choose data source:",
            ["Google Sheets", "Upload Excel File"],
            help="Select how you want to provide the contact data"
        )
        
        if data_source == "Google Sheets":
            sheet_url = st.text_input(
                "Google Sheet URL:",
                placeholder="https://docs.google.com/spreadsheets/d/your-sheet-id/edit",
                help="Make sure your sheet is publicly accessible or set to 'Anyone with link can view'"
            )
        else:
            uploaded_file = st.file_uploader(
                "Upload Excel File",
                type=['xlsx', 'xls'],
                help="Upload an Excel file with 'Number' and 'Message' columns"
            )
        
        # Message delay setting
        message_delay = st.slider(
            "Delay between messages (seconds):",
            min_value=1,
            max_value=30,
            value=5,
            help="Recommended: 5-10 seconds to avoid WhatsApp restrictions"
        )
    
    # Main content area
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.header("📊 Contact Data")
        
        # Load and preview data
        df = None
        if data_source == "Google Sheets" and sheet_url:
            with st.spinner("Loading data from Google Sheets..."):
                df = read_google_sheet(sheet_url)
        elif data_source == "Upload Excel File" and 'uploaded_file' in locals() and uploaded_file:
            with st.spinner("Reading Excel file..."):
                df = read_excel_file(uploaded_file)
        
        if df is not None and not df.empty:
            st.success(f"✅ Loaded {len(df)} contacts")
            st.dataframe(df, use_container_width=True)
            
            # Validate required columns
            required_columns = ['Number', 'Message']
            missing_columns = [col for col in required_columns if col not in df.columns]
            
            if missing_columns:
                st.error(f"❌ Missing required columns: {', '.join(missing_columns)}")
                st.info("Required columns: 'Number' and 'Message'")
            else:
                st.success("✅ Data format is correct")
        else:
            st.info("📋 Please provide contact data using one of the options in the sidebar")
    
    with col2:
        st.header("🚀 Send Messages")
        
        if df is not None and not df.empty and not any(col for col in ['Number', 'Message'] if col not in df.columns):
            # Initialize session state
            if 'whatsapp_sender' not in st.session_state:
                st.session_state.whatsapp_sender = None
            if 'is_sending' not in st.session_state:
                st.session_state.is_sending = False
            
            # Status container
            status_container = st.empty()
            
            # Login status check
            if st.button("🔐 Check WhatsApp Login Status", type="secondary"):
                with st.spinner("Checking WhatsApp login status..."):
                    if st.session_state.whatsapp_sender is None:
                        st.session_state.whatsapp_sender = WhatsAppSender()
                    
                    login_status = st.session_state.whatsapp_sender.login_whatsapp()
                    
                    if login_status == "qr_needed":
                        st.warning("📱 Please scan the QR code in the opened browser window to login to WhatsApp Web")
                        st.info("After scanning, click 'Send Messages' to start")
                    elif login_status == "logged_in":
                        st.success("✅ WhatsApp Web is ready!")
                    else:
                        st.error("❌ Error accessing WhatsApp Web")
            
            st.markdown("---")
            
            # Send messages button
            if st.button("📤 Send All Messages", type="primary", disabled=st.session_state.is_sending):
                if st.session_state.whatsapp_sender is None:
                    st.session_state.whatsapp_sender = WhatsAppSender()
                
                st.session_state.is_sending = True
                
                # Progress tracking
                progress_bar = st.progress(0)
                status_text = st.empty()
                results_container = st.empty()
                
                results = []
                total_contacts = len(df)
                
                try:
                    # Ensure WhatsApp is ready
                    login_status = st.session_state.whatsapp_sender.login_whatsapp()
                    
                    if login_status == "qr_needed":
                        st.error("❌ Please login to WhatsApp Web first by clicking 'Check WhatsApp Login Status'")
                        st.session_state.is_sending = False
                    else:
                        for index, row in df.iterrows():
                            phone_number = str(row['Number']).strip()
                            message = str(row['Message']).strip()
                            
                            # Update progress
                            progress = (index + 1) / total_contacts
                            progress_bar.progress(progress)
                            
                            # Send message
                            def update_status(msg):
                                status_text.text(msg)
                                results.append({
                                    'timestamp': datetime.now().strftime("%H:%M:%S"),
                                    'number': phone_number,
                                    'status': msg
                                })
                                
                                # Update results display
                                results_df = pd.DataFrame(results)
                                results_container.dataframe(results_df, use_container_width=True)
                            
                            success = st.session_state.whatsapp_sender.send_message(
                                phone_number, 
                                message, 
                                progress_callback=update_status
                            )
                            
                            # Wait between messages
                            if index < total_contacts - 1:  # Don't wait after the last message
                                time.sleep(message_delay)
                        
                        # Final status
                        successful_sends = sum(1 for result in results if "✅" in result['status'])
                        status_text.success(f"🎉 Completed! {successful_sends}/{total_contacts} messages sent successfully")
                        
                except Exception as e:
                    st.error(f"❌ An error occurred: {str(e)}")
                finally:
                    st.session_state.is_sending = False
            
            # Stop button
            if st.session_state.is_sending:
                if st.button("🛑 Stop Sending", type="secondary"):
                    if st.session_state.whatsapp_sender:
                        st.session_state.whatsapp_sender.close()
                        st.session_state.whatsapp_sender = None
                    st.session_state.is_sending = False
                    st.warning("⏹️ Sending stopped by user")
            
        else:
            st.info("📋 Load valid contact data first")
    
    # Footer
    st.markdown("---")
    with st.expander("ℹ️ How to use this tool"):
        st.markdown("""
        ### Steps to send bulk WhatsApp messages:
        
        1. **Prepare your data:**
           - **Google Sheets:** Create a sheet with 'Number' and 'Message' columns, make it public
           - **Excel File:** Upload a file with 'Number' and 'Message' columns
           
        2. **Phone number format:** Use international format without '+' (e.g., 919876543210)
        
        3. **Check WhatsApp login:** Click 'Check WhatsApp Login Status' and scan QR if needed
        
        4. **Send messages:** Click 'Send All Messages' and monitor the progress
        
        ### Important notes:
        - Keep delays between messages (5-10 seconds recommended)
        - Don't close the browser window while sending
        - Test with a few contacts first
        - WhatsApp may temporarily restrict accounts sending too many messages
        """)

if __name__ == "__main__":
    main()