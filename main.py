from flask import Flask, render_template, redirect, request
from bs4 import BeautifulSoup
import re
import requests
import csv
import random
import time
from difflib import SequenceMatcher  # For optional fuzzy matching (if required)


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64)"
        "AppleWebKit/537.36 (KHTML, like Gecko)"
        "Chrome/44.0.2403.157 Safari/537.36"
    ),
    "Accept-Language": "en-US, en;q=0.5",
}

app = Flask(__name__)


@app.route("/")
def home():

    return render_template("index.html")


@app.route("/home")
def red_home():
    return redirect("/")


@app.route("/start")
def start():
    return render_template("search.html")


@app.route("/search", methods=["POST"])
def search():
    product_name = request.form["product_name"]

    amazon_data = get_min_price_amazon_product(
        search_term=product_name, filename="amazon_products.csv"
    )

    flipkart_data = fetch_flipkart_min_price_product(
        product_name=product_name, target_model=product_name
    )

    return render_template("result.html", amazon=amazon_data, flipkart=flipkart_data)


def fetch_flipkart_min_price_product(
    product_name, target_model, filename="flipkart_products.csv"
):
    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/91.0.4472.124 Safari/537.36"
        ),
        "Accept-Language": "en-US, en;q=0.9,en;q=0.8",
    }

    template = "https://www.flipkart.com/search?q={}&as=on&as-show=on&otracker=AS_Query_HistoryAutoSuggest_1_4_na_na_na&otracker1=AS_Query_HistoryAutoSuggest_1_4_na_na_na&as-pos=1&as-type=HISTORY&suggestionId=mobile+phones&requestId=e625b409-ca2a-456a-b53c-0fdb7618b658&as-backfill=on"
    product_query = product_name.replace(" ", "+")
    url = template.format(product_query)

    response = requests.get(url, headers=HEADERS)
    products = []

    if response.status_code == 200:
        soup = BeautifulSoup(response.text, "lxml")

        titles = soup.find_all("div", {"class": "KzDlHZ"})
        prices = soup.find_all("div", {"class": "Nx9bqj _4b5DiR"})
        ratings = soup.find_all("div", {"class": "XQDdHH"})

        for i in range(min(len(titles), len(prices), len(ratings))):  # type: ignore
            title = titles[i].text.strip()
            if "Add to Compare" in title:
                title = title.split("Add to Compare")[1].strip()
            if target_model.lower() in title.lower():
                product_container = titles[i].find_parent("a")
                product_url = (
                    "https://www.flipkart.com" + product_container["href"]
                    if product_container
                    else "URL not available"
                )
                product = {
                    "title": title,
                    "price": float(
                        prices[i].text.replace("₹", "").replace(",", "").strip()
                    ),
                    "rating": ratings[i].text.strip(),
                    "url": product_url,
                }
                products.append(product)

    if products:
        with open(filename, mode="w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(
                file, fieldnames=["title", "price", "rating", "url"]
            )
            writer.writeheader()
            for product in products:
                writer.writerow(product)

        min_product = min(products, key=lambda p: p["price"])
        return {
            "name": min_product["title"],
            "price": f"₹{min_product['price']}",
            "rating": min_product["rating"],
            "url": min_product["url"],
        }
    else:
        return {"name": "No products found", "price": 0, "rating": "N/A", "url": "#"}


def get_min_price_amazon_product(search_term, filename="amazon_products.csv"):
    HEADERS_LIST = [
        {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/91.0.4472.124 Safari/537.36"
            ),
            "Accept-Language": "en-US, en;q=0.5",
        },
        {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/91.0.4472.114 Safari/537.36"
            ),
            "Accept-Language": "en-US, en;q=0.5",
        },
    ]

    def generate_amazon_url(name):
        name_encoded = name.replace(" ", "+")
        return f"https://www.amazon.in/s?k={name_encoded}"

    def get_price_as_float(price_text):
        price_text = re.sub(r"[^\d.]", "", price_text)
        return float(price_text) if price_text else None

    def is_relevant_product(title, search_term):
        """
        Ensure the product title contains the search term (case-insensitive).
        Optionally, you could use fuzzy matching here.
        """
        search_term_lower = search_term.lower()
        title_lower = title.lower()

        return search_term_lower in title_lower

    url = generate_amazon_url(search_term)
    headers = random.choice(HEADERS_LIST)
    time.sleep(random.uniform(2, 5))

    html = requests.get(url, headers=headers)

    if html.status_code != 200:
        print("Error fetching the webpage.")
        return None

    soup = BeautifulSoup(html.text, "lxml")
    products = soup.select("div.s-main-slot div.s-result-item")

    all_products = []

    for product in products:
        title = product.select_one("span.a-size-medium.a-color-base.a-text-normal")
        price = product.select_one("span.a-offscreen")

        if title and price:
            title_text = title.text.strip()
            if is_relevant_product(title_text, search_term):
                price_float = get_price_as_float(price.text)
                rating = product.select_one("span.a-icon-alt")
                product_link = product.select_one("a.a-link-normal.s-no-outline")

                product_details = {
                    "title": title_text,
                    "price": price.text.strip(),
                    "price_float": price_float,
                    "rating": rating.text.strip() if rating else "Rating not found",
                    "url": "https://www.amazon.in" + product_link["href"] if product_link else "URL not found",  # type: ignore
                }

                all_products.append(product_details)

    if all_products:
        with open(filename, mode="w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            writer.writerow(["Product Name", "Price", "Rating", "Product URL"])
            for product in all_products:
                writer.writerow(
                    [
                        product["title"],
                        product["price"],
                        product["rating"],
                        product["url"],
                    ]
                )
    else:
        print("No products found.")

    min_price_product = min(all_products, key=lambda x: x["price_float"], default=None)

    if min_price_product:
        return {
            "title": min_price_product["title"],
            "price": min_price_product["price"],
            "rating": min_price_product["rating"],
            "url": min_price_product["url"],
        }
    else:
        return {"title": "No products found", "price": 0, "rating": "N/A", "url": "#"}


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0")
