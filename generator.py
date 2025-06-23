import random
import string
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from PIL import Image
import pytesseract
import time
import tempfile
import logging
from fake_useragent import UserAgent
import os

# Setup logging to track errors
logging.basicConfig(filename='steam_generator.log', level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"  # Update if Tesseract is elsewhere
ua = UserAgent()

def generate_random_string(length):
    """Generate a random string of letters and digits."""
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

def generate_email():
    """Generate a random email address."""
    domains = ["gmail.com","yahoo.com","hotmail.com"]
    return f"{generate_random_string(10)}@{random.choice(domains)}"

def setup_driver():
    """Set up Chrome WebDriver with user agent and anti-detection settings."""
    options = webdriver.ChromeOptions()
    options.add_argument(f'--user-agent={ua.random}')
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--no-sandbox')
    options.add_argument('--window-size=1920,1080')
    options.add_experimental_option('excludeSwitches', ['enable-automation'])
    options.add_experimental_option('useAutomationExtension', False)
    # Comment out headless for debugging
    # options.add_argument('--headless')
    try:
        driver = webdriver.Chrome(options=options)
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        logging.info("WebDriver initialized successfully.")
        return driver
    except Exception as e:
        logging.error(f"WebDriver setup failed: {e}")
        raise Exception("Failed to initialize WebDriver. Check ChromeDriver version.")

def preprocess_image(image_path):
    """Preprocess image for better OCR results."""
    try:
        img = Image.open(image_path).convert('L')  # Convert to grayscale
        img = img.resize((int(img.width* 2), int(img.height* 2)))  # Increase resolution
        return img
    except Exception as e:
        logging.error(f"Image preprocessing failed: {e}")
        return None

def solve_hcaptcha(driver):
    """Attempt to solve hCaptcha using OCR."""
    try:
        # Switch to hCaptcha iframe
        WebDriverWait(driver, 15).until(
            EC.frame_to_be_available_and_switch_to_it((By.XPATH,"//iframe[@title='widget containing checkbox for hCaptcha security challenge']"))
        )
        checkbox = WebDriverWait(driver, 15).until(
            EC.element_to_be_clickable((By.ID,"checkbox"))
        )
        checkbox.click()
        driver.switch_to.default_content()

        # Handle image-based hCaptcha
        try:
            WebDriverWait(driver, 15).until(
                EC.frame_to_be_available_and_switch_to_it((By.XPATH,"//iframe[contains(@title, 'hCaptcha challenge')]"))
            )
            image_element = WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.XPATH,"//img"))
            )
            image_url = image_element.get_attribute("src")

            # Download image
            response = requests.get(image_url, timeout=10)
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
            temp_file.write(response.content)
            temp_file.close()

            # Preprocess and OCR
            image = preprocess_image(temp_file.name)
            if not image:
                logging.error("Image preprocessing returned None.")
                os.unlink(temp_file.name)
                return False
            text = pytesseract.image_to_string(image).strip()
            os.unlink(temp_file.name)

            # Input OCR result (simplified, assumes text input)
            try:
                input_field = driver.find_element(By.XPATH,"//input[@type='text']")
                input_field.send_keys(text)
                input_field.send_keys(Keys.ENTER)
            except:
                logging.warning("No text input field found. Assuming click-based challenge.")

            driver.switch_to.default_content()
            # Check if hCaptcha passed
            WebDriverWait(driver, 15).until(
                EC.invisibility_of_element((By.XPATH,"//iframe[contains(@title, 'hCaptcha')]"))
            )
            logging.info("hCaptcha solved successfully.")
            return True
        except:
            logging.warning("No image-based hCaptcha found. Assuming checkbox-only.")
            driver.switch_to.default_content()
            return True
    except Exception as e:
        logging.error(f"hCaptcha solving failed: {e}")
        return False

def create_steam_account():
    """Create a single Steam account."""
    driver = setup_driver()
    try:
        # Try loading the page with retries
        for attempt in range(3):
            try:
                driver.get("https://store.steampowered.com/join/")
                WebDriverWait(driver, 15).until(
                    EC.presence_of_element_located((By.ID,"email"))
                )
                break
            except Exception as e:
                logging.error(f"Page load attempt {attempt + 1} failed: {e}")
                if attempt == 2:
                    logging.error("Failed to load Steam join page after retries.")
                    return None
                time.sleep(5)

        # Fill in account details
        email = generate_email()
        driver.find_element(By.ID,"email").send_keys(email)
        driver.find_element(By.ID,"reenter_email").send_keys(email)

        # Handle hCaptcha
        if not solve_hcaptcha(driver):
            logging.error("Failed to bypass hCaptcha.")
            return None

        # Generate username and password
        username = generate_random_string(10)
        password = generate_random_string(12)
        driver.find_element(By.ID,"accountname").send_keys(username)
        driver.find_element(By.ID,"password").send_keys(password)
        driver.find_element(By.ID,"reenter_password").send_keys(password)

        # Submit form
        submit_button = WebDriverWait(driver, 15).until(
            EC.element_to_be_clickable((By.XPATH,"//button[@type='submit']"))
        )
        submit_button.click()

        # Wait for account creation confirmation
        try:
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.CLASS_NAME,"new_account_created"))
            )
            logging.info(f"Account created: {username}")
            return {"username": username,"password": password,"email": email}
        except Exception as e:
            logging.error(f"Account creation confirmation failed: {e}")
            # Dump page source for debugging
            with open("steam_page_source.html","w", encoding="utf-8") as f:
                f.write(driver.page_source)
            logging.info("Page source dumped to steam_page_source.html")
            return None
    except Exception as e:
        logging.error(f"Account creation failed: {e}")
        return None
    finally:
        driver.quit()

def main():
    """Main function to generate multiple accounts."""
    try:
        num_accounts = int(input("How many Steam accounts to generate? "))
        for _ in range(num_accounts):
            try:
                account = create_steam_account()
                if account:
                    print(f"Generated Account:\nUsername: {account['username']}\nPassword: {account['password']}\nEmail: {account['email']}\n")
                else:
                    print("Failed to generate account. Check logs for details.")
                time.sleep(random.uniform(5, 10))  # Random delay to avoid detection
            except Exception as e:
                logging.error(f"Error generating account: {e}")
                print("An error occurred while generating an account.")
    except (ValueError, EOFError):
        logging.error("Invalid input for number of accounts.")
        print("Please enter a valid number.")

if __name__ == "__main__":
    main()
