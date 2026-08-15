from datetime import datetime,timezone
import os,re,json,requests,pytz
from io import BytesIO
from PIL import Image,ImageDraw,ImageFont
import firebase_admin
from firebase_admin import credentials,db,firestore

TOKEN=os.getenv("TELEGRAM_BOT_TOKEN","")
CHAT_ID=os.getenv("TELEGRAM_CHAT_ID","@bajusrate")
SERVICE=os.path.join(os.path.dirname(os.path.abspath(__file__)),"serviceAccount.json")
URL="https://www.goldr.org/price.js?gttm"
LATEST="bajush_gold_price"; HISTORY="bajush_gold_price_history"

NAME={"২২ ক্যারেট সোনার দাম":"22K","২১ ক্যারেট সোনার দাম":"21K","১৮ ক্যারেট সোনার দাম":"18K","সনাতন পদ্ধতির সোনার দাম":"SAN"}
FS={"২২ ক্যারেট সোনার দাম":"22K","২১ ক্যারেট সোনার দাম":"21K","১৮ ক্যারেট সোনার দাম":"18K","সনাতন পদ্ধতির সোনার দাম":"Sonaton"}
fdb=None

if os.path.exists(SERVICE):
    try:
        firebase_admin.initialize_app(credentials.Certificate(SERVICE),{"databaseURL":"https://cal-by-sss-default-rtdb.asia-southeast1.firebasedatabase.app/"})
        fdb=firestore.client(); print("✅ Firebase Initialized")
    except Exception as e: print("❌ Firebase:",e)

def get_data():
    try:
        r=requests.get(URL,headers={"User-Agent":"Mozilla/5.0"},timeout=10); r.raise_for_status()
        m=re.search(r"GoldrPriceTable_goldData\s*=\s*(\[[\s\S]*?\]);",r.text)
        d=re.search(r'const datetime\s*=\s*"([^"]+)"',r.text)
        if not m: raise Exception("Price format not found")
        return {"goldData":json.loads(m.group(1)),"updateDate":d.group(1).split(" ")[0] if d else datetime.now().strftime("%Y-%m-%d")}
    except Exception as e: print("❌ Data:",e); return None

def old_price():
    if not fdb:return None
    try:
        x=fdb.collection(LATEST).document("latest").get()
        if not x.exists:return None
        g=x.to_dict().get("gold",{})
        return {k:int(g.get(k,0)) for k in ["22K","21K","18K","Sonaton"]}
    except Exception as e: print("❌ Old:",e); return None

def current(data):
    return {FS[x["n"]]:int(float(x.get("bg_raw",0))) for x in data["goldData"] if x.get("n") in FS}

def save(data):
    try:
        p={}
        for x in data["goldData"]:
            n=NAME.get(x["n"],x["n"]); p["TRADITIONAL" if n=="SAN" else n]=str(int(float(x["bg_raw"])))
        tz=pytz.timezone("Asia/Dhaka")
        db.reference("gold_data").set({"last_updated":datetime.now(tz).strftime("%d/%m/%Y, %I:%M %p").lower(),"prices":p,"status":"Live"})
        print("✅ RTDB Updated")
    except Exception as e: print("❌ RTDB:",e)
    if fdb:
        try:
            g={FS[x["n"]]:int(float(x["bg_raw"])) for x in data["goldData"] if x.get("n") in FS}
            now=datetime.now(timezone.utc); payload={"fetchedAt":now,"gold":g}
            fdb.collection(LATEST).document("latest").set(payload)
            fdb.collection(HISTORY).document(now.strftime("%Y-%m-%d_%H-%M-%S-%f")).set(payload)
            print("✅ Firestore Updated")
        except Exception as e: print("❌ Firestore:",e)

def make_image(data):
    img=Image.new("RGBA",(1000,667),(0,0,0,0)); d=ImageDraw.Draw(img)
    paths=["arialbd.ttf","ariblk.ttf","/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]
    f=None
    for p in paths:
        try:f=ImageFont.truetype(p,150);break
        except:pass
    f=f or ImageFont.load_default(); y=5
    for x in data["goldData"]:
        n=NAME.get(x["n"],x["n"])+"-"; price=f'{float(x["bg_raw"]):,.0f}'
        d.text((0,y),n,fill=(255,0,0,255),font=f)
        w=f.getbbox(price)[2]; d.text((1000-w,y),price,fill=(0,230,0,255),font=f); y+=162
    b=BytesIO(); b.name="gold_price.png"; img.save(b,"PNG"); b.seek(0); return b

def message(data):
    m="🔔 *GOLD PRICE UPDATED*\n📅 `"+data["updateDate"]+"`\n\n```\nType   | Per Gram  | Per Vori\n-----------------------------\n"
    for x in data["goldData"]:
        n=NAME.get(x["n"],x["n"]); g=f'{float(x["bg_raw"]):,.0f}'; v=f'{float(x["bv_raw"]):,.0f}'
        m+=f"{n:<7} | {g:>9} | {v:>9} ৳\n"
    return m+"```"

def telegram(msg,img):
    try:
        r=requests.post(f"https://api.telegram.org/bot{TOKEN}/sendPhoto",data={"chat_id":CHAT_ID,"caption":msg,"parse_mode":"Markdown"},files={"photo":("gold_price.png",img,"image/png")},timeout=30)
        r.raise_for_status(); print("✅ Telegram Sent")
    except Exception as e: print("❌ Telegram:",e)

def run():
    data=get_data()
    if not data:return
    old=old_price(); cur=current(data)
    print("Previous:",old); print("Current:",cur)
    save(data)
    if old is not None and old==cur:
        print("ℹ️ No price change"); return
    print("🔔 Price changed")
    img=make_image(data); telegram(message(data),img); img.close()

if __name__=="__main__":run()
