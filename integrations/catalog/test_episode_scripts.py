"""Run inside Home Assistant. Every catalog and TV service is mocked."""
import asyncio,copy,os,yaml
from homeassistant.core import HomeAssistant,Context,SupportsResponse
from homeassistant.helpers.script import Script
from homeassistant.helpers import config_validation as cv

URLS={
 'apple': ['https://tv.apple.com/ph/episode/one/umc.cmc.episodeone?showId=umc.cmc.series&playableId=tvs.sbd.4000%3AONE', 'https://tv.apple.com/ph/episode/two/umc.cmc.episodetwo?showId=umc.cmc.series&playableId=tvs.sbd.4000%3ATWO'],
 'hbo': ['https://play.hbomax.com/video/watch/83eca32a-12d2-4e05-8245-e17855c9e390','https://play.hbomax.com/video/watch/94a772a7-28f7-4189-90c4-92e446c175e9'],
 'prime': ['https://app.primevideo.com/detail?gti=amzn1.dv.gti.episode-one','https://app.primevideo.com/detail?gti=amzn1.dv.gti.episode-two']}
ROOTS={'apple':'https://tv.apple.com/ph/show/series/umc.cmc.series','hbo':'https://play.hbomax.com/show/4f6b4985-2dc9-4ab6-ac79-d60f0860b0ac','prime':'https://app.primevideo.com/detail?gti=amzn1.dv.gti.parent-series'}
NAMES={'apple':'play_apple_tv_title','hbo':'play_hbo_title','prime':'play_prime_video_title'}
PACKAGES={'apple':'com.apple.atve.sony.appletv','hbo':'com.wbd.stream','prime':'com.amazon.amazonvideo.livingroom'}
def offer(provider,url):
 return {'service':{'id':provider},'type':'subscription','link':url,'videoLink':url+'&action=play' if provider=='prime' else None}
def show(provider):
 return {'title':'Example','showType':'series','firstAirYear':2022,'streamingOptions':{'ph':[offer(provider,ROOTS[provider])]},'seasons':[{'title':'Season 1','episodes':[{'title':'First','streamingOptions':{'ph':[offer(provider,URLS[provider][0])]}},{'title':'Second','streamingOptions':{'ph':[offer(provider,URLS[provider][1])]}}]}]}
def no_delays(value):
 if isinstance(value,list):return [no_delays(x) for x in value if not(isinstance(x,dict) and 'delay'in x)]
 if isinstance(value,dict):return {k:no_delays(v) for k,v in value.items()}
 return value
