import asyncio,os,yaml,json
from homeassistant.core import HomeAssistant,Context,SupportsResponse
from homeassistant.helpers.script import Script
from homeassistant.helpers import config_validation as cv
async def main():
 hass=HomeAssistant('/tmp/nova-kodi-resolution-check');raw=yaml.safe_load(open(os.environ.get('NOVA_KODI_SCRIPTS_PATH','/config/scripts.yaml')))['play_kodi_pov'];calls=[]
 async def capture(call):
  calls.append(call.data['request_payload']);return {'status':'episode_catalog' if call.data['request_payload'].get('operation')=='browse' else 'playback_requested','playback_verified':False}
 hass.services.async_register('script','pov_execute_request',capture,supports_response=SupportsResponse.ONLY)
 script=Script(hass,cv.SCRIPT_SCHEMA(raw['sequence']),'Resolution bridge','script')
 for value in ['1080p','720p','2160p','highest',None]:
  await script.async_run({'query':'Hocus Pocus','media_type':'movie','resolution':value},Context());assert calls[-1]['resolution']==value;assert calls[-1]['query']=='Hocus Pocus'
 await script.async_run({'query':'South Park','media_type':'series','season':28,'episode':1},Context());assert calls[-1]['resolution'] is None;assert calls[-1]['season']==28 and calls[-1]['episode']==1
 await script.async_run({'query':'South Park','media_type':'series','latest_episode':True,'resolution':'1080p'},Context());assert calls[-1]['latest_episode'] is True;assert calls[-1]['season'] is None and calls[-1]['episode'] is None;assert calls[-1]['resolution']=='1080p'
 shell_calls=[]
 async def shell(call):
  shell_calls.append(call.data['request_payload']);return {'returncode':0,'stdout':json.dumps({'status':'episode_catalog','command_sent':False})}
 hass.services.async_register('shell_command','nova_pov_request',shell,supports_response=SupportsResponse.ONLY)
 raw=yaml.safe_load(open(os.environ.get('NOVA_KODI_SCRIPTS_PATH','/config/scripts.yaml')))['browse_kodi_series']
 browse=Script(hass,cv.SCRIPT_SCHEMA(raw['sequence']),'POV catalog','script')
 calls.clear()
 result=(await browse.async_run({'query':'South Park','season':5,'episode_offset':100},Context())).service_response
 assert result['status']=='episode_catalog' and not calls
 assert shell_calls[-1]['operation']=='browse' and shell_calls[-1]['season']==5 and shell_calls[-1]['episode_offset']==100
 before=len(shell_calls)
 await browse.async_run({'query':'South Park','prepare_playback':True},Context())
 assert len(shell_calls)==before and calls[-1]['operation']=='browse'
 print('PASS catalog information-only path has no app launch; preparation delegates only when explicitly enabled.')
 print('PASS HA wrapper preserves explicit resolution, omitted/null defaults and episode identity; no TV actions.')
asyncio.run(main())
