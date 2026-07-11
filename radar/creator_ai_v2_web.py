from __future__ import annotations
from flask import request
from .reference_library import list_reference_runs
from .creator_ai_v2_pipeline import generate_complete_recreation,list_runs
from .roblox_template_compiler_v2 import TEMPLATE_PATH,install_template
def register_creator_ai_v2_routes(app,page,esc):
 @app.route('/creator-ai-v2')
 def home():
  refs=[x for x in list_reference_runs(limit=500) if str(x.get('status') or '')=='ANALYZED']
  cards=''.join(f'<div class="card"><h3>{esc(x.get("source_name",""))}</h3><form method="post" action="/creator-ai-v2/generate"><input type="hidden" name="source_name" value="{esc(x.get("source_name",""))}"><button type="submit">Generate Complete Roblox Recreation</button></form></div>' for x in refs)
  rows=''.join(f'<tr><td>{esc(r.get("source_name",""))}</td><td>{esc(r.get("status",""))}</td><td>{esc(len(r.get("stages") or []))}</td><td>{esc(r.get("error",""))}</td></tr>' for r in list_runs()) or '<tr><td colspan="4">No runs yet.</td></tr>'
  status='READY' if TEMPLATE_PATH.exists() else 'NOT INSTALLED'
  body=f'<h1>Creator AI v2</h1><div class="card"><h2>One-time Roblox template</h2><p><b>Status:</b> {status}</p><form method="post" action="/creator-ai-v2/template" enctype="multipart/form-data"><input type="file" name="template_file" accept=".rbxlx" required><button type="submit">Install Baseplate Template</button></form></div><div class="card"><h2>Unified pipeline</h2><p>Roblox Brain → World Planner → Procedural Environment → Gameplay Compiler → NPC Director → Camera Director → Project Compiler → Validation → Studio</p></div>{cards}<div class="card"><h2>Runs</h2><table><thead><tr><th>Reference</th><th>Status</th><th>Stages</th><th>Error</th></tr></thead><tbody>{rows}</tbody></table></div>'
  return page('Creator AI v2',body,'/creator-ai-v2')
 @app.route('/creator-ai-v2/template',methods=['POST'])
 def template():
  try: path=install_template(request.files['template_file'])
  except Exception as e: return page('Template failed',f'<h1>Template failed</h1><div class="card"><pre>{esc(e)}</pre></div>','/creator-ai-v2'),500
  return page('Template installed',f'<h1>Template installed</h1><div class="card"><span class="path">{esc(path)}</span></div><a class="btn" href="/creator-ai-v2">Continue</a>','/creator-ai-v2')
 @app.route('/creator-ai-v2/generate',methods=['POST'])
 def generate():
  source=str(request.form.get('source_name') or '').strip()
  try: run=generate_complete_recreation(source,True)
  except Exception as e: return page('Generation failed',f'<h1>Generation failed</h1><div class="card"><pre>{esc(e)}</pre></div><a class="btn" href="/creator-ai-v2">Back</a>','/creator-ai-v2'),500
  rows=''.join(f'<tr><td>{esc(s.name)}</td><td>{esc(s.status)}</td><td>{esc(s.message)}</td></tr>' for s in run.stages); compiled=next((s.output for s in run.stages if s.name=='project_compiler'),{})
  return page('Generation complete',f'<h1>Complete Roblox recreation generated</h1><div class="card"><p><b>Status:</b> {esc(run.status)}</p><p><b>Project:</b> <span class="path">{esc(compiled.get("project_dir",""))}</span></p><p><b>Place:</b> <span class="path">{esc(compiled.get("place_path",""))}</span></p></div><div class="card"><table><thead><tr><th>Stage</th><th>Status</th><th>Message</th></tr></thead><tbody>{rows}</tbody></table></div><a class="btn" href="/creator-ai-v2">Back</a>','/creator-ai-v2')
