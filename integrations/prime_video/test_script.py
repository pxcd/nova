import asyncio,copy,os,yaml
from homeassistant.core import HomeAssistant,Context,SupportsResponse
from homeassistant.helpers.script import Script
from homeassistant.helpers import config_validation as cv
URL='https://app.primevideo.com/detail?gti=amzn1.dv.gti.fb4939ee-4123-439a-a53f-039572cd8c5f'
def movie(title='Fallout',year=2022,link=URL,service='prime',kind='subscription'):
 return {'title':title,'showType':'series','firstAirYear':year,'streamingOptions':{'ph':[{'service':{'id':service},'type':kind,'link':link}]}}
def no_delays(value):
 if isinstance(value,list):return [no_delays(x) for x in value if not (isinstance(x,dict) and 'delay' in x)]
 if isinstance(value,dict):return {k:no_delays(v) for k,v in value.items()}
 return value
async def main():
 hass=HomeAssistant('/tmp/apple-script-check');raw=yaml.safe_load(open(os.environ.get('NOVA_STREAMING_SCRIPTS_PATH','/config/scripts.yaml')))['play_prime_video_title']['sequence'];calls=[];response={'status':200,'content':[movie()]};adb_ok=True
 async def lookup(call):return response
 async def capture(call):
  calls.append((call.domain,dict(call.data)))
  if call.domain=='androidtv':hass.states.async_set('media_player.android_tv_10_0_0_174','idle',{'adb_response':('Status: ok\n' if adb_ok else 'Error\n')+'NOVA_PRIME_'+call.context.id})
 hass.services.async_register('rest_command','netflix_title_search',lookup,supports_response=SupportsResponse.ONLY)
 for domain,name in [('androidtv','adb_command'),('remote','send_command')]:hass.services.async_register(domain,name,capture)
 controls=Script(hass,cv.SCRIPT_SCHEMA(no_delays(yaml.safe_load(open(os.environ.get('NOVA_STREAMING_SCRIPTS_PATH','/config/scripts.yaml')))['streaming_app_profile_and_play']['sequence'])),'Shared playback controls','script')
 async def run_controls(call):await controls.async_run(dict(call.data),call.context)
 hass.services.async_register('script','streaming_app_profile_and_play',run_controls)
 script=Script(hass,cv.SCRIPT_SCHEMA(no_delays(raw)),'Prime Video check','script')
 async def run(**kwargs):
  calls.clear();return (await script.async_run({'query':'Fallout',**kwargs},Context())).service_response
 result=await run();assert result['status']=='playback_requested',result
 command=next(data['command'] for domain,data in calls if domain=='androidtv');assert '-p com.amazon.amazonvideo.livingroom' in command and URL in command
 assert [d['command'] for domain,d in calls if domain=='remote']==['HOME','DPAD_CENTER','DPAD_CENTER']
 result=await run(start_playback=False);assert result['status']=='title_link_sent';assert [d['command'] for domain,d in calls if domain=='remote']==['HOME','DPAD_CENTER']
 result=await run(select_profile=False);assert [d['command'] for domain,d in calls if domain=='remote']==['HOME','DPAD_CENTER']
 result=await run(from_start=True);assert result['status']=='restart_requested' and result['from_start'] is True;assert [d['command'] for domain,d in calls if domain=='remote']==['HOME','DPAD_CENTER',['DPAD_UP','DPAD_CENTER']]
 result=await run(from_start=True,start_playback=False);assert result['status']=='title_link_sent' and result['from_start'] is False;assert [d['command'] for domain,d in calls if domain=='remote']==['HOME','DPAD_CENTER']
 print('PASS normal playback unchanged; explicit Restart uses Up + OK; details-only never restarts; profile step can be disabled')
 item=movie();item['streamingOptions']['ph'].append({**item['streamingOptions']['ph'][0],'link':URL.replace('fb4939ee','ab4939ee')});response={'status':200,'content':[item]};result=await run();assert result['status']=='playback_requested'
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
