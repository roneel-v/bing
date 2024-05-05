import json
import logging
import random
import time
from datetime import date, timedelta

import requests
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

from src.browser import Browser
from src.utils import Utils


class Searches:
    def __init__(self, browser: Browser):
        self.browser = browser
        self.webdriver = browser.webdriver

    def getGoogleTrends(self, wordsCount: int) -> list:
        # Function to retrieve Google Trends search terms
        searchTerms: list[str] = []
        i = 0
        while len(searchTerms) < wordsCount:
            i += 1
            # Fetching daily trends from Google Trends API
            r = requests.get(
                f'https://trends.google.com/trends/api/dailytrends?hl={self.browser.localeLang}&ed={(date.today() - timedelta(days=i)).strftime("%Y%m%d")}&geo={self.browser.localeGeo}&ns=15'
            )
            trends = json.loads(r.text[6:])
            for topic in trends["default"]["trendingSearchesDays"][0][
                "trendingSearches"
            ]:
                searchTerms.append(topic["title"]["query"].lower())
                searchTerms.extend(
                    relatedTopic["query"].lower()
                    for relatedTopic in topic["relatedQueries"]
                )
            searchTerms = list(set(searchTerms))
        del searchTerms[wordsCount : (len(searchTerms) + 1)]
        return searchTerms

    def getRelatedTerms(self, word: str) -> list:
        # Function to retrieve related terms from Bing API
        try:
            r = requests.get(
                f"https://api.bing.com/osjson.aspx?query={word}",
                headers={"User-agent": self.browser.userAgent},
            )
            return r.json()[1]
        except Exception:  # pylint: disable=broad-except
            return []

    def bingSearches(self, numberOfSearches: int, pointsCounter: int = 0):
        # Function to perform Bing searches
        logging.info(
            f"[BING] Starting {self.browser.browserType.capitalize()} Edge Bing searches..."
        )

        search_terms = self.getGoogleTrends(numberOfSearches)
        self.webdriver.get("https://bing.com")

        i = 0
        attempt = 0
        for word in search_terms:
            i += 1
            logging.info(f"[BING] {i}/{numberOfSearches}")
            points = self.bingSearch(word)
            if points <= pointsCounter:
                relatedTerms = self.getRelatedTerms(word)[:2]
                for term in relatedTerms:
                    points = self.bingSearch(term)
                    if not points <= pointsCounter:
                        break
            if points > 0:
                pointsCounter = points
            else:
                break

            if points <= pointsCounter:
                attempt += 1
                if attempt == 2:
                    logging.warning(
                        "[BING] Possible blockage. Refreshing the page."
                    )
                    self.webdriver.refresh()
                    attempt = 0
        logging.info(
            f"[BING] Finished {self.browser.browserType.capitalize()} Edge Bing searches !"
        )
        return pointsCounter

    def bingSearch(self, word: str):
        # Function to perform a single Bing search
        i = 0

        while True:
            try:
                self.browser.utils.waitUntilClickable(By.ID, "sb_form_q")
                searchbar = self.webdriver.find_element(By.ID, "sb_form_q")
                searchbar.clear()
                searchbar.send_keys(word)
                searchbar.submit()
                time.sleep(Utils.randomSeconds(100, 180))

                # Scroll down after the search (adjust the number of scrolls as needed)
                for _ in range(3):  # Scroll down 3 times
                    self.webdriver.execute_script(
                        "window.scrollTo(0, document.body.scrollHeight);"
                    )
                    time.sleep(
                        Utils.randomSeconds(7, 10)
                    )  # Random wait between scrolls

                return self.browser.utils.getBingAccountPoints()
            except TimeoutException:
                if i == 5:
                    logging.info("[BING] " + "TIMED OUT GETTING NEW PROXY")
                    self.webdriver.proxy = self.browser.giveMeProxy()
                elif i == 10:
                    logging.error(
                        "[BING] "
                        + "Cancelling mobile searches due to too many retries."
                    )
                    return self.browser.utils.getBingAccountPoints()
                self.browser.utils.tryDismissAllMessages()
                logging.error("[BING] " + "Timeout, retrying in 5~ seconds...")
                time.sleep(Utils.randomSeconds(7, 15))
                i += 1
                continue
