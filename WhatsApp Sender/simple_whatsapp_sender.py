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

class SimpleWhatsAppSender:
    def __init__(self):
        self.driver = None
        self.setup_driver()
    
    def setup_driver(self):
        """Setup Chrome WebDriver with minimal options for better stability"""
        chrome_options = Options()
        
        # Minimal Chrome options - more stable
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1200,800")
        
        try:
            # Install and setup ChromeDriver
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            self.driver.maximize_window()
            print("✅ Chrome WebDriver initialized successfully")
        except Exception as e:
            print(f"❌ Error setting up Chrome WebDriver: {e}")
            raise e
    
    def login_whatsapp(self):
        """Navigate to WhatsApp Web and handle login"""
        try:
            print("🌐 Navigating to WhatsApp Web...")
            self.driver.get("https://web.whatsapp.com")
            
            # Wait a bit for page to load
            time.sleep(5)
            
            print("⏳ Checking if WhatsApp Web loaded...")
            
            # Check page title
            if "WhatsApp" not in self.driver.title:
                return "error"
            
            # Simple check - look for either QR code or chat interface
            try:
                # Wait for page to fully load
                WebDriverWait(self.driver, 15).until(
                    lambda driver: driver.execute_script("return document.readyState") == "complete"
                )
                
                # Check for QR code canvas or any WhatsApp element
                qr_present = len(self.driver.find_elements(By.CSS_SELECTOR, "canvas")) > 0
                chats_present = len(self.driver.find_elements(By.CSS_SELECTOR, "[data-testid*='chat']")) > 0
                
                if qr_present:
                    print("📱 QR Code detected - need to scan")
                    return "qr_needed"
                elif chats_present:
                    print("✅ Already logged in!")
                    return "logged_in"
                else:
                    print("⏳ WhatsApp is loading...")
                    return "qr_needed"  # Assume QR needed if unclear
                    
            except Exception as e:
                print(f"⚠️ Error checking login status: {e}")
                return "qr_needed"  # Default to QR needed
                
        except Exception as e:
            print(f"❌ Error accessing WhatsApp Web: {e}")
            return "error"
    
    def send_message(self, phone_number, message, progress_callback=None):
        """Send message to a specific phone number"""
        try:
            # Clean phone number
            clean_number = phone_number.replace("+", "").replace(" ", "").replace("-", "")
            
            # Encode message for URL
            encoded_message = urllib.parse.quote(message)
            
            # Create WhatsApp URL
            whatsapp_url = f"https://web.whatsapp.com/send?phone={clean_number}&text={encoded_message}"
            
            if progress_callback:
                progress_callback(f"📱 Opening chat for {clean_number}...")
            
            # Navigate to WhatsApp chat
            self.driver.get(whatsapp_url)
            
            # Wait for page to load
            time.sleep(8)  # Longer wait for stability
            
            if progress_callback:
                progress_callback(f"💬 Sending message to {clean_number}...")
            
            # Try multiple methods to actually send the message
            message_sent = False
            
            # Method 1: Click the send button
            try:
                send_button_selectors = [
                    "[data-testid='send']",
                    "button[aria-label*='Send']",
                    "span[data-icon='send']",
                    "button[data-tab='11']"
                ]
                
                for selector in send_button_selectors:
                    try:
                        send_button = WebDriverWait(self.driver, 3).until(
                            EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                        )
                        send_button.click()
                        message_sent = True
                        break
                    except:
                        continue
                        
            except:
                pass
            
            # Method 2: Press Enter in the message input box
            if not message_sent:
                try:
                    input_selectors = [
                        "[data-testid='conversation-compose-box-input']",
                        "div[contenteditable='true'][data-tab='10']",
                        "[contenteditable='true'][role='textbox']",
                        "div[contenteditable='true']"
                    ]
                    
                    for selector in input_selectors:
                        try:
                            message_box = self.driver.find_element(By.CSS_SELECTOR, selector)
                            message_box.click()  # Focus on the input
                            time.sleep(1)
                            message_box.send_keys(Keys.ENTER)
                            message_sent = True
                            break
                        except:
                            continue
                except:
                    pass
            
            # Method 3: JavaScript click on send button
            if not message_sent:
                try:
                    self.driver.execute_script("""
                        // Find and click send button using JavaScript
                        const sendButton = document.querySelector('[data-testid="send"]') || 
                                         document.querySelector('button[aria-label*="Send"]') ||
                                         document.querySelector('span[data-icon="send"]').closest('button');
                        if (sendButton) {
                            sendButton.click();
                            return true;
                        }
                        return false;
                    """)
                    message_sent = True
                except:
                    pass
            
            # Method 4: Press Ctrl+Enter (WhatsApp shortcut)
            if not message_sent:
                try:
                    message_box = self.driver.find_element(By.CSS_SELECTOR, "[contenteditable='true']")
                    message_box.send_keys(Keys.CONTROL + Keys.ENTER)
                    message_sent = True
                except:
                    pass
            
            time.sleep(2)
            
            if message_sent:
                if progress_callback:
                    progress_callback(f"✅ Message sent to {clean_number}")
                return True
            else:
                if progress_callback:
                    progress_callback(f"⚠️ Message typed but may need manual send for {clean_number}")
                return False
            
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
        page_title="Simple WhatsApp Bulk Sender",
        page_icon="📱",
        layout="wide"
    )
    
    st.title("📱 Simple WhatsApp Bulk Message Sender")
    st.markdown("**Simplified version - More reliable!**")
    st.markdown("---")
    
    # Sidebar for configuration
    with st.sidebar:
        st.header("⚙️ Configuration")
        
        # Data source selection
        data_source = st.radio(
            "Choose data source:",
            ["Google Sheets", "Upload Excel File"]
        )
        
        if data_source == "Google Sheets":
            sheet_url = st.text_input(
                "Google Sheet URL:",
                placeholder="https://docs.google.com/spreadsheets/d/your-sheet-id/edit"
            )
        else:
            uploaded_file = st.file_uploader("Upload Excel File", type=['xlsx', 'xls'])
        
        # Message delay setting
        message_delay = st.slider(
            "Delay between messages (seconds):",
            min_value=3,
            max_value=30,
            value=8,
            help="Longer delays are more reliable"
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
            else:
                st.success("✅ Data format is correct")
        else:
            st.info("📋 Please provide contact data using one of the options in the sidebar")
    
    with col2:
        st.header("🚀 Send Messages")
        
        if df is not None and not df.empty and not any(col for col in ['Number', 'Message'] if col not in df.columns):
            
            # Initialize session state
            if 'simple_sender' not in st.session_state:
                st.session_state.simple_sender = None
            if 'is_sending' not in st.session_state:
                st.session_state.is_sending = False
            
            # Initialize WhatsApp
            if st.button("🔧 Initialize WhatsApp", type="secondary"):
                with st.spinner("Setting up Chrome and WhatsApp Web..."):
                    try:
                        if st.session_state.simple_sender:
                            st.session_state.simple_sender.close()
                        
                        st.session_state.simple_sender = SimpleWhatsAppSender()
                        login_status = st.session_state.simple_sender.login_whatsapp()
                        
                        if login_status == "qr_needed":
                            st.warning("📱 Please scan the QR code in the Chrome window that opened")
                            st.info("After scanning, you can start sending messages!")
                        elif login_status == "logged_in":
                            st.success("✅ WhatsApp Web is ready!")
                        else:
                            st.error("❌ Could not connect to WhatsApp Web")
                            
                    except Exception as e:
                        st.error(f"❌ Error: {str(e)}")
            
            st.markdown("---")
            
            # Send messages button
            if st.button("📤 Send All Messages", type="primary", disabled=st.session_state.is_sending):
                
                if st.session_state.simple_sender is None:
                    st.error("❌ Please initialize WhatsApp first!")
                else:
                    st.session_state.is_sending = True
                    
                    # Progress tracking
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    results_container = st.empty()
                    
                    results = []
                    total_contacts = len(df)
                    
                    try:
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
                                    'Time': datetime.now().strftime("%H:%M:%S"),
                                    'Number': phone_number,
                                    'Status': msg
                                })
                                
                                # Update results display
                                if results:
                                    results_df = pd.DataFrame(results)
                                    results_container.dataframe(results_df, use_container_width=True)
                            
                            success = st.session_state.simple_sender.send_message(
                                phone_number, 
                                message, 
                                progress_callback=update_status
                            )
                            
                            # Wait between messages
                            if index < total_contacts - 1:
                                for i in range(message_delay):
                                    status_text.text(f"⏳ Waiting {message_delay - i} seconds before next message...")
                                    time.sleep(1)
                        
                        # Final status
                        successful_sends = sum(1 for result in results if "✅" in result['Status'])
                        status_text.success(f"🎉 Completed! {successful_sends}/{total_contacts} messages sent")
                        
                    except Exception as e:
                        st.error(f"❌ An error occurred: {str(e)}")
                    finally:
                        st.session_state.is_sending = False
            
            # Stop button
            if st.session_state.is_sending:
                if st.button("🛑 Stop Sending"):
                    st.session_state.is_sending = False
                    st.warning("⏹️ Sending stopped by user")
        
        else:
            st.info("📋 Load valid contact data first")
    
    # Footer
    st.markdown("---")
    st.info("💡 **Tip:** Test with 1-2 contacts first before sending to many people!")

if __name__ == "__main__":
    main()