import requests
from bs4 import BeautifulSoup
import re
import time
import pandas as pd
from datetime import datetime

def change_domain(url):
  pattern = r"https://([a-z]+)\.linkedin\.com"
  match = re.search(pattern, url)
  if match:
    converted_url = re.sub(pattern, f"https://www.linkedin.com", url)
    return converted_url

def remove_special_characters(text):
    text = text.replace('\n', ' ')
    text = ' '.join(text.split())
    return text

def get_job_postings(keyword, location, days):
  stop = False
  hrs = days * 86400
  start = 0
  keyword = keyword.replace(' ', '%20')
  location = location.replace(' ', '%20')
  processed_posts = []
  error_pages = []
  while stop!=True:
    pre_url = 'https://linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search?f_TPR=r'+str(hrs)+'&keywords='+keyword+'&location='+location
    final_url= pre_url + '&trk=public_jobs_jobs-search-bar_search-submit&position=1&pageNum=0&start='+str(start)
    if start%100 == 0:
      time.sleep(6)
    r = requests.get(final_url)
    if r.status_code == 200:
      soup = BeautifulSoup(r.content, 'html.parser')
      posts = soup.find_all('li')
      for post in posts:
        try:
          title = remove_special_characters(post.div.find(class_='base-search-card__info').h3.string) if post.div.find(class_='base-search-card__info') != None else ''
          company = remove_special_characters(post.div.find(class_='base-search-card__info').h4.a.string) if post.div.find(class_='base-search-card__info') != None else ''
          url = post.div.a['href'] if post.div != None else ''
          fetched_location = remove_special_characters(post.div.find(class_='job-search-card__location').string) if post.div.find(class_='job-search-card__location') != None else ''
          company_url = post.div.find(class_='base-search-card__info').h4.a['href'] if post.div.find(class_='base-search-card__info') != None else ''
          p = {
              'Title':title,
              'Company': company,
              'url':url,
              'Location':fetched_location,
              'company_url':company_url
          }
          processed_posts.append(p)
        except:
          error_pages.append(post)
    else:
      print(r.status_code)
      print('Stopped at page',str(start))
      print(final_url)
      stop = True
    start = start+25
    if start == 100:
      stop = True
  return [pd.DataFrame(processed_posts), error_pages]

"""Function to Fetch Job Posting"""

def get_job_description(url):
  rms = remove_special_characters
  r = requests.get(url)
  job_desciption = {}
  if r.status_code == 200:
    soup = BeautifulSoup(r.content, 'html.parser')
    try:
      if soup.find('span', class_='posted-time-ago__text') != None:
        job_desciption['posted'] = rms(soup.find('span', class_='posted-time-ago__text').string)
      if soup.find('figcaption', class_='num-applicants__caption') != None:
        job_desciption['applicants'] = rms(soup.find('figcaption', class_='num-applicants__caption').string)
      if soup.find('span', class_='num-applicants__caption') != None:
        job_desciption['applicants'] = rms(soup.find('span', class_='num-applicants__caption').string)
      if soup.find('ul',class_='description__job-criteria-list') != None:
        job_criteria_section = soup.find('ul',class_='description__job-criteria-list')
        job_criteria_list = job_criteria_section.find_all('li')
        extracted_criteria = {}
        for job_criteria in job_criteria_list:
          extracted_criteria[rms(job_criteria.h3.string)] = rms(job_criteria.span.string)
        job_desciption['criteria'] = extracted_criteria
      if soup.find('section',class_="core-section-container") != None:
        description_html = soup.find('section',class_="core-section-container")
        description = soup.find('section',class_="core-section-container").strings
        sentences = []
        for s in description:
          sentences.append(rms(s))
        job_desciption['text_desciption'] = sentences
        job_desciption['html_desciption'] = description_html
    except Exception:
       print(Exception)
       return 'Exception'
  else:
    print('Not 200 for', url)
  return job_desciption

search_keys = ['Software Engineer','Software Developer','Backend Developer', 'Frontend Developer']
locations = ['Ontario, Canada']
postings = pd.DataFrame(columns=['Title', 'Company', 'url', 'Location', 'company_url'])
for search_key in search_keys:
  for location in locations:
    job_postings, error_posts = get_job_postings(search_key, location, 7)
    postings = pd.concat([postings, job_postings], ignore_index=True)

postings.to_csv('se_postings.csv')
postings = pd.read_csv('se_postings.csv')

"""Extracting list from saved file"""

postings['url'] = postings.apply(lambda x: x.url.split('?')[0], axis=1)

postings['id'] = postings.apply(lambda x: x.url.split('-')[len(x.url.split('-'))-1], axis=1)

postings.drop(columns=['Unnamed: 0'], inplace=True)

postings = postings.drop_duplicates(subset=['id'])

"""Exctracting Description"""

criteria_list = ['Employment type','Seniority level', 'Job function', 'Industries']
postings_with_description = postings.copy()
postings_with_description['description'] = None
for index, row in postings.iterrows():
  url = row['url']
  description = get_job_description(url)
  if len(description.keys())!=0:
    if 'posted' in description:
      postings_with_description.loc[index, 'posted'] = description['posted']
    if 'applicants' in description:
      postings_with_description.loc[index, 'applicants'] = description['applicants']
    if 'criteria' in description:
      for criteria in criteria_list:
        if criteria in description['criteria']:
          postings_with_description.loc[index, criteria]  = description['criteria'][criteria]
    if 'text_desciption' in description:
      list_of_strings = [x for x in description['text_desciption'] if len(x)!= 0]
      description_string = ' '.join(list_of_strings)
      postings_with_description.loc[index, 'Description String']  = description_string
    if 'html_desciption'in description:
      postings_with_description.loc[index, 'html_desciption'] = str(description['html_desciption'])
  if index%5 == 0:
    time.sleep(6)

postings_with_description.to_pickle('ml_job_descriptions.pkl')

postings_with_description['id'] = postings_with_description['id'].astype(int)

print('Finding Missing')

"""Finding Missing"""

count_missing = 0
for index, row in postings_with_description.iterrows():
  url = row['url']
  posted = row['posted']
  if type(posted) != str:
    count_missing = count_missing+1
    converted_url = change_domain(url)
    description = get_job_description(converted_url)
    if len(description.keys())!=0:
      if 'posted' in description:
        postings_with_description.loc[index, 'posted'] = description['posted']
      if 'applicants' in description:
        postings_with_description.loc[index, 'applicants'] = description['applicants']
      if 'criteria' in description:
        for criteria in criteria_list:
          if criteria in description['criteria']:
            postings_with_description.loc[index, criteria]  = description['criteria'][criteria]
      if 'text_desciption' in description:
        list_of_strings = [x for x in description['text_desciption'] if len(x)!= 0]
        description_string = ' '.join(list_of_strings)
        postings_with_description.loc[index, 'Description String']  = description_string
      if count_missing%5 ==0:
        time.sleep(5)
count_missing

"""Counting Missing"""
timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
filename = f"data/scraped_{timestamp}.pkl"
postings_with_description.to_pickle(filename)
print('Saved to File, Script Execution Completed')
