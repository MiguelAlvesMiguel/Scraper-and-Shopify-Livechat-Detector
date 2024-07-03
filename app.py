import os
import requests
import wget
import zipfile
from flask import Flask, render_template, request, jsonify, send_file
from flask_socketio import SocketIO, emit
from bs4 import BeautifulSoup
import re
import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
import time
import subprocess
import matplotlib.pyplot as plt
from io import BytesIO
from urllib.parse import urlparse
import platform
# Ensure xlsxwriter is installed
try:
    import xlsxwriter
except ImportError:
    os.system('pip install xlsxwriter')

# Initialize Flask app and SocketIO
app = Flask(__name__)
app.config['TEMPLATES_AUTO_RELOAD'] = True
socketio = SocketIO(app)

# List of known directory sites to exclude
EXCLUDED_SITES = ["yelp.com", "amazon.com", "wikipedia.org", "tripadvisor.com", "facebook.com"]

# List of live chat services to check for
live_chat_services = [
    'gorgias', 'livechat.com', 'tidio', 'zendesk', 'tawk.to', 'intercom', 'drift', 'snapengage', 'gladlychat',
    'liveperson', 'crisp.chat', 'smartsupp', 'purechat', 'clickdesk', 'chatra', 'kayako', 'olark', 'boldchat',
    'snapengage', 'zopim', 'userlike', 'freshchat', 'comm100', 'richpanel', 'chat-app'
]

results_data = []
shopify_without_livechat_data = []
processed_domains = set()


def get_chrome_version():
    """Get the current version of the Chrome browser installed on the system."""
    try:
        output = subprocess.check_output(
            ["google-chrome", "--version"]
        )
        version = output.decode().strip().split(' ')[2]
        return version
    except Exception as e:
        print(f"Error getting Chrome version: {e}")
        return None

def download_chromedriver(version):
    """Download the chromedriver matching the installed Chrome browser version."""
    driver_path = 'chromedriver.exe'
    if not os.path.exists(driver_path):
        print("Chromedriver not found, downloading...")
        
        # Download chromedriver for the specified version
        system = platform.system()
        if system == "Darwin":  # macOS
            download_url = f"https://chromedriver.storage.googleapis.com/{version}/chromedriver_mac64.zip"
        elif system == "Linux":
            download_url = f"https://chromedriver.storage.googleapis.com/{version}/chromedriver_linux64.zip"
        else:
            download_url = f"https://chromedriver.storage.googleapis.com/{version}/chromedriver_win32.zip"

        latest_driver_zip = wget.download(download_url, 'chromedriver.zip')
        
        with zipfile.ZipFile(latest_driver_zip, 'r') as zip_ref:
            zip_ref.extractall()
        
        os.remove(latest_driver_zip)
        print("Chromedriver downloaded and extracted.")
    else:
        print("Chromedriver already exists.")

def get_main_domain(url):
    """Extract the main domain from a URL."""
    parsed_url = urlparse(url)
    return parsed_url.netloc

def google_search(query, num_pages):
    options = Options()
    options.headless = True  # Run Chrome in headless mode
    service = Service('chromedriver.exe')  # Path to the ChromeDriver executable
    driver = webdriver.Chrome(service=service, options=options)
    
    max_retries = 3
    retries = 0
    links = []

    while retries < max_retries and len(links) == 0:
        for page in range(0, num_pages):  # Loop through the specified number of pages
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
                    main_domain = get_main_domain(link)
                    if not any(site in link for site in EXCLUDED_SITES) and main_domain not in processed_domains:
                        links.append(link)
                        processed_domains.add(main_domain)
                        socketio.emit('update', {'message': f"Found {len(links)} websites, scraping in progress..."})
        
        if len(links) == 0:
            retries += 1
            print(f"No links found, retrying... ({retries}/{max_retries})")

    print(f"Found {len(links)} links on the Google search pages.")
    
    driver.quit()
    return links


def check_shopify(url):
    print(f"Checking if {url} uses Shopify...")
    try:
        response = requests.get(url, timeout=3)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        if 'Shopify' in response.text or soup.find(attrs={'data-shopify'}) or soup.find('link', {'href': re.compile(r'\.myshopify\.com')}):
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
        response = requests.get(url, timeout=3)
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
            if not contact_form.startswith('http'):
                contact_form = url + contact_form
            print(f"Found contact form: {contact_form}")
        
        return email, contact_form
    except requests.RequestException as e:
        print(f"Error finding contact info for {url}: {e}")
        return None, None

