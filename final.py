import requests
from time import sleep
from datetime import datetime
from bs4 import BeautifulSoup
import re
import json
from typing import Dict, List
from urllib.parse import quote
import random
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich import print as rprint

console = Console()

class Scraper:
    def __init__(self):
        self.session = requests.Session()
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Pragma': 'no-cache',
            'Cache-Control': 'no-cache'
        }

    def parse_health_status(self, url):
        response = self.session.get(url, headers=self.headers)
        soup = BeautifulSoup(response.text, 'html.parser')
        healthy_servers = []
        rss_enabled_servers = []
        rows = soup.select('#status-tbl tbody tr')
        for row in rows:
            server_name = row.find('td').text.strip()
            healthy_status = row.find_all('td')[2].text.strip()
            rss_status = row.find_all('td')[6].text.strip()
            if '✅' in healthy_status:
                healthy_servers.append(server_name)
            if '✅' in rss_status:
                rss_enabled_servers.append(server_name)
        result = {
            "healthy_servers": healthy_servers,
            "rss_enabled_servers": rss_enabled_servers
        }
        return json.dumps(result, indent=4)

    def InstanceQuery(self):
        url = "https://status.d420.de/"
        json_result = self.parse_health_status(url)
        return json_result

    def InstanceChecker(self, instance: str) -> bool:
        try:
            response = self.session.get(f"{instance}/search?q=test", headers=self.headers, timeout=10)
            soup = BeautifulSoup(response.text, 'html.parser')
            return bool(soup.find('a', class_='tweet-link'))
        except:
            return False

    def parse_tweet_stats(self, stats_div) -> Dict[str, int]:
        stats = {}
        for stat in stats_div.find_all('span', class_='tweet-stat'):
            icon = stat.find('span', class_=lambda x: x and x.startswith('icon-'))
            if icon:
                stat_type = icon['class'][0].replace('icon-', '')
                value_text = stat.get_text(strip=True).replace(',', '') or '0'
                try:
                    value = float(value_text)
                except:
                    value = 0
                stats[stat_type] = value
        return stats

    def parse_tweet_item(self, item) -> Dict:
        tweet_data = {}
        tweet_link = item.find('a', class_='tweet-link')
        if tweet_link:
            tweet_data['link'] = tweet_link['href']
            tweet_data['id'] = tweet_link['href'].split('status/')[1].split('#')[0]
        
        retweet_header = item.find('div', class_='retweet-header')
        if retweet_header:
            tweet_data['is_retweet'] = True
            tweet_data['retweeted_by'] = retweet_header.get_text(strip=True).replace(' retweeted', '')
        else:
            tweet_data['is_retweet'] = False
        
        tweet_header = item.find('div', class_='tweet-header')
        if tweet_header:
            tweet_data['author'] = {
                'username': tweet_header.find('a', class_='username').get_text(strip=True),
                'fullname': tweet_header.find('a', class_='fullname').get_text(strip=True),
                'avatar': tweet_header.find('img', class_='avatar')['src'] if tweet_header.find('img', class_='avatar') else None
            }
        
        content_div = item.find('div', class_='tweet-content')
        if content_div:
            tweet_data['content'] = content_div.get_text(strip=True)
            tweet_data['mentions'] = [a.get_text(strip=True) for a in content_div.find_all('a', href=lambda x: x and not x.startswith(('http', '/search')))]
            tweet_data['hashtags'] = [a.get_text(strip=True) for a in content_div.find_all('a', href=lambda x: x and x.startswith('/search?q=%23'))]
            tweet_data['links'] = [a['href'] for a in content_div.find_all('a', href=lambda x: x and x.startswith(('http', 'https')))]
        
        stats_div = item.find('div', class_='tweet-stats')
        if stats_div:
            tweet_data['stats'] = self.parse_tweet_stats(stats_div)
        
        date_elem = item.find('span', class_='tweet-date')
        if date_elem and date_elem.find('a'):
            tweet_data['date'] = date_elem.find('a')['title']
        
        return tweet_data

    def get_next_page_url(self, soup, instance):
        show_more = soup.find('div', class_='show-more')
        if show_more and show_more.find('a'):
            load_more_href = show_more.find('a')['href']
            return f"{instance}/search{load_more_href}"
        return None

    def NitterScrape(self, instance: str, query: str, max_pages: int = 2) -> List[Dict]:
        all_tweets = []
        current_page = 1
        search_url = f"{instance}/search?f=tweets&q={quote(query)}&since=&until=&near="
        current_url = search_url
        
        while current_page <= max_pages:
            response = self.session.get(current_url, headers=self.headers)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            timeline = soup.find_all(class_='timeline')
            if not timeline:
                break
                
            timeline_items = timeline[0].find_all(class_='timeline-item')
            all_tweets.extend([self.parse_tweet_item(item) for item in timeline_items])
            
            next_url = self.get_next_page_url(soup, instance)
            if not next_url or current_page >= max_pages:
                break
                
            current_url = next_url
            current_page += 1
            sleep(1)
            
        return all_tweets
    
    def followerCount(self, query: str):
        endpoint = f"https://lightbrd.com/{query}"
        response = self.session.get(endpoint, headers=self.headers)
        soup = BeautifulSoup(response.text, 'html.parser')
        profile = soup.find('div', class_='profile-card-extra-links')
        if not profile:
            return None  
        followers = profile.find('li', class_='followers')
        if not followers:
            return None  
        match = re.search(r'\d+', followers.text.replace(",", ""))
        return int(match.group()) if match else None

