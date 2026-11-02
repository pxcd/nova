import asyncio,os,yaml
from homeassistant.core import HomeAssistant,Context,SupportsResponse
from homeassistant.helpers.script import Script
from homeassistant.helpers import config_validation as cv
async def main():
 hass=HomeAssistant('/tmp/nova-kodi-resolution-check');raw=yaml.safe_load(open(os.environ.get('NOVA_KODI_SCRIPTS_PATH','/config/scripts.yaml')))['play_kodi_pov'];calls=[]
 async def capture(call):
  calls.append(call.data['request_payload']);return {'status':'playback_requested','playback_verified':False}
 hass.services.async_register('script','pov_execute_request',capture,supports_response=SupportsResponse.ONLY)
 script=Script(hass,cv.SCRIPT_SCHEMA(raw['sequence']),'Resolution bridge','script')
 for value in ['1080p','720p','2160p','highest',None]:
  await script.async_run({'query':'Hocus Pocus','media_type':'movie','resolution':value},Context());assert calls[-1]['resolution']==value;assert calls[-1]['query']=='Hocus Pocus'
 await script.async_run({'query':'South Park','media_type':'series','season':28,'episode':1},Context());assert calls[-1]['resolution'] is None;assert calls[-1]['season']==28 and calls[-1]['episode']==1
 print('PASS HA wrapper preserves explicit resolution, omitted/null defaults and episode identity; no TV actions.')
asyncio.run(main())
