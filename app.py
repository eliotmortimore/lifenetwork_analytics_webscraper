import asyncio
from playwright.async_api import async_playwright
import os
from datetime import datetime
import json
import csv
import re
import psycopg2


class WebScraperToGoogleSheets:
    def __init__(self, username=None, password=None):
        self.username = username
        self.password = password

    async def login(self, page):
        """Handle login process"""
        try:
            # Fill username field first
            username_selectors = [
                'input[name="username"]',
                'input[name="email"]',
                'input[type="email"]',
                'input[id*="username"]',
                'input[id*="email"]',
                'input[placeholder*="username"]',
                'input[placeholder*="email"]'
            ]
            
            username_field = None
            for selector in username_selectors:
                try:
                    username_field = await page.wait_for_selector(selector, timeout=2000)
                    if username_field:
                        break
                except:
                    continue
            
            if username_field:
                await username_field.fill(self.username)
                print("✅ Filled username")
            else:
                print("❌ Username field not found")
                return False
            
            # Fill password field
            password_selectors = [
                'input[name="password"]',
                'input[type="password"]',
                'input[id*="password"]',
                'input[placeholder*="password"]'
            ]
            
            password_field = None
            for selector in password_selectors:
                try:
                    password_field = await page.wait_for_selector(selector, timeout=2000)
                    if password_field:
                        break
                except:
                    continue
            
            if password_field:
                await password_field.fill(self.password)
                print("✅ Filled password")
            else:
                print("❌ Password field not found")
                return False
            
            # Now look for login button after filling credentials
            login_selectors = [
                'a[href*="login"]',
                'button[class*="login"]',
                'a[class*="login"]',
                '[data-testid="login"]',
                '.login-button',
                '#login-button',
                'a:has-text("Login")',
                'button:has-text("Login")',
                'a:has-text("Sign In")',
                'button:has-text("Sign In")',
                'button[type="submit"]',
                'input[type="submit"]'
            ]
            
            login_button = None
            for selector in login_selectors:
                try:
                    login_button = await page.wait_for_selector(selector, timeout=2000)
                    if login_button:
                        break
                except:
                    continue
            
            if not login_button:
                print("❌ Login button not found")
                return False
            
            # Click the login button after filling credentials
            await login_button.click()
            print("✅ Clicked login button after filling credentials")
            
            # Wait for login to complete
            await page.wait_for_timeout(3000)
            
            # Check if login was successful (look for logout button or user menu)
            logout_indicators = [
                'a[href*="logout"]',
                'button:has-text("Logout")',
                'a:has-text("Logout")',
                '.user-menu',
                '.profile-menu'
            ]
            
            for indicator in logout_indicators:
                try:
                    await page.wait_for_selector(indicator, timeout=2000)
                    print("✅ Login successful!")
                    return True
                except:
                    continue
            
            print("⚠️ Login status unclear - continuing anyway")
            return True
                
        except Exception as e:
            print(f"❌ Login error: {e}")
            return False

    async def scrape_website(self, url):
        """Scrape website using Playwright with optional login"""
        scraped_data = []

        async with async_playwright() as p:
            # Launch browser
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            try:
                # Navigate to website
                await page.goto(url, wait_until="networkidle")
                print(f"🌐 Navigated to {url}")

                # Login if credentials are provided
                if self.username and self.password:
                    print("🔐 Attempting login...")
                    login_success = await self.login(page)
                    if not login_success:
                        print("⚠️ Login failed, continuing without login")
                else:
                    print("ℹ️ No credentials provided, skipping login")

                # Handle GoLife Network admin panel
                if "admin.golifenetwork.com" in url:
                    print("📊 Looking for analytics button in left column...")
                    
                    # Look for analytics button in left sidebar/column
                    analytics_selectors = [
                        'a[href*="analytics"]',
                        'button[class*="analytics"]',
                        'a[class*="analytics"]',
                        '[data-testid="analytics"]',
                        '.analytics-button',
                        '#analytics-button',
                        'a:has-text("Analytics")',
                        'button:has-text("Analytics")',
                        'li:has-text("Analytics")',
                        'nav a:has-text("Analytics")',
                        '.sidebar a:has-text("Analytics")',
                        '.menu a:has-text("Analytics")'
                    ]
                    
                    analytics_button = None
                    for selector in analytics_selectors:
                        try:
                            analytics_button = await page.wait_for_selector(selector, timeout=2000)
                            if analytics_button:
                                break
                        except:
                            continue
                    
                    if analytics_button:
                        print("✅ Found analytics button, clicking...")
                        await analytics_button.click()
                        await page.wait_for_timeout(2000)  # Wait for page to load
                        print("✅ Clicked analytics button")
                        
                        # After clicking analytics button, save full page HTML for inspection
                        html_content = await page.content()
                        with open('analytics_page.html', 'w', encoding='utf-8') as f:
                            f.write(html_content)
                        print('DEBUG: Saved analytics page HTML to analytics_page.html')

                        # Now scrape analytics data
                        title = await page.title()
                        print(f"📄 Current page: {title}")

                        # Extract 'Total Accounts Created'
                        total_accounts = None
                        try:
                            # Try to find the number next to the label
                            total_accounts_label = await page.query_selector('span:has-text("Total Accounts Created")')
                            if total_accounts_label:
                                # Get the next sibling span (the number)
                                total_accounts_value = await total_accounts_label.evaluate('el => el.nextElementSibling && el.nextElementSibling.textContent')
                                print('DEBUG: Total Accounts Created value:', total_accounts_value)
                                if total_accounts_value and total_accounts_value.strip().isdigit():
                                    total_accounts = total_accounts_value.strip()
                            # Fallback: try to find the number in the table 'Total' row under 'Valid Memberships (Active + Trial)'
                            if not total_accounts:
                                table = await page.query_selector('table')
                                if table:
                                    headers = []
                                    header_elems = await table.query_selector_all('thead tr th')
                                    for h in header_elems:
                                        headers.append(await h.inner_text())
                                    rows = await table.query_selector_all('tbody tr')
                                    for row in rows:
                                        cells = await row.query_selector_all('td')
                                        row_data = [await cell.inner_text() for cell in cells]
                                        if row_data and row_data[0].strip().lower() == 'total':
                                            if 'Valid Memberships (Active + Trial)' in headers:
                                                idx = headers.index('Valid Memberships (Active + Trial)')
                                                if idx < len(row_data):
                                                    total_accounts = row_data[idx]
                        except Exception as e:
                            print(f"Error extracting total accounts: {e}")

                        # Extract the metrics table
                        table_data = []
                        headers = []
                        try:
                            table = await page.query_selector('table')
                            if table:
                                # Get headers
                                header_elems = await table.query_selector_all('thead tr th')
                                for h in header_elems:
                                    headers.append(await h.inner_text())
                                # Get rows
                                rows = await table.query_selector_all('tbody tr')
                                for row in rows:
                                    cells = await row.query_selector_all('td')
                                    row_data = [await cell.inner_text() for cell in cells]
                                    # Map each cell to its header
                                    row_dict = {headers[i]: row_data[i] if i < len(row_data) else '' for i in range(len(headers))}
                                    table_data.append(row_dict)
                        except Exception as e:
                            print(f"Error extracting table: {e}")

                        analytics_data = {
                            'page_title': title,
                            'total_accounts': total_accounts,
                            'table_headers': headers if table_data else [],
                            'table_rows': table_data
                        }
                        scraped_data.append(analytics_data)
                        print(f"📊 Extracted analytics: Total Accounts={total_accounts}, Rows={len(table_data)}")
                    else:
                        print("❌ Analytics button not found in left column")
                        scraped_data.append({'error': 'Analytics button not found'})

                # Example: Scraping quotes from quotes.toscrape.com
                elif "quotes.toscrape.com" in url:
                    quotes = await page.query_selector_all('.quote')

                    for quote in quotes:
                        text = await quote.query_selector('.text')
                        author = await quote.query_selector('.author')

                        quote_text = await text.inner_text() if text else ""
                        author_name = await author.inner_text() if author else ""

                        scraped_data.append({
                            'quote': quote_text,
                            'author': author_name
                        })

                # Generic scraping for other websites
                else:
                    # Get page title
                    title = await page.title()

                    # Get all headings
                    headings = await page.query_selector_all('h1, h2, h3')
                    heading_texts = [await h.inner_text() for h in headings]

                    # Get all paragraphs
                    paragraphs = await page.query_selector_all('p')
                    paragraph_texts = [await p.inner_text() for p in paragraphs if await p.inner_text()]

                    scraped_data.append({
                        'title': title,
                        'headings': heading_texts,
                        'paragraphs': paragraph_texts[:10]  # Limit to first 10 paragraphs
                    })

            except Exception as e:
                print(f"Error scraping website: {e}")
                scraped_data.append({'error': str(e)})

            finally:
                await browser.close()

        return scraped_data

    async def run_scraper(self, url):
        """Scrape and print data only"""
        scraped_data = await self.scrape_website(url)
        
        # Print only quotes and authors in a clean format
        if scraped_data and not any('error' in item for item in scraped_data):
            print(f"\nQuotes from {url}:")
            print("-" * 50)
            for item in scraped_data:
                if 'quote' in item and 'author' in item:
                    print(f"Quote: {item['quote']}")
                    print(f"Author: {item['author']}")
                    print()
        else:
            print(f"Error scraping {url}")
        
        return scraped_data


