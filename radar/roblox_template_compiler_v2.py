from __future__ import annotations
import json, os, subprocess, time, uuid, xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass
from pathlib import Path
from .full_video_analyzer import BASE
from .world_planner import WorldPlan
TEMPLATE_DIR=BASE/'assets'/'roblox_templates'; TEMPLATE_PATH=TEMPLATE_DIR/'AIVideoGenBase.rbxlx'; OUTPUT_DIR=BASE/'outputs'/'creator_ai_v2'
@dataclass
class CompileResult:
    project_id:str; source_name:str; place_path:str; project_dir:str; valid:bool; errors:list[str]; warnings:list[str]
class Refs:
    def __init__(self,root): self.used={x.attrib.get('referent','') for x in root.findall('.//Item')}; self.i=0
    def next(self):
        while True:
            self.i+=1; r=f'RBXAI{self.i:X}'
            if r not in self.used: self.used.add(r); return r
def prop(p,t,n,v): x=ET.SubElement(p,t,{'name':n}); x.text=('true' if v else 'false') if t=='bool' else str(v); return x
def vec(p,n,v):
    x=ET.SubElement(p,'Vector3',{'name':n})
    for t,a in zip(('X','Y','Z'),v): ET.SubElement(x,t).text=str(a)
def cf(p,n,v):
    x=ET.SubElement(p,'CoordinateFrame',{'name':n})
    for t,a in zip(('X','Y','Z'),v): ET.SubElement(x,t).text=str(a)
    for t,a in {'R00':1,'R01':0,'R02':0,'R10':0,'R11':1,'R12':0,'R20':0,'R21':0,'R22':1}.items(): ET.SubElement(x,t).text=str(a)
def col(rgb): r,g,b=rgb; return (255<<24)|(int(r)<<16)|(int(g)<<8)|int(b)
def item(parent,refs,cls,name): i=ET.SubElement(parent,'Item',{'class':cls,'referent':refs.next()}); p=ET.SubElement(i,'Properties'); prop(p,'string','Name',name); return i,p
def name(i): x=i.find("./Properties/string[@name='Name']"); return x.text if x is not None and x.text else ''
def svc(root,cls):
    for i in root.findall('./Item'):
        if i.attrib.get('class')==cls:return i
    raise ValueError(f'Template missing service {cls}')
def remove(parent,n):
    for c in list(parent.findall('./Item')):
        if name(c)==n: parent.remove(c)
def part(parent,refs,n,size,pos,rgb,cls='Part'):
    i,p=item(parent,refs,cls,n); prop(p,'bool','Anchored',True); prop(p,'bool','CanCollide',True); cf(p,'CFrame',pos); vec(p,'size',size); prop(p,'Color3uint8','Color3uint8',col(rgb)); prop(p,'token','Material',256); prop(p,'float','Transparency',0); return i
def script(parent,refs,n,source,cls='ModuleScript'): i,p=item(parent,refs,cls,n); prop(p,'bool','Disabled',False); prop(p,'ProtectedString','Source',source); return i
def zone(parent,refs,z):
    cx,cy,cz=z.center; sx,sy,sz=z.size
    if z.kind in {'room','corridor'}:
        part(parent,refs,z.zone_id+'_Floor',(sx,1,sz),(cx,0,cz),(220,225,230)); part(parent,refs,z.zone_id+'_BackWall',(sx,sy,1),(cx,sy/2,cz+sz/2),(180,195,210)); part(parent,refs,z.zone_id+'_LeftWall',(1,sy,sz),(cx-sx/2,sy/2,cz),(180,195,210)); part(parent,refs,z.zone_id+'_RightWall',(1,sy,sz),(cx+sx/2,sy/2,cz),(180,195,210))
    else: part(parent,refs,z.zone_id,(sx,1,sz),(cx,0,cz),(205,210,220))
def add_prop(parent,refs,s):
    t=s.get('type','prop'); x,y,z=s.get('position',[0,1,0]); dims={'hospital_bed':(7,2,3),'reception_desk':(12,4,3),'building':(18,16,22),'accent_platform':(12,1,12)}.get(t,(4,4,4)); rgb={'hospital_bed':(235,235,240),'reception_desk':(100,150,190),'building':(150,165,190),'accent_platform':(70,220,140)}.get(t,(180,180,190)); part(parent,refs,t,dims,(x,y,z),rgb)
def lua_table(data):
    return json.dumps(data,ensure_ascii=False).replace('true','true').replace('false','false').replace('null','nil')
def gameplay_src(plan):
    data=json.dumps(asdict(plan),ensure_ascii=False)
    return f'''local Players=game:GetService("Players")\nlocal M={{}}\nlocal PLAN={data}\nfunction M.Start()\n local p=Players.LocalPlayer; local c=p.Character or p.CharacterAdded:Wait(); local h=c:WaitForChild("Humanoid"); local r=c:WaitForChild("HumanoidRootPart")\n for _,s in ipairs(PLAN.gameplay_specs or {{}}) do\n  if s.action=="walk" then h.WalkSpeed=16; h:MoveTo(r.Position+r.CFrame.LookVector*28) end\n  if s.action=="jump" then task.delay(1.5,function() h.Jump=true end) end\n  if s.action=="grow" then task.delay(2,function() for _,n in ipairs({{"BodyHeightScale","BodyWidthScale","BodyDepthScale","HeadScale"}}) do local v=h:FindFirstChild(n); if v then v.Value=tonumber(s.properties.target_scale) or 2 end end end) end\n end\nend\nreturn M'''
