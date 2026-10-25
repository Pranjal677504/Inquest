from pathlib import Path
import os, sys, subprocess, signal, socket, time, json, urllib.request, hashlib, traceback
from playwright.sync_api import sync_playwright, expect
base=Path(__file__).parent
repo=base/'checkout'
py=str(base/'venv/bin/python')
origin='http://127.0.0.1:8000'
report={'candidate':'6eaa02310185c98439e8177beb50540362cadfdd','checks':{}}
proc=None
logs=[]
def save():
 (base/'walkthrough.json').write_text(json.dumps(report,indent=2))
def start(args,label):
 global proc
 with socket.socket() as sock: sock.bind(('127.0.0.1',8000))
 log=(base/(label+'.log')).open('w'); logs.append(log)
 env={k:v for k,v in os.environ.items() if k in ('PATH','HOME','TMPDIR','LANG','LC_ALL','SYSTEMROOT')}
 proc=subprocess.Popen([py,*args],cwd=repo,stdout=log,stderr=subprocess.STDOUT,start_new_session=True,env=env)
 deadline=time.monotonic()+20
 while time.monotonic()<deadline:
  if proc.poll() is not None: raise RuntimeError(label+' exited '+str(proc.returncode))
  try:
   with urllib.request.urlopen(origin+'/api/health',timeout=1) as r:
    if r.status==200: return
  except OSError: time.sleep(.1)
 raise RuntimeError(label+' did not become healthy')
def stop():
 global proc
 if proc is not None:
  os.killpg(proc.pid,signal.SIGINT)
  try: proc.wait(timeout=10)
  except subprocess.TimeoutExpired:
   os.killpg(proc.pid,signal.SIGTERM); proc.wait(timeout=5)
  proc=None
def sample(browser,url,label):
 context=browser.new_context(viewport={'width':1440,'height':1000})
 page=context.new_page(); errors=[]; requests=[]; failed=[]
 page.on('pageerror',lambda e:errors.append(str(e)))
 page.on('request',lambda r:requests.append(r.url))
 page.on('requestfailed',lambda r:failed.append(r.url))
 statuses={}
 for path in ['/','/api/health']:
  r=page.goto(url+path); statuses[path]=r.status; assert r.status==200
 assert page.request.get(url+'/api/health').json()=={'status':'ok'}
 home_external=sorted(set(r for r in requests if not r.startswith(url+'/')))
 requests.clear(); failed.clear()
 r=page.goto(url+'/runs'); statuses['/runs']=r.status; assert r.status==200
 page.get_by_role('button',name='Open sample investigation').click()
 expect(page.locator('#import-status')).to_contain_text('Opened 2 public sample episodes')
 expect(page.locator('#run-policy')).to_have_text('Policy earliest-alert-v1')
 expect(page.locator('#episode-detail')).to_contain_text('Accepted')
 expect(page.locator('#episode-detail .timeline li')).to_have_count(5)
 artifacts=page.evaluate('window.INQUEST_SAMPLE_FILES')
 results=[json.loads(f['content']) for f in artifacts if f['path'].endswith('/result.json')]
 assert [r['score']['success'] for r in results]==[True,False]
 assert all(r['usage']['model_requests']==0 for r in results)
 citation=page.locator('button.citation').first; citation.click()
 expect(page.locator('.timeline li:focus')).to_be_visible()
 page.screenshot(path=str(base/(label+'-accepted.png')),full_page=True)
 page.locator('#episode-list button').nth(1).click()
 expect(page.locator('#episode-detail')).to_contain_text('Reported, not accepted')
 expect(page.locator('#episode-detail .timeline li')).to_have_count(5)
 page.screenshot(path=str(base/(label+'-incorrect.png')),full_page=True)
 for path in ['/investigate','/api/local/config']:
  statuses[path]=page.request.get(url+path).status
  assert statuses[path]==404,(path,statuses[path])
 assert not errors,errors
 assert not failed,failed
 assert all(r.startswith(url+'/') for r in requests),requests
 assert page.evaluate('Object.keys(localStorage).length+Object.keys(sessionStorage).length')==0
 asset=page.request.get(url+'/assets/sample-run.js')
 assert asset.status==200
 assert asset.body()==(repo/'public/assets/sample-run.js').read_bytes()
 report['checks'][label]={'url':url,'home_external_requests':home_external,'http_statuses':statuses,'sample_outcomes':[r['score']['success'] for r in results],'model_requests':0,'page_errors':errors,'failed_requests':failed,'sample_asset_sha256':hashlib.sha256(asset.body()).hexdigest()}
 save(); print('PASS',label,flush=True); context.close()
