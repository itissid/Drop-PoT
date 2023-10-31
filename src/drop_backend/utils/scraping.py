#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#export OPENAI_API_KEY=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

import re
import requests
from bs4 import BeautifulSoup # type: ignore

# write a function that can extract text from a list of URLs and returns a text documents per URL
def get_documents(urls: list) -> dict[str, str]:
    """Extract text from a list of URLs and returns a text documents per URL

    Args:
        urls (list): list of URLs

    Returns:
        list: list of text documents
    """
    documents = {}
    headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9',
            # Add more headers if necessary
    }
    for url in urls:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            # Extract the text content from the response
            # soup = BeautifulSoup(response.content, 'html.parser')
            text = extract_text_with_links(response.content)
            # text = soup.get_text()
            # text = re.sub(r'\n{2,}', '\n', text)
            documents[url] = text
        elif response.status_code == 403:
            print(f"403 Forbidden: Access to the webpage is restricted. {response.reason}")
        else:
            print(f"Error: {response.status_code} - Unable to access the webpage.")
    return documents


def extract_text_with_links(html):
    # Create a BeautifulSoup object
    soup = BeautifulSoup(html, 'html.parser')

    # Remove unwanted tags
    unwanted_tags = ['script', 'style']
    for tag in soup.find_all(unwanted_tags):
        tag.decompose()

    # Process specific tags
    for a in soup.find_all('a'):
        text = a.get_text(strip=True)
        href = a.get('href')
        if text and href:
            a.string = f'{text} ({href})'

    for br in soup.find_all('br'):
        br.insert_after('\n')

    for p in soup.find_all('p'):
        p.insert_after('\n\n')
        for child in p.find_all(recursive=False):
            if child.name != 'br':
                child.insert_before(' ')

    for heading in soup.find_all(re.compile('^h[1-6]$')):
        heading.insert_after('\n\n')

    # Extract text
    text = soup.get_text(separator=' ')

    text = re.sub(r'\n+', '\n', text.strip())
    text = re.sub(r'\n\s+', '\n', text.strip())
    # text = re.sub(r'\s+', ' ', text)

    return text
