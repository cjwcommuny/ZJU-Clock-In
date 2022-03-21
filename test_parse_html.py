import json
import re

from bs4 import BeautifulSoup

if __name__ == '__main__':
    with open('html.html', 'r') as f:
        html = f.read()
        soup = BeautifulSoup(html, 'html.parser')
        soup = BeautifulSoup(soup.prettify(), 'html.parser')
        script_string = soup.find_all('script', type="text/javascript")[-1].string
        info = re.findall(r'var def = (.*})(?=;)', script_string)[0]
        info = json.loads(info)
        print(info)

    # with open('html.html', 'w') as f:
    #     f.write(soup.prettify())
