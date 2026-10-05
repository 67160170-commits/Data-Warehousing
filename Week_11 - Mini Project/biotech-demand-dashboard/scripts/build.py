"""สร้างข้อมูลจำลอง + โมเดลพยากรณ์ + ฝังข้อมูลลง dashboard/index.html
รัน: python scripts/build.py  (ใช้เฉพาะ Python มาตรฐาน)"""
import csv, json, random, os
random.seed(11)
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def months(y, m, n):
    out = []
    for _ in range(n):
        out.append(f"{y}-{m:02d}"); m += 1
        if m > 12: m, y = 1, y + 1
    return out
ACT = months(2024, 10, 24); FC = months(2026, 10, 6)
SEAS = [0.92,0.90,0.97,1.00,1.04,1.06,1.05,1.02,1.00,1.03,1.08,1.13]
PRODUCTS = {"Probiotic Powder": (6000,.022), "Enzyme Concentrate": (3200,.016), "Bio-Fertilizer": (4500,.010)}
BOM = {"Probiotic Powder": {"Culture Medium":.30,"Organic Carrier":.50},
       "Enzyme Concentrate": {"Enzyme Substrate":.45,"Culture Medium":.20},
       "Bio-Fertilizer": {"Organic Carrier":.80,"Culture Medium":.10}}
MAT = {"Culture Medium":("kg",14,.7), "Organic Carrier":("kg",30,1.6), "Enzyme Substrate":("kg",21,4.2)}
demand = {p:[round(b*(1+g*t)*SEAS[int(ACT[t][5:])-1]*random.uniform(.94,1.06)) for t in range(24)] for p,(b,g) in PRODUCTS.items()}

def forecast(s, labels, hz):
    n=len(s); mx=(n-1)/2; my=sum(s)/n
    sl=sum((x-mx)*(y-my) for x,y in enumerate(s))/sum((x-mx)**2 for x in range(n)); ic=my-sl*mx
    idx={}
    for t,(y,l) in enumerate(zip(s,labels)): idx.setdefault(int(l[5:]),[]).append(y/(ic+sl*t))
    idx={m:sum(v)/len(v) for m,v in idx.items()}
    err=sum(abs(y-(ic+sl*t)*idx[int(l[5:])]) for t,(y,l) in enumerate(zip(s,labels)))/n
    return [round((ic+sl*(n+i))*idx.get(int(l[5:]),1)) for i,l in enumerate(hz)], err
mape=lambda a,f: sum(abs(x-y)/x for x,y in zip(a,f))/len(a)*100
bt={}; fc={}; err={}
for p,s in demand.items():  # backtest แบบ rolling 1 เดือนล่วงหน้า ย้อนหลัง 6 เดือน
    ai=[]; manual=[]
    for o in range(18,24):
        ai.append(forecast(s[:o],ACT[:o],[ACT[o]])[0][0]); manual.append(round(sum(s[o-3:o])/3))
    bt[p]={"actual":s[18:],"ai":ai,"manual":manual,"mape_ai":round(mape(s[18:],ai),1),"mape_manual":round(mape(s[18:],manual),1)}
    fc[p],err[p]=forecast(s,ACT,FC)
def wcsv(name,head,rows):
    with open(f"{ROOT}/data/{name}","w",newline="",encoding="utf-8") as f:
        w=csv.writer(f); w.writerow(head); w.writerows(rows)
wcsv("demand_history.csv",["month","product","units_ordered"],[[m,p,v] for p,s in demand.items() for m,v in zip(ACT,s)])
wcsv("demand_forecast.csv",["month","product","forecast_units","lower","upper"],[[m,p,v,round(v-1.3*err[p]),round(v+1.3*err[p])] for p in fc for m,v in zip(FC,fc[p])])
wcsv("bom.csv",["product","material","kg_per_unit"],[[p,m,k] for p,d in BOM.items() for m,k in d.items()])
need={m:[0]*6 for m in MAT}
for p,d in BOM.items():
    for m,k in d.items():
        for i in range(6): need[m][i]+=fc[p][i]*k
mats=[]
for m,(u,lt,fac) in MAT.items():
    n1=need[m][0]; stock=round(n1*fac); order=max(0,round(sum(need[m][:2])*1.15-stock)); c=round(stock/n1,1)
    mats.append({"material":m,"unit":u,"lead_days":lt,"need":[round(x) for x in need[m]],"stock":stock,"order":order,"cover":c,
                 "status":"เสี่ยงขาด" if c<1 else ("สต็อกเกิน" if c>3 else "พอดี")})
wcsv("material_plan.csv",["material","unit","lead_time_days","need_next_month","stock_on_hand","months_of_cover","recommended_order","status"],
     [[x["material"],x["unit"],x["lead_days"],x["need"][0],x["stock"],x["cover"],x["order"],x["status"]] for x in mats])
D={"act":ACT,"fc":FC,"demand":demand,"forecast":fc,"bt":bt,"mats":mats,
   "mape_ai":round(sum(v["mape_ai"] for v in bt.values())/3,1),"mape_manual":round(sum(v["mape_manual"] for v in bt.values())/3,1)}
html=open(f"{ROOT}/dashboard/template.html",encoding="utf-8").read().replace("__DATA__",json.dumps(D,ensure_ascii=False))
open(f"{ROOT}/dashboard/index.html","w",encoding="utf-8").write(html)
print(D["mape_ai"],D["mape_manual"],[(m["material"],m["cover"],m["status"],m["order"]) for m in mats])
