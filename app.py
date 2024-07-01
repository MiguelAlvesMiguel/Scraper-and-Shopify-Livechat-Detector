import os
import requests
import wget
import zipfile
from flask import Flask, render_template, request, redirect, url_for, jsonify
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

# Initialize Flask app
app = Flask(__name__)
app.config['TEMPLATES_AUTO_RELOAD'] = True

# List of known directory sites to exclude
EXCLUDED_SITES = ["yelp.com", "amazon.com", "wikipedia.org", "tripadvisor.com", "facebook.com"]

# List of live chat services to check for
live_chat_services = [
    'gorgias', 'livechat.com', 'tidio', 'zendesk', 'tawk.to', 'intercom', 'drift', 'snapengage', 'gladlychat',
    'liveperson', 'crisp.chat', 'smartsupp', 'purechat', 'clickdesk', 'chatra', 'kayako', 'olark', 'boldchat',
    'snapengage', 'zopim', 'userlike', 'freshchat', 'comm100', 'richpanel', 'chat-app'
]

results_data = []

def get_chrome_version():
    """Get the current version of the Chrome browser installed on the system."""
    output = subprocess.check_output(
        r'wmic datafile where name="C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe" get Version /value',
        shell=True
    )
    version = output.decode().strip().split('=')[1]
    return version

def download_chromedriver(version):
    """Download the chromedriver matching the installed Chrome browser version."""
    driver_path = 'chromedriver.exe'
    if not os.path.exists(driver_path):
        print("Chromedriver not found, downloading...")
        
        # Download chromedriver for the specified version
        download_url = f"https://storage.googleapis.com/chrome-for-testing-public/{version}/win64/chromedriver-win64.zip"
        latest_driver_zip = wget.download(download_url, 'chromedriver.zip')
        
        with zipfile.ZipFile(latest_driver_zip, 'r') as zip_ref:
            zip_ref.extractall()
        
        os.remove(latest_driver_zip)
        print("Chromedriver downloaded and extracted.")
    else:
        print("Chromedriver already exists.")

def google_search(query, num_pages):
    options = Options()
    options.headless = True  # Run Chrome in headless mode
    service = Service('chromedriver.exe')  # Path to the ChromeDriver executable
    driver = webdriver.Chrome(service=service, options=options)
    
    links = []
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
                if not any(site in link for site in EXCLUDED_SITES):
                    links.append(link)
    
    print(f"Found {len(links)} links on the Google search pages.")
    
    driver.quit()
    return links

def check_shopify(url):
    print(f"Checking if {url} uses Shopify...")
    try:
        response = requests.get(url, timeout=10)
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
        response = requests.get(url, timeout=10)
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
            contact_form = url + contact_form_element['href']
            print(f"Found contact form: {contact_form}")
        
        return email, contact_form
    except requests.RequestException as e:
        print(f"Error finding contact info for {url}: {e}")
        return None, None

def check_live_chat(url):
    print(f"Checking for live chat solutions on {url}...")
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
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
    results_data = []
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
                'Contact Form': contact_form,
                'Live Chat Solution': live_chat
            }
        else:
            # Update existing record with new information
            data[url]['Shopify'] = shopify
            data[url]['Email'] = email
            data[url]['Contact Form'] = contact_form
            data[url]['Live Chat Solution'] = live_chat
        
        # Append result to results_data for real-time updates
        results_data.append(data[url])
    
    df = pd.DataFrame(data.values())
    df.to_excel('lead_report.xlsx', index=False)

    # Filter for Shopify stores without live chat solutions
    no_live_chat_df = df[(df['Shopify'] == True) & (df['Live Chat Solution'].isna())]
    no_live_chat_df.to_excel('shopify_without_livechat.xlsx', index=False)

    # Ensure static directory exists
    if not os.path.exists('static'):
        os.makedirs('static')

    # Generate pie chart for live chat solution usage
    total_sites = len(df)
    sites_with_live_chat = len(df[df['Live Chat Solution'].notna()])
    sites_without_live_chat = total_sites - sites_with_live_chat

    labels = 'With Live Chat', 'Without Live Chat'
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
    except Exception as e:
        print(f"Error saving pie chart: {e}")
    
    print("Data collection complete. Reports saved to 'lead_report.xlsx' and 'shopify_without_livechat.xlsx'.")
    return df

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        query = request.form['query']
        num_pages = int(request.form['num_pages'])
        return redirect(url_for('results', query=query, num_pages=num_pages))
    return render_template('index.html')

@app.route('/results')
def results():
    query = request.args.get('query')
    num_pages = int(request.args.get('num_pages'))
    scrape_data(query, num_pages)
    return render_template('results.html', query=query)

@app.route('/updates')
def updates():
    return jsonify(results_data)

if __name__ == '__main__':
    app.run(debug=True)
