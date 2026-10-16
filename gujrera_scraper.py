"""
GujRERA Opportunity Database (v9 — six-API full enrichment)
=============================================================
Phase 1: Listing API
Phase 2: Six detail APIs per project:
  1. alldatabyprojectid          → status, formOneId, formThreeId
  2. getproject-details          → description (BHK info), engineer, architect
  3. getProjectProgressReports   → overall progress score
  4. get-all-view-unit-details   → total units, carpet area range, unit costs
  5. get-project-details-for-qpr → blocks, inventory per block, affordable flag
  6. project-block-progress-dtl  → per-block construction progress

pip install requests pandas openpyxl

Usage:
  python gujrera_scraper.py --district Ahmedabad --details --limit 10  # test
  python gujrera_scraper.py --district Ahmedabad --details              # full
"""
import argparse,json,logging,ssl,time,re
import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.ssl_ import create_urllib3_context

BASE="https://gujrera.gujarat.gov.in"
API={
    "list":    BASE+"/dashboard/get-district-wise-projectlist/{cost}/{scheme}/{fy}/{district}/{type}",
    "basic":   BASE+"/project_reg/public/alldatabyprojectid/{pid}",
    "detail":  BASE+"/project_reg/public/getproject-details/{pid}",
    "progress":BASE+"/project_reg/public/getProjectProgressReports-ByPrjRegId/{pid}",
    "units":   BASE+"/dashboard/get-all-view-unit-details-by-id/{pid}",
    "qpr":     BASE+"/project_reg/public/project-app/get-project-details-for-qpr/{pid}",
    "blocks":  BASE+"/dashboard//project-block-progress-dtl-by-prj-id/{f1id}",
}
DISTRICTS=["Ahmedabad","Vadodara","Surat","Rajkot","Gandhinagar","Bhavnagar","Jamnagar","Junagadh","Others"]
logging.basicConfig(level=logging.INFO,format="%(asctime)s  %(levelname)-8s  %(message)s",datefmt="%H:%M:%S")
log=logging.getLogger("gujrera")

class L(HTTPAdapter):
    def init_poolmanager(self,*a,**k):
        c=create_urllib3_context();c.check_hostname=False;c.verify_mode=ssl.CERT_NONE;c.options|=0x4
        k["ssl_context"]=c;return super().init_poolmanager(*a,**k)

def session():
    import urllib3;urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    s=requests.Session();s.mount("https://",L());s.verify=False
    s.headers.update({"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept":"application/json","Referer":BASE+"/","Origin":BASE})
    s.get(BASE,timeout=15);return s

def get(s,url):
    try:
        r=s.get(url,timeout=30)
        if r.status_code==200:return r.json()
    except:pass
    return None

def listing(s,dist,ptype="Residential",cost="0",fy="all"):
    url=API["list"].format(cost=cost,scheme="0",fy=fy,district=dist,type=ptype)
    r=s.get(url,timeout=60);r.raise_for_status()
    p=r.json().get("data",[]);log.info(f"  {dist}: {len(p)} projects");return p

