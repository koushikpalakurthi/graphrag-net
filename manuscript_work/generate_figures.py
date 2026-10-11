from PIL import Image, ImageDraw, ImageFont
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "figures"
OUT.mkdir(exist_ok=True)
W, H = 1800, 1080
NAVY="#17324D"; BLUE="#2878B5"; TEAL="#168C8C"; GOLD="#D99225"; RED="#B94B4B"; INK="#203040"; MUTED="#607080"; BG="#F3F6F9"; WHITE="#FFFFFF"; LINE="#B7C5D1"; PALE="#E7EEF4"
FONT="C:/Windows/Fonts/arial.ttf"; BOLD="C:/Windows/Fonts/arialbd.ttf"
def f(sz,b=False): return ImageFont.truetype(BOLD if b else FONT,sz)
def canvas(title, subtitle=""):
 im=Image.new('RGB',(W,H),BG); d=ImageDraw.Draw(im)
 d.rounded_rectangle((34,28,W-34,H-30),radius=28,fill=WHITE,outline="#D9E2EA",width=2)
 d.text((72,55),title,font=f(37,True),fill=NAVY)
 if subtitle: d.text((74,108),subtitle,font=f(21),fill=MUTED)
 d.line((72,150,W-72,150),fill="#D9E2EA",width=2)
 return im,d
def textcenter(d,box,s,sz=22,color=INK,bold=False):
 x1,y1,x2,y2=box; font=f(sz,bold); maxw=x2-x1-28; lines=[]
 for para in s.split("\n"):
  line=""
  for word in para.split():
   candidate=(line+" "+word).strip()
   if line and font.getlength(candidate)>maxw: lines.append(line); line=word
   else: line=candidate
  lines.append(line)
 s="\n".join(lines); bb=d.multiline_textbbox((0,0),s,font=font,spacing=5,align='center'); d.multiline_text(((x1+x2-(bb[2]-bb[0]))/2,(y1+y2-(bb[3]-bb[1]))/2),s,font=font,fill=color,spacing=5,align='center')
def box(d,xy,s,fill=PALE,stroke=LINE,sz=21,color=INK,bold=False,r=18):
 d.rounded_rectangle(xy,radius=r,fill=fill,outline=stroke,width=3); textcenter(d,xy,s,sz,color,bold)
