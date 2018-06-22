from main.settings import DATA_HOOVERS_REVENUE_AT_LEAST_70M
from main.crawler import Crawler

crawler = Crawler()
crawler.run_from_file(file=DATA_HOOVERS_REVENUE_AT_LEAST_70M,
                      range=(0, 100))
