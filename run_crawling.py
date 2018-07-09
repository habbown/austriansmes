from main.crawler import Crawler, DBTable
from main.settings import DATA_TOP_2000

crawler = Crawler()
collection_dict = crawler.get_content(file=DATA_TOP_2000,
                                      rows=(0, 800))

table = DBTable()
table.push_from_source(source=collection_dict)
table.close_connection()
