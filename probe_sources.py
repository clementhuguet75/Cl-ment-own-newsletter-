import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse

urls = {
 "ISW Research": "https://understandingwar.org/research/",
 "ISW WWW": "https://www.understandingwar.org/",
 "Feeder": "https://feeder.co/discover/fbbae6245c/understandingwar-org",
 "Google news": "https://news.google.com/rss/search?q=site%3Aunderstandingwar.org%2Fresearch%2F&hl=en-US&gl=US&ceid=US%3Aen",
 "Bing news": "https://www.bing.com/news/search?q=site%3Aunderstandingwar.org%2Fresearch%2F&format=rss",
 "RSS Bridge": "https://rss-bridge.org/bridge01/?action=display&bridge=InstituteForTheStudyOfWarBridge&searchURL=https%3A%2F%2Funderstandingwar.org%2Fresearch%2F&limit=5&format=Atom",
}
for name,url in urls.items():
 try:
  resp=requests.get(url,timeout=13,headers={"User-Agent":"Mozilla/5.0"})
  soup=BeautifulSoup(resp.text,"html.parser")
  isw_links=[(a.get_text(" ",strip=True)[:80],a.get("href")) for a in soup.select("a[href]") if ("understandingwar.org/research/" in a.get("href","") or "/research/" in a.get("href",""))]
  print(name,resp.status_code,resp.url[:120],"bytes",len(resp.content),"ISW LINKS",len(isw_links),isw_links[:3])
  print("Preview", " ".join(soup.get_text(" ",strip=True).split())[:130])
 except requests.RequestException as exc:
  print(name,type(exc).__name__,str(exc)[:130])
