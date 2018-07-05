from main.crawler import Crawler
from main.settings import DATA_TOP_2000

crawler = Crawler()
crawler.run_from_file(file=DATA_TOP_2000,
                      rows=(0, 500))