try:
 with sync_playwright() as p:
  browser=p.chromium.launch()
  report['browser_version']=browser.version
  start(['app.py'],'public-server')
  sample(browser,origin,'local-public')
  stop()
  args=['scripts/serve_local.py','--data-dir',str(base/'jobs')]
  start(args,'local-server')
  context=browser.new_context(viewport={'width':1440,'height':1000}); page=context.new_page(); errors=[]; requests=[]
  page.on('pageerror',lambda e:errors.append(str(e)))
  page.on('request',lambda r:requests.append(r.url))
  page.goto(origin+'/investigate')
  expect(page.locator('#start')).to_be_enabled()
  expect(page.locator('.execution-note')).to_contain_text('not an LLM')
  page.locator('#suite').select_option('authored-v2')
  page.locator('#case').select_option('authored-v2-004')
  page.locator('#budget').select_option('5')
  with page.expect_response(lambda r:r.url.endswith('/api/local/jobs') and r.request.method=='POST') as response:
   page.locator('#start').click()
  assert response.value.status==202
  job=response.value.json(); job_id=job['id']
  expect(page.locator('#job-detail .pill')).to_have_text('completed',timeout=30000)
  expect(page.locator('#job-detail .timeline li')).not_to_have_count(0)
  job_url=page.url
  page.screenshot(path=str(base/'local-job.png'),full_page=True)
  result_path=next((base/'jobs'/job_id/'episodes').glob('*/result.json'))
  before=result_path.read_bytes(); result=json.loads(before)
  assert result['usage']['model_requests']==0
  assert result['score']['steps']<=5
  page.get_by_role('link',name='Open saved result').click()
  expect(page.locator('#import-status')).to_contain_text('Opened 1 planned episodes')
  expect(page.locator('#episode-detail')).to_contain_text('authored-v2-004')
  page.locator('button.citation').first.click()
  expect(page.locator('.timeline li:focus')).to_be_visible()
  page.screenshot(path=str(base/'local-saved-result.png'),full_page=True)
  stop(); start(args,'local-server-restart')
  page.goto(job_url)
  expect(page.locator('#job-detail .pill')).to_have_text('completed',timeout=15000)
  page.get_by_role('link',name='Open saved result').click()
  expect(page.locator('#episode-detail')).to_contain_text('authored-v2-004')
  assert result_path.read_bytes()==before
  assert not errors,errors
  assert all(r.startswith(origin+'/') for r in requests),requests
  assert page.evaluate('Object.keys(localStorage).length+Object.keys(sessionStorage).length')==0
  report['checks']['local-job']={'job_id':job_id,'case':'authored-v2-004','budget':5,'state':'completed','steps':result['score']['steps'],'accepted':result['score']['success'],'model_requests':0,'restart_persisted':True,'result_sha256':hashlib.sha256(before).hexdigest(),'page_errors':errors,'job_url':job_url}
  save(); print('PASS local-job-and-restart',flush=True)
  context.close(); stop()
  sample(browser,'https://inquestbench.vercel.app','hosted-public')
  browser.close()
 report['clean_after']=subprocess.check_output(['git','status','--short'],cwd=repo,text=True).strip()
 assert not report['clean_after']
 report['status']='passed'; save(); print('WALKTHROUGH PASSED',flush=True)
except Exception as e:
 report['status']='failed'; report['error']=str(e); save(); traceback.print_exc(); raise
finally:
 stop()
 for log in logs:log.close()
