import requests
from bs4 import BeautifulSoup

# List of websites to check
websites = [
    "https://kulalaland.com",
    "https://pelacase.ca",
    "https://cowboy.com",
    "https://cocofloss.com",
    "https://lootcrate.com",
    "https://www.potgang.co.uk",
    "https://us.dryrobe.com",
    "https://kith.com",
    "https://meowmeowtweet.com",
    "https://rothys.com",
    "https://www.tentree.ca",
    "https://www.givemetap.com",
    "https://www.bioliteenergy.com",
    "https://lucadanni.com"
]

def check_for_shopify_and_chatbot(url):
    try:
        response = requests.get(url)
        response.raise_for_status()
        
        is_shopify = False
        has_chatbot = False
        
        if "myshopify.com" in response.url:
            is_shopify = True
        
        soup = BeautifulSoup(response.text, 'html.parser')
        shopify_indicators = [
            "cdn.shopify.com",
            "shopify.js",
            "shopify.css",
            "shopify-api"
        ]
        
        for script in soup.find_all("script", src=True):
            if any(indicator in script['src'] for indicator in shopify_indicators):
                is_shopify = True
                break
        
        for link in soup.find_all("link", href=True):
            if any(indicator in link['href'] for indicator in shopify_indicators):
                is_shopify = True
                break
        
        chatbot_indicators = ["chatbot", "livechat", "intercom", "drift", "tawk.to", "zendesk chat"]
        for indicator in chatbot_indicators:
            if indicator in response.text.lower():
                has_chatbot = True
                break
        
        if not has_chatbot:
            if soup.find(attrs={"id": "chatbot"}) or soup.find(attrs={"class": "chatbot"}):
                has_chatbot = True
        
        return is_shopify, has_chatbot
    
    except requests.exceptions.RequestException as e:
        print(f"Error checking {url}: {e}")
        return False, False

# Check each website for being a Shopify store and having a chatbot
results = {}
for website in websites:
    is_shopify, has_chatbot = check_for_shopify_and_chatbot(website)
    results[website] = {"is_shopify": is_shopify, "has_chatbot": has_chatbot}
    print(f"{website} - Shopify: {is_shopify}, Chatbot: {has_chatbot}")

# Print the results
print("\nShopify and Chatbot Check Results:")
for website, result in results.items():
    shopify_status = 'Yes' if result['is_shopify'] else 'No'
    chatbot_status = 'Yes' if result['has_chatbot'] else 'No'
    print(f"{website}: Shopify - {shopify_status}, Chatbot - {chatbot_status}")

#Summary of the results
shopify_count = sum(result['is_shopify'] for result in results.values())
chatbot_count = sum(result['has_chatbot'] for result in results.values())
print(f"\nTotal Shopify stores: {shopify_count}")
print(f"Total websites with chatbots: {chatbot_count}")

