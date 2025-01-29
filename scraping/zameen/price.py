"""Extract the listings from zameen.com 
"""

import re
from typing import List
from collections import deque
import datetime

import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from tqdm import tqdm

from config import CITIES_MAPPING, HOMES_URL, PLOTS_URL, COMMERCIAL_URL, HEADERS


class ScrapeZameenPrice:
    RETRIES = 10

    def __init__(self):
        self.listings = deque()

    def send_request(self, url: str) -> str:
        try:
            retry = Retry(
                total=5,
                backoff_factor=2,
            )
            adapter = HTTPAdapter(max_retries=retry)

            session = requests.Session()
            session.mount("https://", adapter)
            response = session.get(url, timeout=180, headers=HEADERS)
            return response
        except Exception as e:
            print(f"Reqeust failed for {url} with exception {e}")
            return None

    def parse_page(self, response: requests.Response) -> None:
        soup = BeautifulSoup(response.text, "html.parser")
        articles = soup.findAll("li", {"role": "article"})
        data = []
        for article in articles:
            price_text = (
                article.find("span", {"aria-label": "Price"}).get_text().lower()
            )
            price = float(re.findall(r"([\d\.\d]+)", price_text)[0])
            if "crore" in price_text:
                price *= 10000000
            elif "lakh" in price_text:
                price *= 100000
            elif "thousand" in price_text:
                price *= 1000
            else:
                price = None

            article_data = {
                "property_type": response.url.split("/")[-2].replace("s", ""),
                "url": urljoin(response.url, article.find("a").get("href")),
                "price": price,
                "price_text": price_text,
                "title": article.find("h2").get_text(),
                "listing_created": article.find(
                    "span", {"aria-label": "Listing creation date"}
                ).get_text(),
                "listing_updated": article.find(
                    "span", {"aria-label": "Listing updated date"}
                ).get_text(),
                "creation_timestamp": datetime.datetime.now(),
            }
            data.append(article_data)

        print(data)

    def parse_pagination(
        self, response: requests.Response, city: str, id: int
    ) -> List[str]:
        soup = BeautifulSoup(response.text, "html.parser")
        soup.find('span[aria-label="Summary text"]')
        pages_text = soup.find("span", {"aria-label": "Summary text"}).get_text()
        pages = (
            int(re.findall(r"of ([\d,\d]+) ", pages_text)[0].replace(",", "")) // 25
        ) + 2

        for page in range(1, pages):
            if "Plot" in response.url:
                url = PLOTS_URL
            elif "Homes" in response.url:
                url = HOMES_URL
            else:
                url = COMMERCIAL_URL

            url = url.format(city=city, id=id, page=page)
            self.listings.append((url, self.RETRIES))

    def parse_listings(self) -> None:
        print(f"Processing {len(self.listings)} listing urls")

        pbar = tqdm(total=len(self.listings))
        while self.listings:
            pbar.update(1)
            url, retry = self.listings.popleft()
            response = self.send_request(url)
            if response is None:
                if retry > 0:
                    self.listings.append((url, retry - 1))
                    pbar.update(-1)
                else:
                    print(f"Reqeust failed for {url}, Max retries reached.")
            else:
                self.parse_page(response)

    def process_city(self, city: str, id: int) -> None:
        homes_url = HOMES_URL.format(city=city, id=id, page=1)
        plots_url = PLOTS_URL.format(city=city, id=id, page=1)
        commercial_url = COMMERCIAL_URL.format(city=city, id=id, page=1)

        homes_response = self.send_request(homes_url)
        plots_response = self.send_request(plots_url)
        commercial_response = self.send_request(commercial_url)

        self.parse_pagination(homes_response, city, id)
        self.parse_pagination(plots_response, city, id)
        self.parse_pagination(commercial_response, city, id)
        self.parse_listings()

    def run(self) -> None:
        for city, id in CITIES_MAPPING.items():
            self.process_city(city=city, id=id)


def main():
    scraper = ScrapeZameenPrice()
    scraper.run()


if __name__ == "__main__":
    main()