def enrich(s,projects,delay=0.3,limit=0):
    total=limit if limit else len(projects)
    sub=projects[:total]
    log.info(f"\nPhase 2: Enriching {total} projects (6 APIs each)...")
    ok=0;fail=0
    for i,p in enumerate(sub):
        pid=p.get("projectRegId")or p.get("wfoid")
        if not pid:continue
        if(i+1)%25==0 or i==0:log.info(f"  [{i+1}/{total}]  ok={ok} fail={fail}")

        # 1. Basic (status, form IDs)
        d=get(s,API["basic"].format(pid=pid))
        if d:
            dd=d.get("data",d)
            if isinstance(dd,list)and dd:dd=dd[0]
            if isinstance(dd,dict):
                p["_status"]=dd.get("projectStatus","")
                p["_f1id"]=dd.get("formOneId","")
                p["_f3id"]=dd.get("formThreeId",dd.get("formThreePk",""))
                p["_promoterType"]=dd.get("promoterType","")

        # 2. Project details (description has BHK, engineer, architect)
        d=get(s,API["detail"].format(pid=pid))
        if d:
            dd=d.get("data",{})
            if isinstance(dd,dict):
                pd_obj=dd.get("projectDetail",{})
                if isinstance(pd_obj,dict):
                    p["_desc"]=pd_obj.get("projectDescription",pd_obj.get("projectDesc",""))
                    p["_landArea"]=pd_obj.get("landArea","")
                    p["_openArea"]=pd_obj.get("openArea","")
                    p["_coveredArea"]=pd_obj.get("coveredArea","")
                    p["_planAuthority"]=pd_obj.get("planPassingAuthority",pd_obj.get("planPassAuth",""))
                eng=dd.get("englist",[])
                if eng and isinstance(eng,list):p["_engineer"]=eng[0].get("name","")
                arch=dd.get("acrchlist",[])
                if arch and isinstance(arch,list):p["_architect"]=arch[0].get("name","")

        # 3. Progress score
        d=get(s,API["progress"].format(pid=pid))
        if d:
            dd=d.get("data",{})
            if isinstance(dd,dict):
                p["_progressText"]=dd.get("progress","")
                p["_progressScore"]=dd.get("score","")
                p["_timeElapsed"]=dd.get("timeLaps","")

        # 4. Unit summary (total units, carpet range, cost range)
        d=get(s,API["units"].format(pid=pid))
        if d:
            dd=d.get("data",[])
            if isinstance(dd,list)and dd:dd=dd[0]
            if isinstance(dd,dict):
                p["_totUnits"]=dd.get("totunit","")
                p["_minCarpet"]=dd.get("mincararea","")
                p["_maxCarpet"]=dd.get("maxcararea","")
                p["_avgUnit"]=dd.get("averageunit","")
                p["_totCarpet"]=dd.get("totcararea","")
                p["_minUnitCost"]=dd.get("mincost","")
                p["_maxUnitCost"]=dd.get("maxcost","")

        # 5. QPR details (blocks, inventory counts, affordable)
        d=get(s,API["qpr"].format(pid=pid))
        if d:
            dd=d.get("data",{})
            if isinstance(dd,dict):
                p["_noOfBlocks"]=dd.get("noOfBlocks","")
                p["_affordable"]=dd.get("affordableHousing","")
                inv=dd.get("inventoryCountDetails",[])
                if inv:
                    p["_blockInventory"]="; ".join(f"{b.get('block_name','')}: {b.get('cnt','')}" for b in inv)

        # 6. Block progress (needs formOneId)
        f1id=p.get("_f1id","")
        if f1id:
            d=get(s,API["blocks"].format(f1id=f1id))
            if d:
                dd=d.get("data",[])
                if isinstance(dd,list)and dd:
                    parts=[]
                    for b in dd:
                        parts.append(f"{b.get('blk_name','')}: {b.get('block_progress','')}%")
                    p["_blockProgress"]="; ".join(parts)

        ok+=1
        time.sleep(delay)

    log.info(f"  Done: {ok} enriched, {fail} failed")
    return projects

def extract_bhk(desc):
    if not desc:return""
    m=re.findall(r'(\d+)\s*BHK',str(desc),re.IGNORECASE)
    return", ".join(sorted(set(m)))+" BHK" if m else""

def normalize(projects):
    rows=[]
    for p in projects:
        bhk=extract_bhk(p.get("_desc",""))
        row={
            # Identification
            "project_name":p.get("projectName",""),
            "rera_id":p.get("regNo",""),
            "builder":p.get("promoterName",""),
            "builder_type":p.get("_promoterType",""),
            "address":p.get("project_address",""),
            "district":p.get("districtName",""),
            "description":p.get("_desc",""),

            # Physical
            "project_type":p.get("projectType",""),
            "total_units":p.get("_totUnits",""),
            "num_blocks":p.get("_noOfBlocks",""),
            "block_inventory":p.get("_blockInventory",""),
            "bhk_mix":bhk,
            "min_carpet_sqm":p.get("_minCarpet",""),
            "max_carpet_sqm":p.get("_maxCarpet",""),
            "avg_unit_sqm":p.get("_avgUnit",""),
            "total_carpet_sqm":p.get("_totCarpet",""),
            "land_area_sqm":p.get("_landArea",""),
            "open_area_sqm":p.get("_openArea",""),
            "covered_area_sqm":p.get("_coveredArea",""),
            "affordable_housing":p.get("_affordable",""),

            # Timeline
            "launch_date":p.get("startDate",""),
            "approval_date":p.get("approvedOn",""),
            "original_end_date":p.get("projOrgFDate",""),
            "extended_end_date":p.get("extDate",""),
            "project_status":p.get("_status",p.get("projectStatus","")),
            "progress_text":p.get("_progressText",""),
            "progress_score":p.get("_progressScore",""),
            "time_elapsed_pct":p.get("_timeElapsed",""),
            "block_progress":p.get("_blockProgress",""),

            # Commercial
            "total_project_cost":p.get("projectCost",p.get("total_est_cost_of_proj","")),
            "min_unit_cost":p.get("_minUnitCost",""),
            "max_unit_cost":p.get("_maxUnitCost",""),

            # Contact
            "builder_email":p.get("pmtr_email_id",""),
            "builder_mobile":p.get("pr_mobile_no",""),
            "engineer":p.get("_engineer",""),
            "architect":p.get("_architect",""),
            "plan_authority":p.get("_planAuthority",""),

            # IDs
            "project_reg_id":p.get("projectRegId",""),
        }
        try:
            c=float(str(row["total_project_cost"]).replace(",",""))
            row["cost_in_cr"]=round(c/1e7,2)
        except:row["cost_in_cr"]=""
        try:
            mn=float(row["min_unit_cost"]);mx=float(row["max_unit_cost"])
            row["unit_price_range_lakhs"]=f"{mn/1e5:.1f}L - {mx/1e5:.1f}L"
        except:row["unit_price_range_lakhs"]=""

        rows.append(row)
    return rows

