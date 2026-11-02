import os
import asyncio,yaml
from homeassistant.core import HomeAssistant,Context,SupportsResponse
from homeassistant.helpers.script import Script
from homeassistant.helpers import config_validation as cv

def no_delays(v):
 if isinstance(v,list):return [no_delays(x) for x in v if not(isinstance(x,dict) and 'delay' in x)]
 if isinstance(v,dict):
  out={k:no_delays(x) for k,x in v.items()}
  if 'wait_template' in out:out['timeout']='00:00:00'
  return out
 return v
async def main():
 hass=HomeAssistant('/tmp/netflix-restart-check');scripts=yaml.safe_load(open(os.environ.get('NOVA_SCRIPTS_PATH', '/config/scripts.yaml')));calls=[];response={'status':200,'content':[{'title':'White Chicks','showType':'movie','streamingOptions':{'ph':[{'service':{'id':'netflix'},'type':'subscription','link':'https://www.netflix.com/title/60034587'}]}}]}
 def foreground(app):hass.states.async_set('remote.sony_xr_55x90l','on',{'current_activity':app})
 async def lookup(call):return response
 async def capture(call):
  calls.append((call.domain,dict(call.data, _service=call.service)))
 hass.services.async_register('rest_command','netflix_title_search',lookup,supports_response=SupportsResponse.ONLY)
 for domain,name in [('media_player','play_media'),('media_player','media_play'),('remote','send_command')]:hass.services.async_register(domain,name,capture)
 helper=Script(hass,cv.SCRIPT_SCHEMA(no_delays(scripts['netflix_restart_from_playback']['sequence'])),'restart test','script')
 async def restart(call):return (await helper.async_run({},call.context)).service_response
 hass.services.async_register('script','netflix_restart_from_playback',restart,supports_response=SupportsResponse.ONLY)
 script=Script(hass,cv.SCRIPT_SCHEMA(no_delays(scripts['play_netflix_title']['sequence'])),'Netflix test','script')
 foreground('com.netflix.ninja');result=(await script.async_run({'query':'White Chicks'},Context())).service_response;assert result['status']=='playback_requested';assert [d['command'] for domain,d in calls if domain=='remote']==['HOME'];assert calls[-1][1]['_service']=='media_play' and result['play_command_sent'] is True
 calls.clear();result=(await script.async_run({'query':'White Chicks','from_start':True},Context())).service_response;assert result['status']=='restart_requested' and result['from_start'] is True;assert [d['command'] for domain,d in calls if domain=='remote']==['HOME',['DPAD_DOWN','DPAD_CENTER']];assert not any(d['_service']=='media_play' for _,d in calls)
 calls.clear();foreground('launcher');result=(await helper.async_run({},Context())).service_response;assert result['status']=='needs_netflix_playback' and not calls
 calls.clear();result=(await script.async_run({'query':'White Chicks'},Context())).service_response;assert result['status']=='needs_netflix_foreground' and result['play_command_sent'] is False;assert not any(d['_service']=='media_play' for _,d in calls)
 response={'status':429,'content':'limited'};calls.clear();result=(await script.async_run({'query':'White Chicks','from_start':True},Context())).service_response;assert result['status']=='failed' and not calls
 print('PASS normal launch sends dedicated Play; wrong foreground blocks Play; explicit restart acts on the title page without Back; wrong app blocks selection; failed lookup sends no TV commands. All services mocked.')
asyncio.run(main())