def fetch_new_tokens():
    try:
        endpoint = "https://api.dexscreener.com/token-profiles/latest/v1"
        response = requests.get(endpoint)
        if response.status_code != 200:
            console.print(f"[gray]Failed to fetch token profiles: Status {response.status_code}[/gray]")
            return []
        return [item['tokenAddress'] for item in response.json()]
    except Exception as e:
        console.print(f"[gray]Error fetching token profiles: {str(e)}[/gray]")
        return []

def analyze_token(token):
    try:
        url = f"https://api.rugcheck.xyz/v1/tokens/{token}/report"
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        
        if data.get('score', 0) < 85:
            return {'error': 'Safety score below 85%'}
        if data.get('rugged', False):
            return {'error': 'Potential rug pull detected'}
        if data['token'].get('mintAuthority') is not None:
            return {'error': 'Token is mintable (inflation risk)'}
        if data['token'].get('freezeAuthority') is not None:
            return {'error': 'Token is pausable (trading risk)'}
        
        markets = data.get('markets', [])
        if not markets:
            return {'error': 'No liquidity data available'}
        
        lp_data = markets[0].get('lp', {})
        if lp_data.get('lpLocked', 0) <= 0 or lp_data.get('lpUnlocked', 0) > 0:
            return {'error': 'Liquidity is not properly locked'}
        
        risk_score = data.get('score', 0)
        total_supply = data['token'].get('supply', 0)
        decimals = data['token'].get('decimals', 0)
        top_holders_pct = sum(holder.get('pct', 0) for holder in data.get('topHolders', []))
        total_liquidity = data.get('totalMarketLiquidity', 0)
        transfer_fee = data.get('transferFee', {}).get('pct', 0)
        known_creator = data.get('creator') in data.get('knownAccounts', {})
        
        if total_supply and decimals:
            quote_price = markets[0]['lp'].get('quotePrice', 0)
            market_cap = (total_supply / (10 ** decimals)) * quote_price
        else:
            market_cap = None
            
        liquidity_ratio = (total_liquidity / market_cap) if market_cap else None
        
        return {
            'risk_score': risk_score,
            'market_cap': market_cap,
            'top_holders_pct': top_holders_pct,
            'liquidity_depth': total_liquidity,
            'liquidity_ratio': liquidity_ratio,
            'transfer_fee': transfer_fee,
            'known_creator': known_creator,
            'suggestions': [
                f"Token has safety score of {risk_score}%",
                "Liquidity is properly locked",
                "Token is not mintable (fixed supply)",
                "Token is not pausable"
            ]
        }

    except requests.exceptions.RequestException as e:
        return {'error': f"Request failed: {e}"}
    except KeyError as e:
        return {'error': f"Invalid data format: {e}"}