def check_live_chat(url):
    print(f"Checking for live chat solutions on {url}...")
    try:
        response = requests.get(url, timeout=3)
        response.raise_for_status()
        if 'CHAT WITH US' in response.text:
            return 'UNKNOWN'
        for solution in live_chat_services:
            if solution in response.text:
                print(f"Found live chat solution: {solution} on {url}")
                return solution
        print(f"No live chat solution found on {url}")
        return None
    except requests.RequestException as e:
        print(f"Error checking live chat for {url}: {e}")
        return None

def scrape_data(query, num_pages):
    global results_data
    global shopify_without_livechat_data
    results_data = []
    shopify_without_livechat_data = []
    chrome_version = get_chrome_version()
    download_chromedriver(chrome_version)
    search_results = google_search(query, num_pages)
    data = {}
    
    for result in search_results:
        url = result
        print(f"Processing {url}...")
        shopify = check_shopify(url)
        email, contact_form = find_contact_info(url)
        live_chat = check_live_chat(url)
        
        if url not in data:
            data[url] = {
                'URL': url,
                'Shopify': shopify,
                'Email': email,
                'Contact_Form': contact_form,
                'Live_Chat_Solution': live_chat
            }
        else:
            # Update existing record with new information
            data[url]['Shopify'] = shopify
            data[url]['Email'] = email
            data[url]['Contact_Form'] = contact_form
            data[url]['Live_Chat_Solution'] = live_chat
        
        # Append result to results_data for real-time updates
        results_data.append(data[url])
        socketio.emit('update', {'results_data': data[url]})
        print(f"Processed {url}: {data[url]}")
        
        # Append to shopify_without_livechat_data if it matches the criteria
        if shopify and not live_chat:
            shopify_without_livechat_data.append(data[url])
    
    df = pd.DataFrame(data.values())
    df.to_excel('lead_report.xlsx', index=False)

    # Filter for Shopify stores without live chat solutions
    no_live_chat_df = df[(df['Shopify'] == True) & (df['Live_Chat_Solution'].isna())]
    no_live_chat_df.to_excel('shopify_without_livechat.xlsx', index=False)

    # Ensure static directory exists
    if not os.path.exists('static'):
        os.makedirs('static')

    # Generate pie chart for live chat solution usage
    total_sites = len(df)
    sites_with_live_chat = len(df[df['Live_Chat_Solution'].notna()])
    sites_without_live_chat = total_sites - sites_with_live_chat

    labels = ['With Live Chat', 'Without Live Chat']
    sizes = [sites_with_live_chat, sites_without_live_chat]
    colors = ['#ff9999','#66b3ff']
    explode = (0.1, 0)  # explode the first slice

    plt.pie(sizes, explode=explode, labels=labels, colors=colors,
            autopct='%1.1f%%', shadow=True, startangle=140)
    plt.title(f"Live Chat Solution Usage for: {query}")
    plt.axis('equal')  # Equal aspect ratio ensures that pie is drawn as a circle.

    try:
        plt.savefig('static/live_chat_usage_pie_chart.png')
        print("Pie chart saved successfully.")
        socketio.emit('update', {'pie_chart': 'static/live_chat_usage_pie_chart.png'})
    except Exception as e:
        print(f"Error saving pie chart: {e}")
    
    print("Data collection complete. Reports saved to 'lead_report.xlsx' and 'shopify_without_livechat.xlsx'.")
    socketio.emit('scraping_complete')
    return df

@app.route('/', methods=['GET', 'POST'])
def index():
    return render_template('index.html')

@app.route('/scrape', methods=['POST'])
def scrape():
    query = request.form['query']
    num_pages = int(request.form['num_pages'])
    socketio.start_background_task(target=scrape_data, query=query, num_pages=num_pages)
    return jsonify(success=True)

@app.route('/download/<filename>')
def download_file(filename):
    path = os.path.join(app.root_path, filename)
    return send_file(path, as_attachment=True)

@app.route('/export')
def export():
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        pd.DataFrame(results_data).to_excel(writer, sheet_name='All Results', index=False)
        pd.DataFrame(shopify_without_livechat_data).to_excel(writer, sheet_name='Shopify without Live Chat', index=False)
    output.seek(0)
    return send_file(output, download_name="exported_data.xlsx", as_attachment=True)

if __name__ == '__main__':
    socketio.run(app, debug=True)
