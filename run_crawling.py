from main.settings import DATA_HOOVERS_REVENUE_AT_LEAST_70M
from main.crawler import run_crawling

run_crawling(file=DATA_HOOVERS_REVENUE_AT_LEAST_70M,
             range=(0, 100))