def main():
    console.print(Panel.fit("Token Analyzer", style="bold blue"))
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        task1 = progress.add_task("[gray]Fetching new tokens...", total=None)
        new_tokens = fetch_new_tokens()
        progress.update(task1, completed=True)
        
        console.print(f"[gray]Found {len(new_tokens)} new tokens[/gray]")
        
        task2 = progress.add_task("[gray]Analyzing tokens...", total=len(new_tokens))
        good_token_json = {}
        good_tokens = []
        
        for token in new_tokens:
            token_data = analyze_token(token)
            if 'error' not in token_data:
                if token_data['risk_score'] <= 400:
                    if token_data['top_holders_pct'] <= 55:
                        if token_data['transfer_fee'] <= 0:
                            good_tokens.append(token)
                            good_token_json[token] = token_data
            progress.update(task2, advance=1)
        
        scraper = Scraper()
        task3 = progress.add_task("[gray]Finding healthy instances...", total=None)
        instances = json.loads(scraper.InstanceQuery())['healthy_servers']
        StaticInstances = ['https://nitter.privacydev.net/', 'https://nitter.poast.org/']
        progress.update(task3, completed=True)
        
        task4 = progress.add_task("[gray]Filtering queryable instances...", total=None)
        instanceURLs = []
        for instance in instances:
            instance = "https://" + instance
            if scraper.InstanceChecker(instance):
                instanceURLs.append(instance)
        for instance in StaticInstances:
            if scraper.InstanceChecker(instance):
                instanceURLs.append(instance)
        progress.update(task4, completed=True)
        
        if instanceURLs:
            instancefinal = random.choice(instanceURLs)
        else:
            instancefinal = random.choice(StaticInstances)
        social_tokens = []
        
        task5 = progress.add_task("[gray]Analyzing social data...", total=len(good_tokens))
        for token in good_tokens:
            tweets = scraper.NitterScrape(instancefinal, token, max_pages=4)
            total_tweets = len(tweets)
            
            users = []
            for tweet in tweets:
                try:
                    usr = tweet['author']['username'].replace("@", "")
                    users.append(usr)
                except:
                    continue
            
            users = list(set(users))
            user_followers = []
            for user in users:
                followers = scraper.followerCount(user)
                if followers:
                    user_followers.append({user: followers})
            
            social_tokens.append({token: user_followers, 'tweets': total_tweets})
            progress.update(task5, advance=1)
    
    table = Table(title="Token Analysis Results", show_lines=True)
    table.add_column("Token", style="cyan")
    table.add_column("Risk Score", justify="right", style="green")
    table.add_column("Market Cap ($)", justify="right", style="yellow")
    table.add_column("Top Holders %", justify="right", style="magenta")
    table.add_column("Liquidity ($)", justify="right", style="blue")
    table.add_column("Tweets", justify="right", style="cyan")
    table.add_column("Known Creator", justify="center", style="green")

    for token in good_tokens:
        data = good_token_json[token]
        social_data = next((item for item in social_tokens if token in item), None)
        tweets = social_data['tweets'] if social_data else 0
        
        table.add_row(
            token[:10] + "...",
            f"{int(data['risk_score'])}%",
            f"${int(data['market_cap'])}" if data['market_cap'] else "N/A",
            f"{int(data['top_holders_pct'])}%",
            f"${int(data['liquidity_depth'])}",
            str(tweets),
            "✓" if data['known_creator'] else "✗"
        )

    console.print("\n")
    console.print(table)
    
    for token in good_tokens:
        data = good_token_json[token]
        console.print(f"\n[bold cyan]Token Details: {token}[/bold cyan]")
        console.print(Panel.fit("\n".join(data['suggestions']), title="Analysis", border_style="blue"))
        
        social_data = next((item for item in social_tokens if token in item), None)
        if social_data:
            user_table = Table(title="Top Social Influencers", show_header=True, header_style="bold magenta")
            user_table.add_column("Username", style="cyan")
            user_table.add_column("Followers", justify="right", style="green")
            
            for user_data in social_data[token]:
                for username, followers in user_data.items():
                    user_table.add_row(username, f"{followers:,}")
            
            console.print(user_table)
    
    console.print("\n[bold green]Analysis Complete![/bold green]")

if __name__ == "__main__":
    main()