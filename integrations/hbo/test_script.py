import asyncio,yaml
from homeassistant.core import HomeAssistant,Context,SupportsResponse
from homeassistant.helpers.script import Script
from homeassistant.helpers import config_validation as cv

def no_delays(v):
 if isinstance(v,list):return [no_delays(x) for x in v if not(isinstance(x,dict) and 'delay' in x)]
 if isinstance(v,dict):return {k:no_delays(x) for k,x in v.items()}
 return v
async def main():
 hass=HomeAssistant('/tmp/hbo-restart-check');raw=yaml.safe_load(open('/config/scripts.yaml'))['play_hbo_title']['sequence'];calls=[];stop_ok=True;response={'status':200,'content':[{'title':'Game of Thrones','streamingOptions':{'ph':[{'service':{'id':'hbo'},'type':'subscription','link':'https://play.hbomax.com/show/4f6b4985-2dc9-4ab6-ac79-d60f0860b0ac'}]}}]}
 async def lookup(call):return response
 async def capture(call):
  calls.append((call.domain,dict(call.data)))
  if call.domain=='androidtv':hass.states.async_set('media_player.android_tv_10_0_0_174','idle',{'adb_response':'NOVA_HBO_STOP_'+call.context.id if stop_ok else 'failed'})
 hass.services.async_register('rest_command','netflix_title_search',lookup,supports_response=SupportsResponse.ONLY)
 for domain,name in [('androidtv','adb_command'),('remote','send_command'),('media_player','play_media')]:hass.services.async_register(domain,name,capture)
 script=Script(hass,cv.SCRIPT_SCHEMA(no_delays(raw)),'HBO restart test','script')
 async def run(**kw):
  calls.clear();return (await script.async_run({'query':'Game of Thrones',**kw},Context())).service_response
 def keys():return [d['command'] for domain,d in calls if domain=='remote']
 r=await run();assert r['status']=='playback_requested';assert keys()==['HOME','DPAD_CENTER','DPAD_CENTER'];assert calls[0][0]=='androidtv'
 r=await run(from_start=True);assert r['status']=='restart_requested' and r['from_start'] is True;assert keys()==['HOME','DPAD_CENTER',['DPAD_RIGHT','DPAD_CENTER']]
 r=await run(start_playback=False);assert r['status']=='title_link_sent';assert keys()==['HOME','DPAD_CENTER']
 stop_ok=False;r=await run(from_start=True);assert r['status']=='failed';assert not keys();assert not any(d=='media_player' for d,_ in calls)
 stop_ok=True;response={'status':429,'content':'limited'};r=await run(from_start=True);assert r['status']=='failed' and not calls
 response={'status':200,'content':[{'title':'Game of Thrones','streamingOptions':{}}]};r=await run(from_start=True);assert r['status']=='unavailable' and not calls
 print('PASS cold launch precedes title/profile; Resume and Restart paths differ; details-only does not play; launch/catalog failures stop safely. Services mocked.')
asyncio.run(main())
