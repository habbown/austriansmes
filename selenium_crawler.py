# needs a file logindata.p

from bs4 import BeautifulSoup
import locale
import crawler
import pprint
import time
import logindata

locale.setlocale(locale.LC_ALL, '')
from selenium import webdriver

suchwort = "Hallo Asia"
username = logindata.username
password = logindata.password

driver = webdriver.Firefox()  # (executable_path=r"C:\Users\mkoeberl\Documents\geckodriver.exe")
driver.implicitly_wait(10)
driver.get('https://daten.compass.at/sso/login/return?loggedOut=true')
main_window = driver.current_window_handle

kundenkennung_box = driver.find_element_by_name('userDomain')
kundenkennung_box.send_keys("916F8E")

benutzername_box = driver.find_element_by_name('username')
benutzername_box.send_keys(username)

kennwort_box = driver.find_element_by_name('password')
kennwort_box.send_keys(password)

login_button = driver.find_element_by_name('loginSubmit')
login_button.click()

# startseite_button = driver.find_element_by_xpath("//input[@type='submit']")
# startseite_button.click()

driver.get("https://daten.compass.at/FirmenCompass/")
suchwort_box = driver.find_element_by_name('suchwort')
suchwort_box.send_keys(suchwort)

suchen_button = driver.find_element_by_name("suchen")
suchen_button.click()

time.sleep(10)

profile = driver.page_source
profile_soup = BeautifulSoup(profile, 'html.parser')
values = crawler.extract_values_from_profile(profile_soup)

open_abschluesse = driver.find_element_by_xpath("//a[@data-toggle='#toggle-jahresabschluss']")
open_abschluesse.click()

abschluesse_list = driver.find_elements_by_name("erstellen")
for abschluss_link in abschluesse_list:
    abschluss_link.click()
    new_window = [window for window in driver.window_handles if window != main_window][0]
    driver.switch_to.window(new_window)
    time.sleep(5)
    abschluss = driver.page_source
    abschluss_soup = BeautifulSoup(abschluss, 'html.parser')
    values1 = crawler.extract_values_from_bilanz(abschluss_soup)
    values.update(values1)
    driver.close()
    driver.switch_to.window(main_window)

pprint.pprint(values)