def insert_to_postgres(total_accounts, premium_row):
    conn = psycopg2.connect(dbname='golife_analytics', user=os.getenv('USER'))
    cur = conn.cursor()
    # Insert total accounts
    if total_accounts is not None:
        cur.execute("""
            INSERT INTO total_accounts (total_accounts) VALUES (%s)
        """, (int(total_accounts),))
    # Insert LIFE Premium row
    if premium_row:
        cur.execute("""
            INSERT INTO premium_subscribers (
                valid_memberships, active_memberships, trial_memberships, canceled_memberships, past_due_memberships
            ) VALUES (%s, %s, %s, %s, %s)
        """, (
            int(premium_row.get('Valid Memberships (Active + Trial)', 0) or 0),
            int(premium_row.get('Active Memberships', 0) or 0),
            int(premium_row.get('Trial Memberships', 0) or 0),
            int(premium_row.get('Canceled Memberships', 0) or 0),
            int(premium_row.get('Past-Due Memberships', 0) or 0)
        ))
    conn.commit()
    cur.close()
    conn.close()


# Example usage
async def main():
    # Username and password for login
    username = "test@golifenetwork.com"
    password = "test1234"
    
    scraper = WebScraperToGoogleSheets(username=username, password=password)
    all_data = []

    # Example URLs to scrape
    urls = [
        "https://admin.golifenetwork.com/home",
        # Add more URLs as needed
    ]

    for url in urls:
        try:
            scraped_data = await scraper.scrape_website(url)
            for item in scraped_data:
                if 'total_accounts' in item and 'table_headers' in item and 'table_rows' in item:
                    headers = item['table_headers']
                    premium_headers = [
                        'Package Name',
                        'Valid Memberships (Active + Trial)',
                        'Active Memberships',
                        'Trial Memberships',
                        'Canceled Memberships',
                        'Past-Due Memberships'
                    ]
                    total_row = {h: '' for h in headers}
                    total_row['Package Name'] = 'Total Accounts Created'
                    total_row['type'] = 'total_accounts'
                    total_row['Valid Memberships (Active + Trial)'] = item['total_accounts']
                    premium_rows = []
                    for row in item['table_rows']:
                        row_dict = {h: row.get(h, '') for h in headers}
                        # CHANGED: Save the 'Total' row instead of 'LIFE Premium'
                        if row_dict.get('Package Name', '').strip().lower() == 'total':
                            filtered_row = {h: row_dict.get(h, '') for h in premium_headers}
                            premium_rows.append(filtered_row)
                    # Insert into PostgreSQL
                    premium_row = premium_rows[0] if premium_rows else None
                    insert_to_postgres(item['total_accounts'], premium_row)
        except Exception as e:
            print(f"Error processing {url}: {e}")

    # Remove CSV writing logic
    # if all_data:
    #     timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    #     # Ensure folders exist
    #     os.makedirs('total_accounts', exist_ok=True)
    #     os.makedirs('premium_subscribers', exist_ok=True)
    #     for data in all_data:
    #         headers = data['headers']
    #         # Write total accounts file (only use fields in total_row)
    #         total_csv = f"total_accounts/total_accounts_{timestamp}.csv"
    #         total_headers = list(data['total_row'].keys())
    #         with open(total_csv, 'w', newline='', encoding='utf-8') as csvfile:
    #             writer = csv.DictWriter(csvfile, fieldnames=total_headers)
    #             writer.writeheader()
    #             # Only write fields in total_headers
    #             filtered_total_row = {k: v for k, v in data['total_row'].items() if k in total_headers}
    #             writer.writerow(filtered_total_row)
    #         print(f"✅ Wrote total accounts to {total_csv}")
    #         # Write premium subscribers file (with only the correct columns)
    #         premium_csv = f"premium_subscribers/premium_subscribers_{timestamp}.csv"
    #         with open(premium_csv, 'w', newline='', encoding='utf-8') as csvfile:
    #             writer = csv.DictWriter(csvfile, fieldnames=data['premium_headers'])
    #             writer.writeheader()
    #             for row in data['premium_rows']:
    #                 filtered_row = {k: v for k, v in row.items() if k in data['premium_headers']}
    #                 writer.writerow(filtered_row)
    #         print(f"✅ Wrote premium subscribers to {premium_csv}")
    # else:
    #     print("\n❌ No analytics data found to write to CSV")


# Installation and setup instructions
def print_setup_instructions():
    print("""
    SETUP INSTRUCTIONS:

    1. Install required packages:
       pip install playwright

    2. Install Playwright browsers:
       playwright install chromium

    3. Update the username and password in the main() function

    4. Run the script:
       python app.py
    """)


if __name__ == "__main__":
    print_setup_instructions()
    print("\nStarting scraper...")
    asyncio.run(main())