def export(projects,output):
    if not projects:log.warning("Nothing.");return
    df=pd.DataFrame(projects)
    pri=[
        "project_name","rera_id","builder","builder_type","address","district","description",
        "project_type","total_units","num_blocks","block_inventory","bhk_mix",
        "min_carpet_sqm","max_carpet_sqm","avg_unit_sqm","total_carpet_sqm",
        "land_area_sqm","open_area_sqm","covered_area_sqm","affordable_housing",
        "launch_date","approval_date","original_end_date","extended_end_date",
        "project_status","progress_text","progress_score","time_elapsed_pct","block_progress",
        "total_project_cost","cost_in_cr","min_unit_cost","max_unit_cost","unit_price_range_lakhs",
        "builder_email","builder_mobile","engineer","architect","plan_authority","project_reg_id",
    ]
    cols=[c for c in pri if c in df.columns]
    extra=[c for c in df.columns if c not in pri]
    df=df[cols+extra]
    df=df.dropna(axis=1,how="all")
    df=df.loc[:,~(df.astype(str).eq("").all())]

    x=output if output.endswith(".xlsx")else output.rsplit(".",1)[0]+".xlsx"
    df.to_excel(x,index=False,sheet_name="Opportunity Database")
    log.info(f"\nExcel: {x}  ({len(df)} rows, {len(df.columns)} cols)")
    c=x.replace(".xlsx",".csv");df.to_csv(c,index=False,encoding="utf-8-sig");log.info(f"CSV:   {c}")
    j=x.replace(".xlsx",".json")
    with open(j,"w",encoding="utf-8")as f:json.dump(projects,f,ensure_ascii=False,indent=2)
    log.info(f"JSON:  {j}")

    log.info(f"\nField coverage:")
    for col in df.columns[:35]:
        filled=df[col].apply(lambda v:bool(v)and str(v).strip()not in('','nan','None','0','0.0')).sum()
        pct=filled/len(df)*100
        bar='#'*int(pct/5)+'.'*(20-int(pct/5))
        log.info(f"  {col:30s}  [{bar}] {pct:5.1f}%  ({filled})")

def main():
    ap=argparse.ArgumentParser(description="GujRERA v9 — six-API enrichment")
    ap.add_argument("--district",default=None)
    ap.add_argument("--type",default="Residential")
    ap.add_argument("--details",action="store_true")
    ap.add_argument("--output",default="gujrera_opportunity_database.xlsx")
    ap.add_argument("--delay",type=float,default=0.3)
    ap.add_argument("--limit",type=int,default=0)
    args=ap.parse_args()
    log.info("="*60)
    log.info("GujRERA Opportunity Database  v9 (six-API)")
    log.info("="*60)
    log.info(f"District: {args.district or'All'} | Details: {args.details} | Limit: {args.limit or'all'}")
    s_=session()
    dists=[args.district]if args.district else list(DISTRICTS)
    log.info("\nPhase 1: Listings...")
    raw=[]
    for d in dists:
        try:raw.extend(listing(s_,d,args.type));time.sleep(1)
        except Exception as e:log.warning(f"  {d}: {e}");time.sleep(3)
    log.info(f"Phase 1: {len(raw)} projects.")
    if not raw:return
    if args.details:enrich(s_,raw,args.delay,args.limit)
    export(normalize(raw),args.output)
    log.info("\nDone!")

if __name__=="__main__":main()
