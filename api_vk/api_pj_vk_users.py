import requests
from datetime import datetime
import pandas as pd

token="5b29b7d85b29b7d85b29b7d8a95815da0e55b295b29b7d8322e3000803cab761540ec78"
idd=10095732
a=[]
k=0
l=1000
url="https://api.vk.com/method/"
v="5.199"

while k<100000:
    params={"group_id":str(idd),"offset":k,"count":l,"fields":"sex,bdate,city","access_token":token,"v":v}
    m=requests.get(f"{url}groups.getMembers",params=params)
    n=m.json()
    if not n or "response" not in n or not n["response"]["items"]:
        break
    b=n["response"]["items"]
    a.extend(b)
    k+=l
    if len(b)<l:
        break
c=[]
for i in a:
    date=i.get("bdate","")
    age=None
    if date:
        try:
            dmy=date.split(".")
            if len(dmy)>=3:
                d,m,y=int(dmy[0]),int(dmy[1]),int(dmy[2])
                if 1900<=y<=datetime.now().year:
                    age=datetime.now().year-y
                    if (datetime.now().month,datetime.now().day)<(m,d):
                        age-=1
                    if age<0:
                        age=None
        except:
            age=None

    sex=i.get("sex",0)
    if sex==1:
        sexx="женский"
    elif sex==2:
        sexx="мужской"
    else:
        sexx="не указан"

    cities=i.get("city",{})
    city=cities.get("title","") if cities else ""

    info={"имя":i.get("first_name",""),"фамилия":i.get("last_name",""),"возраст":age,"пол":sexx,"город":city}
    c.append(info)

df=pd.DataFrame(c)
df.to_csv("pj_users.csv")
