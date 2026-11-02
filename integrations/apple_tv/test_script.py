import asyncio,copy,os,yaml
from homeassistant.core import HomeAssistant,Context,SupportsResponse
from homeassistant.helpers.script import Script
from homeassistant.helpers import config_validation as cv
URL='https://tv.apple.com/ph/show/severance/umc.cmc.1srk2goyh2q2zdxcx605w8vtx'
def movie(title='Severance',year=2022,link=URL,service='apple',kind='subscription'):
 return {'title':title,'showType':'series','firstAirYear':year,'streamingOptions':{'ph':[{'service':{'id':service},'type':kind,'link':link}]}}
def no_delays(value):
 if isinstance(value,list):return [no_delays(x) for x in value if not (isinstance(x,dict) and 'delay' in x)]
 if isinstance(value,dict):return {k:no_delays(v) for k,v in value.items()}
 return value
async def main():
 hass=HomeAssistant('/tmp/apple-script-check');raw=yaml.safe_load(open(os.environ.get('NOVA_APPLE_SCRIPTS_PATH','/config/scripts.yaml')))['play_apple_tv_title']['sequence'];calls=[];response={'status':200,'content':[movie()]};adb_ok=True
 async def lookup(call):return response
 async def capture(call):
  calls.append((call.domain,dict(call.data)))
  if call.domain=='androidtv':hass.states.async_set('media_player.android_tv_10_0_0_174','idle',{'adb_response':('Status: ok\n' if adb_ok else 'Error\n')+'NOVA_APPLE_'+call.context.id})
 hass.services.async_register('rest_command','netflix_title_search',lookup,supports_response=SupportsResponse.ONLY)
 for domain,name in [('androidtv','adb_command'),('remote','send_command')]:hass.services.async_register(domain,name,capture)
 script=Script(hass,cv.SCRIPT_SCHEMA(no_delays(raw)),'Apple TV check','script')
 async def run(**kwargs):
  calls.clear();return (await script.async_run({'query':'Severance',**kwargs},Context())).service_response
 result=await run();assert result['status']=='playback_requested',result
 command=next(data['command'] for domain,data in calls if domain=='androidtv');assert '-p com.apple.atve.sony.appletv' in command and URL in command
 assert [d['command'] for domain,d in calls if domain=='remote']==['HOME','DPAD_CENTER','MEDIA_PLAY']
 result=await run(start_playback=False);assert result['status']=='title_link_sent';assert [d['command'] for domain,d in calls if domain=='remote']==['HOME']
 print('PASS playback targets installed Apple app; details-only sends neither OK nor Play')
 response={'status':200,'content':[movie(year=2004),movie(year=2024)]};result=await run(year=2004,start_playback=False);assert result['year']==2004
 result=await run();assert result['status']=='needs_clarification' and not calls
 print('PASS explicit year resolves collisions; ambiguity sends no TV commands')
 for bad in [movie(kind='rent'),movie(service='hbo'),movie(link='https://evil.example/title'),movie(link=URL+"'; bad-command")]:
  response={'status':200,'content':[bad]};result=await run();assert result['status']=='unavailable' and not calls,result
 response={'status':429,'content':'limited'};result=await run();assert result['status']=='failed' and not calls
 print('PASS rental, wrong service, unsafe link, and lookup errors send no TV commands')
 response={'status':200,'content':[movie()]};adb_ok=False;result=await run();assert result['status']=='failed';assert [d['command'] for domain,d in calls if domain=='remote']==['HOME']
 print('PASS failed ADB launch returns failure and never presses OK; all services mocked')
asyncio.run(main())