def arrow(d,a,b,color=BLUE,width=5,label=None):
 import math
 d.line((a,b),fill=color,width=width); ang=math.atan2(b[1]-a[1],b[0]-a[0]); L=16
 pts=[b,(b[0]-L*math.cos(ang-.5),b[1]-L*math.sin(ang-.5)),(b[0]-L*math.cos(ang+.5),b[1]-L*math.sin(ang+.5))]; d.polygon(pts,fill=color)
 if label: d.text(((a[0]+b[0])//2,(a[1]+b[1])//2-26),label,font=f(16,True),fill=color)
def footer(d,s): d.text((75,H-82),s,font=f(17),fill=MUTED)
def save(im,name): im.save(OUT/name,dpi=(220,220),optimize=True)

# 4.1 end-to-end
im,d=canvas("Figure 4.1  |  End-to-End System Architecture","GraphRAG-Net • CTI ingestion, graph learning, evidence retrieval, answer scoring")
xs=[75,415,755,1095,1435]; width=285; y1,y2=270,500
labels=["Knowledge sources\nATT&CK / STIX\nCVE • CWE • CAPEC\nAdvisories", "Structured extraction\nSchema constrained LLM\nJSON validation\nSource provenance", "Entity resolution\nExact ID → fuzzy match\nReview queue\nTyped CTI graph", "Graph learning\nHeterogeneous GraphSAGE\n64-D embeddings\nLink scoring", "Query answering\nLexical + graph retrieval\nEvidence ranking\nAnswer / abstain"]
colors=["#EAF2F8","#EAF2F8","#E9F5F3","#EAF2F8","#FFF3DF"]
for x,l,c in zip(xs,labels,colors): box(d,(x,y1,x+width,y2),l,c,sz=20,bold=True)
for x in xs[:-1]: arrow(d,(x+width+8,385),(x+width+48,385))
box(d,(450,630,1350,805),"Confidence scoring • 9 retrieval / evidence features\nLogistic or Gradient Boosting → sigmoid calibration → ranked confidence", "#F0ECF8", "#9B86B8",sz=23,bold=True)
arrow(d,(1578,510),(1300,620),TEAL); arrow(d,(580,505),(650,620),TEAL)
box(d,(550,850,1250,932),"Current labels are proxy-derived; calibration is a development diagnostic, not independent validation.","#FFF0EF",RED,sz=18,color=RED)
footer(d,"Data sources and processing stages reflect the repository implementation. Human review is retained for ambiguous entity matches.")
save(im,"Figure_4_1_System_Architecture.png")

# 4.2 extraction
im,d=canvas("Figure 4.2  |  Schema-Constrained Extraction and Entity Disambiguation","Advisory text is converted to validated typed triplets, then aligned against the graph")
box(d,(85,325,325,500),"Threat\nadvisory text", "#EAF2F8",sz=24,bold=True)
box(d,(410,285,730,535),"LLM extraction\nJSON / schema mode\nEntity + relation fields\nSource evidence", "#EAF2F8",BLUE,sz=23,bold=True)
box(d,(810,325,1085,500),"Validate\nrequired fields • types\nreferences • provenance", "#E9F5F3",TEAL,sz=21,bold=True)
arrow(d,(330,410),(400,410)); arrow(d,(735,410),(800,410))
box(d,(1190,230,1680,370),"Tier 1 • Exact identifier\nKnown ID → reuse existing node", "#E9F5F3",TEAL,sz=21,bold=True)
box(d,(1190,420,1680,585),"Tier 2 • Fuzzy same-type match\n≥97% auto-merge\n88–96% flagged for review", "#FFF3DF",GOLD,sz=21,bold=True)
box(d,(1190,635,1680,775),"Tier 3 • Below threshold\nCreate a new entity node", "#FCEEEE",RED,sz=21,bold=True)
arrow(d,(1090,410),(1175,300)); arrow(d,(1090,410),(1175,500)); arrow(d,(1090,410),(1175,700))
box(d,(570,700,1035,835),"Persist resolved nodes / edges\nPreserve source and review status", "#EAF2F8",BLUE,sz=22,bold=True)
arrow(d,(1435,375),(1035,730),TEAL); arrow(d,(1435,590),(1035,755),GOLD); arrow(d,(1435,780),(1035,790),RED)
footer(d,"Repository behavior: the 88–96% band is flagged, but is not automatically merged; lower scores create a new node.")
save(im,"Figure_4_2_Extraction_Disambiguation.png")

# 4.3 GraphSAGE
im,d=canvas("Figure 4.3  |  Heterogeneous GraphSAGE and Link Prediction","Typed entities exchange relation-specific messages; a decoder scores candidate links")
nodes=[(200,300,"Threat\nGroup",BLUE),(500,240,"Technique",TEAL),(500,430,"Software",GOLD),(800,330,"Campaign",RED),(1100,230,"CVE",BLUE),(1100,440,"Mitigation",TEAL)]
for x,y,l,c in nodes: d.ellipse((x,y,x+175,y+105),fill=c,outline=WHITE,width=4); textcenter(d,(x,y,x+175,y+105),l,22,WHITE,True)
arrow(d,(375,340),(495,290),BLUE,label="USES"); arrow(d,(375,360),(495,465),GOLD,label="USES"); arrow(d,(675,290),(795,360),TEAL,label="ATTRIBUTED"); arrow(d,(975,360),(1095,280),RED,label="AFFECTS"); arrow(d,(975,390),(1095,470),TEAL,label="MITIGATED_BY")
box(d,(145,650,650,830),"Encoder\n2 relation-aware SAGE layers\n64-dimensional node embeddings", "#EAF2F8",BLUE,sz=23,bold=True)
box(d,(700,650,1195,830),"Training objective\nPositive observed edges + typed corruptions\nDot-product decoder • binary cross entropy", "#E9F5F3",TEAL,sz=22,bold=True)
box(d,(1260,650,1645,830),"Evaluation status\nNo valid held-out Hits@k results\nreported by current pipeline", "#FFF0EF",RED,sz=20,bold=True)
arrow(d,(650,740),(690,740)); arrow(d,(1195,740),(1250,740))
footer(d,"The repository training/evaluation path reuses observed edges; treat link scores as exploratory until a held-out protocol is run.")
save(im,"Figure_4_3_Heterogeneous_GraphSAGE.png")

# 4.4 retrieval
im,d=canvas("Figure 4.4  |  Dual-Channel Reciprocal Rank Fusion Retrieval","Lexical evidence proposes seeds; graph embeddings add structural context")
box(d,(100,375,340,540),"User query", "#EAF2F8",BLUE,sz=25,bold=True)
box(d,(440,225,800,395),"Lexical channel\nBM25 + TF-IDF\nweighted candidate ranking", "#EAF2F8",BLUE,sz=23,bold=True)
box(d,(440,540,800,710),"Graph channel\nAverage seed embeddings\ncosine similarity ranking", "#E9F5F3",TEAL,sz=23,bold=True)
arrow(d,(345,420),(430,315)); arrow(d,(345,475),(430,620))
box(d,(900,330,1210,575),"Reciprocal Rank Fusion\nRRF(k=60)\nΣ 1 / (60 + rank)", "#FFF3DF",GOLD,sz=23,bold=True)
arrow(d,(805,315),(890,390)); arrow(d,(805,620),(890,520))
box(d,(1310,225,1655,395),"Fused evidence\nTop ranked passages / entities", "#EAF2F8",BLUE,sz=22,bold=True)
box(d,(1310,540,1655,710),"Context expansion\nOne-hop subgraph + evidence", "#E9F5F3",TEAL,sz=22,bold=True)
arrow(d,(1215,390),(1300,315)); arrow(d,(1215,520),(1300,620))
footer(d,"The structural channel is seeded from lexical retrieval output; it is not an independent query encoder.")
save(im,"Figure_4_4_Dual_Channel_RRF.png")

# 4.5 scoring
im,d=canvas("Figure 4.5  |  Platt-Calibrated 9-Feature Confidence Scoring","Feature construction → model selection → sigmoid calibration → confidence estimate")
box(d,(75,235,555,710),"Retrieval features (4)\n• top1_score\n• top1_top2_margin\n• n_supporting_paths\n• avg_path_length\n\nEvidence features (3)\n• entity_jaccard\n• evidence_cosine_sim\n• channels_agree\n\nAnswer features (2)\n• self_consistency_score\n• unsupported_claim_ratio", "#EAF2F8",BLUE,sz=21,bold=False)
box(d,(650,290,925,625),"Candidate models\nLogistic Regression\nGradient Boosting\n\nSelect by Brier\nscore on split", "#E9F5F3",TEAL,sz=23,bold=True)
box(d,(1030,290,1295,625),"Platt calibration\nSigmoid mapping\nfrom calibration split", "#FFF3DF",GOLD,sz=23,bold=True)
box(d,(1400,290,1685,625),"Output\nCalibrated score\n+ evidence-ranked\nanswer confidence", "#F0ECF8", "#9B86B8",sz=22,bold=True)
arrow(d,(560,460),(640,460)); arrow(d,(930,460),(1020,460)); arrow(d,(1300,460),(1390,460))
box(d,(485,790,1390,900),"Caution: proxy labels are built using entity_jaccard and evidence_cosine_sim, which are also model inputs. ECE = 0.1285 is not independent calibration evidence.","#FFF0EF",RED,sz=20,color=RED,bold=True)
footer(d,"Feature names follow confidence_scorer/feature_extractor.py; calibration flow follows the repository training scripts.")
save(im,"Figure_4_5_Confidence_Scoring.png")

# 5.1 unavailable metrics comparison matrix
im,d=canvas("Figure 5.1  |  Hits@k Comparison: GNN vs Translation Embeddings","Requested comparison metrics • numeric values unavailable from the current repository evaluation")
cols=["Model","Hits@1","Hits@3","Hits@10"]
x0,y0=155,300; widths=[560,300,300,300]; rowh=150
xx=x0
for label,w in zip(cols,widths):
 d.rounded_rectangle((xx,y0,xx+w-8,y0+105),radius=12,fill=NAVY); textcenter(d,(xx,y0,xx+w-8,y0+105),label,25,WHITE,True); xx+=w
for ri,row in enumerate([["Heterogeneous GraphSAGE","Not measured","Not measured","Not measured"],["Translation embeddings\n(TransE / DistMult baseline)","Not measured","Not measured","Not measured"]]):
 y=y0+125+ri*rowh; xx=x0
 for ci,(label,w) in enumerate(zip(row,widths)):
  fill="#FCEEEE" if ci else "#EAF2F8"; d.rounded_rectangle((xx,y,xx+w-8,y+120),radius=12,fill=fill,outline="#D9E2EA",width=2); textcenter(d,(xx,y,xx+w-8,y+120),label,22,RED if ci else INK,ci>0); xx+=w
box(d,(260,760,1540,895),"No valid held-out candidate-ranking results or translation-embedding baseline artifacts were found. The current evaluator scores on training edges; plotting fabricated Hits@k bars would misstate performance.","#FFF0EF",RED,sz=21,color=RED,bold=True)
footer(d,"Use this figure as an explicit results-availability panel until both models are evaluated with the same held-out split and candidate set.")
save(im,"Figure_5_1_Hits_at_k_Comparison.png")

# 5.2 use repository reliability image framed and caveated
src=Image.open(ROOT/"data/processed/reliability_diagram.png").convert("RGB")
im,d=canvas("Figure 5.2  |  Platt Calibration Reliability Diagram","Repository development diagnostic • reported ECE = 0.1285")
src.thumbnail((1120,700)); im.paste(src,((W-src.width)//2,180))
d=ImageDraw.Draw(im)
box(d,(170,900,1630,980),"Interpret cautiously: labels are constructed from two of the plotted model features (entity overlap and evidence similarity); this is proxy-label performance, not independent calibration validation.","#FFF0EF",RED,sz=18,color=RED,bold=True,r=12)
save(im,"Figure_5_2_Reliability_Diagram.png")

# 5.3 APT28 graph associations
im,d=canvas("Figure 5.3  |  APT28 Threat Graph and Multi-Hop Evidence Paths","Repository-supported entity relationships • technique-to-tactic paths are graph associations")
hub=(90,420,330,590); box(d,hub,"APT28\nG0007",NAVY,NAVY,sz=30,color=WHITE,bold=True)
techs=[("Spearphishing\nAttachment\nT1566.001","Initial Access\nTA0001"),("PowerShell\nT1059.001","Execution\nTA0002"),("OS Credential\nDumping\nT1003","Credential Access\nTA0006"),("Pass the Hash\nT1550.002","Lateral Movement\nTA0008"),("Encrypted Non-C2\nExfiltration\nT1048.002","Exfiltration\nTA0010")]
ys=[180,335,490,645,800]
for (tl,ta),y in zip(techs,ys):
 box(d,(520,y,865,y+112),tl,"#EAF2F8",BLUE,sz=19,bold=True)
 box(d,(1250,y,1620,y+112),ta,"#E9F5F3",TEAL,sz=20,bold=True)
 arrow(d,(335,505),(510,y+56),BLUE,label="USES")
 arrow(d,(875,y+56),(1240,y+56),TEAL,label="PART_OF_TACTIC")
box(d,(620,925,1540,1000),"APT28 → LSASS Memory (T1003.001) → OS Credential Dumping (T1003) → Credential Access (TA0006)","#FFF3DF",GOLD,sz=18,bold=True)
footer(d,"Tactic columns are arranged for readability; the underlying edges do not establish a temporal execution sequence or causal attack chronology.")
save(im,"Figure_5_3_APT28_Threat_Graph.png")

# contact sheet
files=sorted(p for p in OUT.glob("Figure_*.png") if p.name != "Figure_Contact_Sheet.png"); thumbs=[]
for p in files:
 imt=Image.open(p).convert("RGB"); imt.thumbnail((600,360)); thumbs.append((p,imt.copy()))
sheet=Image.new('RGB',(1260,4*410+30),BG); sd=ImageDraw.Draw(sheet)
for i,(p,t) in enumerate(thumbs):
 x=20+(i%2)*620; y=15+(i//2)*410; sheet.paste(t,(x,y)); sd.text((x,y+365),p.stem,font=f(18,True),fill=NAVY)
sheet.save(OUT/"Figure_Contact_Sheet.png",dpi=(150,150))
readme="""GraphRAG-Net figure pack\n\nEight 1800x1080 PNG figures, saved at 220 DPI. Figure 5.1 intentionally reports unavailable Hits@k values because the repository does not contain valid held-out evaluation results or a translation-embedding baseline. Figure 5.2 reproduces the repository reliability diagram and discloses its proxy-label limitation. Figure 5.3 depicts recorded graph associations; it does not claim temporal ordering.\n\nSource inputs: repository scripts and data/processed artifacts.\n"""
(OUT/"README.txt").write_text(readme,encoding="utf-8")
with zipfile.ZipFile(ROOT/"GraphRAG-Net_Figure_Pack.zip","w",zipfile.ZIP_DEFLATED) as z:
 for p in files+[OUT/"Figure_Contact_Sheet.png",OUT/"README.txt"]: z.write(p,p.relative_to(ROOT))
print(f"Wrote {len(files)} figures to {OUT}")