def camera_src(): return '''local Players=game:GetService("Players")\nlocal RunService=game:GetService("RunService")\nlocal M={}\nfunction M.Start() local p=Players.LocalPlayer; local c=p.Character or p.CharacterAdded:Wait(); local r=c:WaitForChild("HumanoidRootPart"); local cam=workspace.CurrentCamera; cam.CameraType=Enum.CameraType.Scriptable; RunService.RenderStepped:Connect(function() if r.Parent then local pos=r.Position-r.CFrame.LookVector*9+Vector3.new(0,3,0); cam.CFrame=CFrame.lookAt(pos,r.Position+Vector3.new(0,2,0)) end end) end\nreturn M'''
def npc_src(plan):
    data=json.dumps(plan.npc_specs,ensure_ascii=False)
    return f'''local Players=game:GetService("Players")\nlocal M={{}}\nlocal SPECS={data}\nfunction M.Start(folder)\n for i,s in ipairs(SPECS) do local model=Instance.new("Model"); model.Name=(s.type or "NPC")..i; model.Parent=folder; local root=Instance.new("Part"); root.Name="HumanoidRootPart"; root.Size=Vector3.new(2,2,1); root.Position=Vector3.new(table.unpack(s.position or {{0,2,20}})); root.Parent=model; local hum=Instance.new("Humanoid"); hum.WalkSpeed=s.speed or 12; hum.Parent=model; model.PrimaryPart=root; if s.behavior=="chase" then task.spawn(function() while model.Parent do task.wait(.25); local p=Players:GetPlayers()[1]; if p and p.Character and p.Character:FindFirstChild("HumanoidRootPart") then hum:MoveTo(p.Character.HumanoidRootPart.Position) end end end) end end\nend\nreturn M'''
def boot(): return '''local RS=game:GetService("ReplicatedStorage")\nlocal pkg=RS:WaitForChild("CreatorAIV2Package")\nrequire(pkg:WaitForChild("GameplayCompiler")).Start()\nrequire(pkg:WaitForChild("CameraDirector")).Start()\nrequire(pkg:WaitForChild("NPCDirector")).Start(workspace:WaitForChild("CreatorAIV2Generated"))'''
def validate(path):
    root=ET.parse(path).getroot(); names={name(i) for i in root.findall('.//Item')}; errors=[f'Missing {n}' for n in ['CreatorAIV2Generated','CreatorAIV2Package','GeneratedScene'] if n not in names]; return {'valid':not errors,'errors':errors,'warnings':[],'size_bytes':path.stat().st_size}
def compile_world(source_name:str,plan:WorldPlan,template_path:str|Path=TEMPLATE_PATH)->CompileResult:
    template=Path(template_path)
    if not template.exists(): raise FileNotFoundError('Upload a blank Baseplate .rbxlx on Creator AI v2 first.')
    tree=ET.parse(template); root=tree.getroot(); refs=Refs(root); workspace=svc(root,'Workspace'); rs=svc(root,'ReplicatedStorage'); sp=svc(root,'StarterPlayer')
    remove(workspace,'CreatorAIV2Generated'); generated,_=item(workspace,refs,'Folder','CreatorAIV2Generated')
    for z in plan.zones: zone(generated,refs,z)
    for p in plan.props: add_prop(generated,refs,p)
    for h in plan.hazards: x,y,z=h.get('position',[0,1,0]); sx,sy,sz=h.get('size',[8,1,8]); part(generated,refs,'KillBlock',(sx,sy,sz),(x,y,z),(255,50,50))
    part(generated,refs,'GeneratedSpawn',(8,1,8),tuple(plan.player_path[0] if plan.player_path else (0,1,0)),(80,220,120),'SpawnLocation')
    remove(rs,'CreatorAIV2Package'); pkg,_=item(rs,refs,'Folder','CreatorAIV2Package'); script(pkg,refs,'GameplayCompiler',gameplay_src(plan)); script(pkg,refs,'CameraDirector',camera_src()); script(pkg,refs,'NPCDirector',npc_src(plan))
    sps=next((c for c in sp.findall('./Item') if c.attrib.get('class')=='StarterPlayerScripts' or name(c)=='StarterPlayerScripts'),None)
    if sps is None:sps,_=item(sp,refs,'StarterPlayerScripts','StarterPlayerScripts')
    remove(sps,'GeneratedScene'); script(sps,refs,'GeneratedScene',boot(),'LocalScript')
    project_id=f'{int(time.time())}_{uuid.uuid4().hex[:8]}'; safe=''.join(c if c.isalnum() or c in '-_' else '_' for c in Path(source_name).stem); project=OUTPUT_DIR/f'{safe}_{project_id}'; project.mkdir(parents=True,exist_ok=True); place=project/'GeneratedGame.rbxlx'; ET.indent(tree,space='  '); tree.write(place,encoding='utf-8',xml_declaration=True); result=validate(place); (project/'world_plan.json').write_text(json.dumps(asdict(plan),indent=2),encoding='utf-8'); (project/'validation.json').write_text(json.dumps(result,indent=2),encoding='utf-8'); return CompileResult(project_id,source_name,str(place),str(project),result['valid'],result['errors'],result['warnings'])
def install_template(upload): TEMPLATE_DIR.mkdir(parents=True,exist_ok=True); upload.save(TEMPLATE_PATH); ET.parse(TEMPLATE_PATH); return TEMPLATE_PATH
def open_place(path):
    p=Path(path)
    if os.name=='nt': os.startfile(str(p))
    else: subprocess.Popen(['xdg-open',str(p)])
