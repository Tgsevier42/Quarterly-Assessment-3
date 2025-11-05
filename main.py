# main.py
# 
# This is the main application file.
# It runs all three steps in order:
# 1. Fetches news from GNews
# 2. Summarizes the articles using OpenAI
# 3. Sends the summaries in a formatted email via Gmail

import requests
import smtplib
import ssl
from email.message import EmailMessage
from newspaper import Article
from openai import OpenAI
import config # Our file with API keys and settings

# --- Constants (Easy to change) ---
NEWS_TOPIC = "artificial intelligence"
MAX_ARTICLES = 5

# --- Initialize OpenAI Client ---
# We do this once at the start
try:
    client = OpenAI(api_key=config.OPENAI_API_KEY)
except Exception as e:
    print(f"Error initializing OpenAI client: {e}")
    client = None

# --- Step 1: Fetch the Articles ---
def fetch_news(topic, max_articles):
    """
    Fetches a list of news articles from the GNews API.
    Returns a list of article dictionaries.
    """
    print(f"Fetching {max_articles} articles for '{topic}'...")
    url = (
        "https://gnews.io/api/v4/search?"
        f"q={topic}&"
        f"max={max_articles}&"
        "lang=en&"
        f"apikey={config.GNEWS_API_KEY}"
    )
    
    try:
        response = requests.get(url)
        response.raise_for_status() # Raises an error for bad status codes
        data = response.json()
        return data.get('articles', [])
    except requests.exceptions.RequestException as e:
        print(f"Error fetching news: {e}")
        return []

# --- Step 2: Summarize the Articles ---
def summarize_article(article_url):
    """
    Scrapes the text from a given URL and uses an LLM to summarize it.
    Returns a summary string or None if it fails.
    """
    try:
        # 2a. Scrape the article text
        article = Article(article_url)
        article.download()
        article.parse()
        
        article_text = article.text
        
        # If text is too short, it's likely a paywall or error page
        if len(article_text) < 250:
            print(f"    - Text too short or unreadable, skipping.")
            return None
            
        # 2b. Summarize with LLM
        if not client:
            print("    - OpenAI client not initialized, skipping summary.")
            return None

        completion = client.chat.completions.create(
          model="gpt-3.5-turbo",
          messages=[
            {"role": "system", "content": "You are a helpful assistant. Summarize the following news article for a daily newsletter in 3 concise sentences."},
            {"role": "user", "content": article_text}
          ]
        )
        summary = completion.choices[0].message.content
        return summary
        
    except Exception as e:
        print(f"    - Error summarizing article: {e}")
        return None

# --- Step 3: Send the Email ---
def send_email(summaries_list):
    """
    Formats and sends an email containing the list of summaries.
    """
    print("Formatting and sending email...")
    
    # 3a. Format the email content
    subject = f"Your Daily AI News Update ({len(summaries_list)} stories)"
    
    # Plain text version
    text_body = "Here is your daily news summary:\n\n"
    # HTML version (for nicer formatting)
    html_body = "<html><body><h2>Here is your daily news summary:</h2><ul>"
    
    for item in summaries_list:
        text_body += f"• {item['title']}\n{item['summary']}\nRead more: {item['url']}\n\n"
        html_body += (
            f"<li>"
            f"<strong>{item['title']}</strong><br>"
            f"<p>{item['summary']}</p>"
            f"<a href='{item['url']}'>Read more</a>"
            f"</li><br>"
        )
    
    html_body += "</ul></body></html>"

    # 3b. Create the email message object
    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = config.SENDER_EMAIL
    msg['To'] = config.RECIPIENT_EMAIL
    msg.set_content(text_body) # Set the plain-text body
    msg.add_alternative(html_body, subtype='html') # Set the HTML body

    # 3c. Send the email
    try:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
            server.login(config.SENDER_EMAIL, config.SENDER_APP_PASSWORD)
            server.send_message(msg)
            print(f"Email successfully sent to {config.RECIPIENT_EMAIL}!")
            
    except smtplib.SMTPException as e:
        print(f"Error: Unable to send email. {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

# --- Main application logic ---
def main():
    """
    Runs the entire newsletter generation process.
    """
    articles = fetch_news(NEWS_TOPIC, MAX_ARTICLES)
    
    if not articles:
        print("No articles found. Exiting.")
        return

    summaries_list = []
    print(f"Found {len(articles)} articles. Starting summarization...")
    
    for article in articles:
        title = article['title']
        url = article['url']
        print(f"  Summarizing: {title}")
        
        summary = summarize_article(url)
        
        # Only add the article if the summary was successful
        if summary:
            summaries_list.append({
                "title": title,
                "summary": summary,
                "url": url
            })
        
    if not summaries_list:
        print("No summaries were generated. Exiting.")
        return

    print(f"Successfully generated {len(summaries_list)} summaries.")
    send_email(summaries_list)
    print("Newsletter process complete.")

# This makes the script runnable by typing "python main.py"
if __name__ == "__main__":
    main()