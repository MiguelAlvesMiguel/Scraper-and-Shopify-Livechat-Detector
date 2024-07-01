import requests
import wget
import zipfile
import os
from bs4 import BeautifulSoup
import re
import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
import time
import subprocess

# List of known directory sites to exclude
EXCLUDED_SITES = ["yelp.com", "amazon.com", "wikipedia.org", "tripadvisor.com", "facebook.com"]

def get_chrome_version():
    """Get the current version of the Chrome browser installed on the system."""
    output = subprocess.check_output(
        r'wmic datafile where name="C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe" get Version /value',
        shell=True
    )
    version = output.decode().strip().split('=')[1]
    return version

def get_chromedriver_version(chrome_version):
    """Get the matching chromedriver version for the installed Chrome browser version."""
    major_version = chrome_version.split('.')[0]
    url = f'https://chromedriver.storage.googleapis.com/LATEST_RELEASE_{major_version}'
    response = requests.get(url)
    return response.text.strip()

def download_chromedriver(version):
    """Download the chromedriver matching the installed Chrome browser version."""
    driver_path = 'chromedriver.exe'
    if not os.path.exists(driver_path):
        print("Chromedriver not found, downloading...")
        
        # Get the latest version of chromedriver for the current Chrome version
        download_url = f"https://chromedriver.storage.googleapis.com/{version}/chromedriver_win32.zip"
        latest_driver_zip = wget.download(download_url, 'chromedriver.zip')
        
        with zipfile.ZipFile(latest_driver_zip, 'r') as zip_ref:
            zip_ref.extractall()
        
        os.remove(latest_driver_zip)
        print("Chromedriver downloaded and extracted.")
    else:
        print("Chromedriver already exists.")

def google_search(query):
    options = Options()
    options.headless = True  # Run Chrome in headless mode
    service = Service('chromedriver.exe')  # Path to the ChromeDriver executable
    driver = webdriver.Chrome(service=service, options=options)
    
    links = []
    for page in range(0, 2):  # Loop through the first 2 pages
        start = page * 10
        search_url = f"https://www.google.com/search?q={query}&start={start}"
        driver.get(search_url)
        
        # Wait for the results to load
        time.sleep(2)
        
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        search_results = soup.find_all('div', class_='yuRUbf')
        for result in search_results:
            a_tag = result.find('a', href=True)
            if a_tag:
                link = a_tag['href']
                if not any(site in link for site in EXCLUDED_SITES):
                    links.append(link)
    
    print(f"Found {len(links)} links on the Google search pages.")
    
    driver.quit()
    return links

def check_shopify(url):
    print(f"Checking if {url} uses Shopify...")
    try:
        response = requests.get(url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        if 'Shopify' in response.text or soup.find(attrs={'data-shopify'}):
            print(f"{url} is using Shopify.")
            return True
        print(f"{url} is not using Shopify.")
        return False
    except requests.RequestException as e:
        print(f"Error checking Shopify for {url}: {e}")
        return False

def find_contact_info(url):
    print(f"Searching for contact info on {url}...")
    try:
        response = requests.get(url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        email = None
        contact_form = None
        
        # Find email
        email_match = re.search(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,4}", response.text)
        if email_match:
            email = email_match.group(0)
            print(f"Found email: {email}")
        
        # Find contact form
        contact_form_element = soup.find('a', href=True, text=re.compile(r'Contact|Contact Us|Support', re.I))
        if contact_form_element:
            contact_form = contact_form_element['href']
            print(f"Found contact form: {contact_form}")
        
        return email, contact_form
    except requests.RequestException as e:
        print(f"Error finding contact info for {url}: {e}")
        return None, None

def check_live_chat(url):
    print(f"Checking for live chat solutions on {url}...")
    try:
        response = requests.get(url)
        response.raise_for_status()
        live_chat_solutions = ['gorgias', 'livechat.com', 'tidio', 'zendesk', 'tawk.to', 'intercom', 'drift', 'snapengage']
        for solution in live_chat_solutions:
            if solution in response.text:
                print(f"Found live chat solution: {solution} on {url}")
                return solution
        print(f"No live chat solution found on {url}")
        return None
    except requests.RequestException as e:
        print(f"Error checking live chat for {url}: {e}")
        return None

def main(query):
    chrome_version = get_chrome_version()
    chromedriver_version = get_chromedriver_version(chrome_version)
    download_chromedriver(chromedriver_version)
    search_results = google_search(query)
    data = []
    
    for result in search_results:
        url = result
        print(f"Processing {url}...")
        shopify = check_shopify(url)
        email, contact_form = find_contact_info(url)
        live_chat = check_live_chat(url)
        
        data.append({
            'URL': url,
            'Shopify': shopify,
            'Email': email,
            'Contact Form': contact_form,
            'Live Chat Solution': live_chat
        })
    
    df = pd.DataFrame(data)
    df.to_excel('lead_report.xlsx', index=False)
    print("Data collection complete. Report saved to 'lead_report.xlsx'.")
    print(df)

# Example usage
main("luggage store")
