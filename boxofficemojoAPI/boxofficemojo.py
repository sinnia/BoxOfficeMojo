__author__ = 'rastko'

import bs4
import re
import requests
import movie
import utils
import csv
import time
import datetime


class BoxOfficeMojo(object):
    """API client object for interacting with BoxOfficeMojo website"""

    BOMURL = "http://www.boxofficemojo.com/movies"

    def __init__(self):
        self.movie_urls = {}
        self.movie_info = {}
        self.total_movies = 0
        self.letters = ['NUM'] # Movies that start with numbers and other chars
        for i in range(65, 91):
          self.letters.append(chr(i))

    def find_number_of_pages(self, soup):
        """Returns the number of sub-pages a certain letter will have"""
        pages = soup.findAll(href=re.compile("page"))
        if len(pages) > 0:
            max_page_url = pages[-1]['href']
            max_page = re.findall("\d+", max_page_url)[0]
            return int(max_page)
        else:
            return 1

    def clean_html(self, soup):
        """Get rid of all bold, italic, underline and link tags"""
        invalid_tags = ['b', 'i', 'u', 'nobr', 'font']
        for tag in invalid_tags:
            for match in soup.findAll(tag):
                match.replaceWithChildren()

    def find_info(self, soup):
      """Adds all the specific movie urls to the movie_urls dictionary"""
      urls = soup.findAll(href=re.compile("id="))
      # First URL is an ad for a movie so get rid of it
      del(urls[0])
      
      with open('boxofficemojo.csv', 'a') as csvfile:
        writer = csv.writer(csvfile, delimiter=',',
                            quotechar='"', quoting=csv.QUOTE_NONNUMERIC)
        self.total_movies += len(urls)
        for url in urls:
          try:
            row = url.parent.parent
            # Parse year from last column to disambiguate repeated names
            date_col = row.findAll("td")[6]
            date_url = date_col.find(href=re.compile("date="))
            date_tbd_url = date_col.find(href=re.compile("yr="))
            if date_url != None:       # Link to date
                date = date_url.renderContents()
            elif date_tbd_url != None: # Link to year in the future
                date = str(date_tbd_url).split("=")[4]
            else:                      # No link
                date = date_col.renderContents()
            year_pattern = re.compile('[0-9]{4}')
            year = year_pattern.search(date).group() if year_pattern.search(date) != None else 0
            # Append year to the movie name
            movie_name = url.renderContents().replace('"','') # + ' (' + str(year) + ')'
            suffix = 1
            while movie_name in self.movie_urls.keys():
                movie_name = url.renderContents() + ' (' + str(suffix) + ')'
                suffix += 1
                print("suffix: " + str(suffix))
            # Save movie id, name, year, gross total, gross MX
            ids = re.findall(r'id=((\w|[-(),\':\s.])+).htm', url["href"])
            if len(ids) == 1:
                id = ids[0][0]
                self.movie_urls[id] = movie_name
                genre = self.get_genre(id)
                gross_usa = row.findAll("td")[2].renderContents().replace('*','').replace('$','').replace(',','')
                gross_usa = 0 if gross_usa == "n/a" else float(gross_usa)
                gross_foreign = self.get_gross_foreign(id)
                gross_foreign_all = gross_foreign[0]
                gross_foreign_mx = gross_foreign[1]
                gross_total = gross_usa + gross_foreign_all
                self.movie_info[movie_name] = (id, movie_name, year, genre,
                                               gross_total, gross_foreign_mx,
                                               gross_usa)
                print("saving info: " + movie_name+" -> "+str(self.movie_info[movie_name]))                
                writer.writerow([movie_name, year, genre, gross_total, gross_foreign_mx, gross_usa, id])
          except:
            print("Error parsing movie: " + str(url.renderContents()))
            raise

    def load_movies(self):
        """Gets all the movie urls and puts them in a dictionary"""
        for letter in self.letters:
            time.sleep(5)
            print(str(datetime.datetime.now()) + ' Crawling for URLs starting with: ' + letter)
            url = self.BOMURL + "/alphabetical.htm?letter=" + letter
            r = requests.get(url)
            if r.status_code != 200:
                print("HTTP Status code returned:"+str(r.status_code) + " for url: " + url)
                continue
            soup = bs4.BeautifulSoup(r.content, features="html.parser")
            self.clean_html(soup)
            num_pages = self.find_number_of_pages(soup)
            self.find_info(soup)
            for num in range(2, num_pages+1):
                new_url = url + "&page=" + str(num)
                r = requests.get(new_url)
                if r.status_code != 200:
                    print("HTTP Status code returned:"+str(r.status_code))
                soup = bs4.BeautifulSoup(r.content, features="html.parser")
                self.clean_html(soup)
                self.find_info(soup)
        print(str(datetime.datetime.now()) + ' Finished crawling')
        vals = self.movie_urls.values()
        print([x for i, x in enumerate(vals) if vals.count(x) > 1])

    @utils.catch_connection_error
    def get_gross_foreign(self, url_or_id):
        url = self.BOMURL + "/?page=intl&country=MX&id=" + url_or_id +".htm"
        print("get_gross_foreign url: " + str(url))
        soup = utils.get_soup(url)
        pattern = re.compile(r'Mexico')
        if soup is not None:
            if soup.find(text=pattern):
                gross_obj = movie.Gross(soup).data
                data = (float(gross_obj['Gross To Date Foreign']),
                  float(gross_obj['Gross To Date Country']))
                return data
            else:
                return (0, 0)
        else:
            return (0, 0)
            pass

    @utils.catch_connection_error
    def get_genre(self, url_or_id):
        url = self.BOMURL + "/?id=" + url_or_id +".htm"
        print("get_genre url: " + str(url))
        soup = utils.get_soup(url)
        pattern = re.compile(r'Genre')
        if soup is not None:
            if soup.find(text=pattern):
                movie_obj = movie.Movie(soup).data
                return movie_obj['Genre']
            else:
                return ""
        else:
            return ""
            pass