async def main():
 hass=HomeAssistant('/tmp/nova-native-episode-tests');raw=yaml.safe_load(open(os.environ.get('NOVA_STREAMING_SCRIPTS_PATH','/config/scripts.yaml')));calls=[];lookups=[];response={};adb_ok=True;stop_ok=True;wake_ok=True;wake_pending=[];apple_result={}
 async def apple_lookup(call):return {'returncode':0,'stdout':__import__('json').dumps(apple_result)}
 hass.services.async_register('shell_command','nova_service_routing',apple_lookup,supports_response=SupportsResponse.ONLY)
 async def lookup(call):lookups.append(dict(call.data));return response
 async def capture(call):
  calls.append((call.domain,dict(call.data)))
  if call.domain=='media_player' and call.service=='turn_on' and wake_ok:
   async def ready():
    await asyncio.sleep(0.01)
    hass.states.async_set('media_player.bravia_xr_55x90l','on')
    hass.states.async_set('remote.sony_xr_55x90l','on')
    hass.states.async_set('media_player.sony_xr_55x90l_2','on')
    hass.states.async_set('media_player.android_tv_10_0_0_174','idle')
   wake_pending.append(asyncio.create_task(ready()))
  if call.domain=='androidtv' and call.data['command'].startswith('am force-stop'):
   hass.states.async_set('media_player.android_tv_10_0_0_174','idle',{'adb_response':'NOVA_EPISODE_STOP_'+call.context.id if stop_ok else 'failed'});return
  if call.domain=='androidtv':hass.states.async_set('media_player.android_tv_10_0_0_174','idle',{'adb_response':('Status: ok\n' if adb_ok else 'Error\n')+'NOVA_EPISODE_'+call.context.id})
 def shorten_waits(v):
  if isinstance(v,list):
   for x in v:shorten_waits(x)
  if isinstance(v,dict):
   if 'wait_template' in v:v['timeout']={'milliseconds':100}
   for x in v.values():shorten_waits(x)
 shorten_waits(raw['play_streaming_episode']['sequence'])
 helper=Script(hass,cv.SCRIPT_SCHEMA(no_delays(raw['play_streaming_episode']['sequence'])),'Native episode','script')
 controls=Script(hass,cv.SCRIPT_SCHEMA(no_delays(raw['streaming_app_profile_and_play']['sequence'])),'Shared playback controls','script')
 async def run_controls(call):await controls.async_run(dict(call.data),call.context)
 hass.services.async_register('script','streaming_app_profile_and_play',run_controls)
 async def native(call):return (await helper.async_run(dict(call.data),call.context)).service_response
 hass.services.async_register('rest_command','netflix_title_search',lookup,supports_response=SupportsResponse.ONLY)
 hass.services.async_register('script','play_streaming_episode',native,supports_response=SupportsResponse.ONLY)
 for domain,service in [('androidtv','adb_command'),('remote','send_command'),('media_player','play_media'),('media_player','turn_on')]:hass.services.async_register(domain,service,capture)
 def awake():
  for entity,state in [('media_player.bravia_xr_55x90l','on'),('remote.sony_xr_55x90l','on'),('media_player.sony_xr_55x90l_2','on'),('media_player.android_tv_10_0_0_174','idle')]:hass.states.async_set(entity,state)
 for provider,name in NAMES.items():
  awake()
  script=Script(hass,cv.SCRIPT_SCHEMA(no_delays(raw[name]['sequence'])),provider+' episode test','script')
  row=show(provider);response={'status':200,'content':[row]}
  async def run(**kw):
   calls.clear();lookups.clear();return (await script.async_run({'query':'Example','season':1,'episode':2,**kw},Context())).service_response
  r=await run();assert r['status']=='playback_requested',r
  assert (r['season'],r['episode'],r['episode_title'])==(1,2,'Second')
  assert r['episode_selection']=='native_deep_link' and r['playback_verified'] is False
  assert lookups[0]['series_granularity']=='episode'
  expected_keys=['HOME','DPAD_CENTER','MEDIA_PLAY' if provider=='apple' else 'DPAD_CENTER']
  assert [d['command'] for domain,d in calls if domain=='remote']==expected_keys,calls
  assert r['profile_play_sequence_sent'] is True
  launch_calls=[d['command'] for domain,d in calls if domain=='androidtv' and d['command'].startswith('am start')]
  assert len(launch_calls)==1,launch_calls
  if provider=='hbo':assert calls[0][1]['command'].startswith('am force-stop com.wbd.stream')
  warm_domains=[domain for domain,_ in calls]
  command=launch_calls[0];expected=URLS[provider][1]+('&action=play' if provider=='prime' else '')
  assert expected in command and PACKAGES[provider] in command
  assert not any(x in command for x in ['DPAD','KEYCODE','MEDIA_PLAY','force-stop','HOME'])
  assert r['tv_ready'] is True and r['wake_requested'] is False
  for entity in ['media_player.bravia_xr_55x90l','remote.sony_xr_55x90l','media_player.sony_xr_55x90l_2','media_player.android_tv_10_0_0_174']:hass.states.async_set(entity,'off')
  r=await run();assert r['status']=='playback_requested' and r['wake_requested'] is True
  assert [domain for domain,_ in calls]==['media_player']+warm_domains,calls
  await asyncio.gather(*wake_pending);wake_pending.clear()
  wake_ok=False
  for entity in ['media_player.bravia_xr_55x90l','remote.sony_xr_55x90l','media_player.sony_xr_55x90l_2','media_player.android_tv_10_0_0_174']:hass.states.async_set(entity,'off')
  r=await run();assert r['status']=='needs_tv_ready' and r['episode_link_sent'] is False
  assert len(calls)==1 and calls[0][0]=='media_player',calls
  awake();hass.states.async_set('media_player.android_tv_10_0_0_174','unavailable')
  r=await run();assert r['status']=='needs_tv_ready' and not calls,r
  wake_ok=True;awake()
  for kw in [{'season':None},{'episode':None},{'season':0},{'episode':True},{'season':1.5},{'season':1000}]:
   r=await run(**kw);assert r['status']=='invalid_episode' and not calls and not lookups,(kw,r)
  for kw in [{'start_playback':False},{'from_start':True}]:
   r=await run(**kw);assert r['status']=='unsupported_request' and not calls and not lookups,(kw,r)
  r=await run(season=1.0,episode=2.0);assert r['status']=='playback_requested'
  response={'status':429,'content':'limited'};r=await run();assert r['status']=='failed' and not calls
  mutations=[]
  q=show(provider);q['showType']='movie';mutations.append((q,'invalid_episode'))
  q=show(provider);q['seasons']=[];mutations.append((q,'episode_metadata_unavailable'))
  q=show(provider);q['seasons'].append(copy.deepcopy(q['seasons'][0]));mutations.append((q,'episode_metadata_unavailable'))
  q=show(provider);q['seasons'][0]['episodes'].pop();mutations.append((q,'episode_metadata_unavailable'))
  q=show(provider);q['seasons'][0]['episodes'][1]='bad metadata';mutations.append((q,'episode_metadata_unavailable'))
  for kind in ['rent','buy','addon']:
   q=show(provider);q['seasons'][0]['episodes'][1]['streamingOptions']['ph'][0]['type']=kind;mutations.append((q,'episode_link_unavailable'))
  q=show(provider);q['seasons'][0]['episodes'][1]['streamingOptions']={};mutations.append((q,'episode_link_unavailable'))
  q=show(provider);q['seasons'][0]['episodes'][1]['streamingOptions']['us']=q['seasons'][0]['episodes'][1]['streamingOptions'].pop('ph');mutations.append((q,'episode_link_unavailable'))
  q=show(provider);q['seasons'][0]['episodes'][1]['streamingOptions']['ph'][0]['service']['id']='netflix';mutations.append((q,'episode_link_unavailable'))
  for bad in ['https://evil.example/episode','https://tv.apple.com.evil.example/episode/x',URLS[provider][1]+"'; echo injected"]:
   q=show(provider);o=q['seasons'][0]['episodes'][1]['streamingOptions']['ph'][0];o['link']=o['videoLink']=bad;mutations.append((q,'episode_link_unavailable'))
  q=show(provider);q['seasons'][0]['episodes'][1]['streamingOptions']['ph']=[offer(provider,ROOTS[provider])];mutations.append((q,'episode_link_unavailable'))
  q=show(provider);q['seasons'][0]['episodes'][1]['streamingOptions']=copy.deepcopy(q['seasons'][0]['episodes'][0]['streamingOptions']);mutations.append((q,'episode_link_unavailable'))
  for entity in ['media_player.bravia_xr_55x90l','remote.sony_xr_55x90l','media_player.sony_xr_55x90l_2','media_player.android_tv_10_0_0_174']:hass.states.async_set(entity,'off')
  for q,status in mutations:
   response={'status':200,'content':[q]};r=await run();assert r['status']==status and not calls,(provider,q,r,calls)
   if status=='episode_link_unavailable':
    assert r['availability_verified'] is False and 'NOT proof' in r['message']
  awake()
  response={'status':200,'content':[show(provider)]};adb_ok=False;r=await run();assert r['status']=='failed';assert [d['command'] for domain,d in calls if domain=='remote']==['HOME'];adb_ok=True
  if provider=='apple':
   q=show(provider);q['seasons'][0]['episodes'][1]['streamingOptions']={}
   response={'status':200,'content':[q]}
   apple_result={'status':'episode_resolved','title_link':URLS['apple'][1],'episode_title':'Second','season':1,'episode':2}
   r=await run();assert r['status']=='playback_requested' and r['title_link']==URLS['apple'][1],r
   apple_result={}
  if provider=='hbo':
   stop_ok=False;r=await run();assert r['status']=='failed' and len(calls)==1 and calls[0][0]=='androidtv';stop_ok=True
  if provider=='prime':
   r=await run(select_profile=False);assert [d['command'] for domain,d in calls if domain=='remote']==['HOME','DPAD_CENTER']
  print('PASS',provider,'exact native episode URI/package, numeric guards, subscription/host checks, delayed wake readiness, wake/ADB timeout blocks launch, no parent/shared-episode fallback and shared profile/Play controls without episode-menu navigation.')
 print('PASS all native episode services mocked; no TV actions.')
asyncio.run(main())
