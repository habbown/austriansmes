from main.crawler import Crawler
from main.settings import DATA_HOOVERS_REVENUE_AT_LEAST_70M

crawler = Crawler()
crawler.run_from_file(file=DATA_HOOVERS_REVENUE_AT_LEAST_70M,
                      rows=(0, 100))
